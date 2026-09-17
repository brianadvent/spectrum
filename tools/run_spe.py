#!/usr/bin/env python3
"""Robuster Runner für die SPE-Replikation 2026.

Der Standardmodus ist ein vollständig lokaler Dry-Run. Netzwerkzugriffe sind
nur mit --execute und einer exakten Request-Bestätigung möglich.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import itertools
import json
import math
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parent
DEFAULT_PROTOCOL = TOOL_DIR / "protocol.json"
CHOICE_RE = re.compile(r"^[AB]$")


class ProtocolError(RuntimeError):
    """Das eingefrorene Protokoll oder seine Daten sind inkonsistent."""


class ApiRequestError(RuntimeError):
    """Ein API-Aufruf ist fehlgeschlagen."""

    def __init__(self, message: str, *, status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after

    @property
    def retryable(self) -> bool:
        return self.status is None or self.status in {408, 409, 429} or bool(self.status and self.status >= 500)


class AttemptBudgetExceeded(RuntimeError):
    """Die vorab bestätigte Obergrenze physischer API-Aufrufe ist erreicht."""


@dataclass(frozen=True)
class Outcome:
    id: str
    text: str


@dataclass(frozen=True)
class Pair:
    index: int
    a: Outcome
    b: Outcome


@dataclass(frozen=True)
class LogicalRequest:
    pair: Pair
    repetition: int
    display_a: Outcome
    display_b: Outcome

    @property
    def logical_id(self) -> str:
        return f"p{self.pair.index:05d}-r{self.repetition:02d}"

    @property
    def order(self) -> str:
        return "canonical" if self.repetition % 2 == 0 else "reversed"

    def canonical_choice(self, displayed_choice: str) -> str:
        if self.order == "canonical":
            return displayed_choice
        return "A" if displayed_choice == "B" else "B"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(data)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_protocol(path: Path) -> dict[str, Any]:
    protocol = load_json(path)
    required = {"protocol_version", "outcomes", "elicitation", "providers", "processing"}
    missing = required.difference(protocol)
    if missing:
        raise ProtocolError(f"Protokollfelder fehlen: {sorted(missing)}")
    return protocol


def resolve_outcomes_path(protocol: dict[str, Any], override: Path | None) -> Path:
    if override is not None:
        return override.resolve()
    return (REPO_ROOT / protocol["outcomes"]["relative_path"]).resolve()


def load_and_validate_outcomes(path: Path, protocol: dict[str, Any]) -> tuple[list[Outcome], dict[str, Any]]:
    raw = path.read_bytes()
    actual_hash = sha256_bytes(raw)
    expected_hash = protocol["outcomes"]["sha256"]
    if actual_hash != expected_hash:
        raise ProtocolError(f"Outcome-Hash weicht ab: erwartet {expected_hash}, erhalten {actual_hash}")

    payload = json.loads(raw.decode("utf-8"))
    rows = payload.get("outcomes")
    if not isinstance(rows, list):
        raise ProtocolError("outcomes.json enthält keine Outcome-Liste")

    outcomes = [Outcome(str(row["id"]), str(row["text"])) for row in rows]
    expected_count = int(protocol["outcomes"]["expected_count"])
    if len(outcomes) != expected_count:
        raise ProtocolError(f"Erwartet {expected_count} Outcomes, gefunden {len(outcomes)}")
    if len({item.id for item in outcomes}) != len(outcomes):
        raise ProtocolError("Outcome-IDs sind nicht eindeutig")
    if len({item.text for item in outcomes}) != len(outcomes):
        raise ProtocolError("Outcome-Texte sind nicht eindeutig")
    if any(not item.id.strip() or not item.text.strip() for item in outcomes):
        raise ProtocolError("Leere Outcome-ID oder leerer Outcome-Text")
    return outcomes, payload.get("meta", {})


def generate_pairs(outcomes: list[Outcome]) -> list[Pair]:
    return [Pair(i, a, b) for i, (a, b) in enumerate(itertools.combinations(outcomes, 2))]


def logical_requests(pair: Pair, k: int) -> list[LogicalRequest]:
    requests: list[LogicalRequest] = []
    for repetition in range(k):
        if repetition % 2 == 0:
            display_a, display_b = pair.a, pair.b
        else:
            display_a, display_b = pair.b, pair.a
        requests.append(LogicalRequest(pair, repetition, display_a, display_b))
    return requests


def render_prompt(template: str, request: LogicalRequest) -> str:
    return template.format(outcome_a=request.display_a.text, outcome_b=request.display_b.text)


def normalize_choice(raw_text: str) -> str | None:
    normalized = raw_text.strip().upper()
    return normalized if CHOICE_RE.fullmatch(normalized) else None


def load_env_file(path: Path) -> None:
    """Lädt einfache KEY=VALUE-Zeilen, ohne vorhandene Umgebungswerte zu überschreiben."""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY"} and key not in os.environ:
            os.environ[key] = value


def sanitize_error_body(body: str, limit: int = 2000) -> str:
    body = body.replace("\n", " ").strip()
    return body[:limit]


class JsonlStore:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.responses_path = run_dir / "responses.jsonl"
        self.attempts_path = run_dir / "attempts.jsonl"
        self._lock = asyncio.Lock()
        self.attempts_by_id: dict[str, list[dict[str, Any]]] = {}
        for row in self.read_jsonl(self.attempts_path):
            self.attempts_by_id.setdefault(row["logical_id"], []).append(row)

    @staticmethod
    def read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ProtocolError(f"Ungültiges JSONL in {path}:{line_number}: {exc}") from exc
        return rows

    def completed(self) -> dict[str, dict[str, Any]]:
        rows = self.read_jsonl(self.responses_path)
        completed: dict[str, dict[str, Any]] = {}
        for row in rows:
            logical_id = row["logical_id"]
            if logical_id in completed and completed[logical_id] != row:
                raise ProtocolError(f"Widersprüchliche doppelte Response für {logical_id}")
            completed[logical_id] = row
        return completed

    async def append(self, path: Path, row: dict[str, Any]) -> None:
        encoded = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        async with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())

    async def append_attempt(self, row: dict[str, Any]) -> None:
        await self.append(self.attempts_path, row)
        self.attempts_by_id.setdefault(row["logical_id"], []).append(row)

    async def append_response(self, row: dict[str, Any]) -> None:
        await self.append(self.responses_path, row)


class RateLimiter:
    def __init__(self, requests_per_minute: int):
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute muss positiv sein")
        self.interval = 60.0 / requests_per_minute
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.interval
        if wait:
            await asyncio.sleep(wait)


class AttemptBudget:
    """Persistente, konservative Obergrenze für tatsächlich gestartete API-Aufrufe."""

    def __init__(self, state_path: Path, maximum: int):
        self.state_path = state_path
        self.maximum = maximum
        self._lock = asyncio.Lock()
        if state_path.exists():
            state = load_json(state_path)
            if int(state.get("maximum", -1)) != maximum:
                raise ProtocolError("Gespeichertes API-Attempt-Limit weicht vom Run-Manifest ab")
            self.current = int(state.get("reserved", 0))
        else:
            self.current = 0
            atomic_write_json(state_path, {"maximum": maximum, "reserved": 0, "updated_at": utc_now()})

    async def reserve(self) -> int:
        async with self._lock:
            if self.current >= self.maximum:
                raise AttemptBudgetExceeded(
                    f"Bestätigte Obergrenze von {self.maximum} physischen API-Aufrufen erreicht"
                )
            self.current += 1
            atomic_write_json(
                self.state_path,
                {"maximum": self.maximum, "reserved": self.current, "updated_at": utc_now()},
            )
            return self.current


class ProviderAdapter:
    def __init__(self, provider: str, config: dict[str, Any], api_key: str, session: Any):
        self.provider = provider
        self.config = config
        self.api_key = api_key
        self.session = session

    def payload(self, prompt: str, max_output_tokens: int) -> dict[str, Any]:
        if self.provider == "openai":
            return {
                "model": self.config["model"],
                "input": [{"role": "user", "content": prompt}],
                "reasoning": self.config["reasoning"],
                "max_output_tokens": max_output_tokens,
                "service_tier": self.config["service_tier"],
                "store": bool(self.config.get("store", False)),
            }
        if self.provider == "anthropic":
            payload = {
                "model": self.config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_output_tokens,
            }
            if "thinking" in self.config:
                payload["thinking"] = self.config["thinking"]
            if "service_tier" in self.config:
                payload["service_tier"] = self.config["service_tier"]
            return payload
        raise ProtocolError(f"Unbekannter Provider: {self.provider}")

    def headers(self) -> dict[str, str]:
        if self.provider == "openai":
            return {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "dissertation-spe-replication/1.0",
            }
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.config["anthropic_version"],
            "Content-Type": "application/json",
            "User-Agent": "dissertation-spe-replication/1.0",
        }

    async def request(self, prompt: str, max_output_tokens: int) -> dict[str, Any]:
        payload = self.payload(prompt, max_output_tokens)
        try:
            async with self.session.post(self.config["endpoint"], headers=self.headers(), json=payload) as response:
                body = await response.text()
                retry_after = response.headers.get("retry-after")
                parsed_retry = None
                if retry_after:
                    try:
                        parsed_retry = float(retry_after)
                    except ValueError:
                        parsed_retry = None
                if response.status >= 400:
                    raise ApiRequestError(
                        f"HTTP {response.status}: provider request failed",
                        status=response.status,
                        retry_after=parsed_retry,
                    )
                try:
                    data = json.loads(body)
                except json.JSONDecodeError as exc:
                    raise ApiRequestError("Provider returned a non-JSON response") from exc
                return self.parse(data)
        except asyncio.TimeoutError as exc:
            raise ApiRequestError("Request-Timeout") from exc

    def parse(self, data: dict[str, Any]) -> dict[str, Any]:
        if self.provider == "openai":
            texts: list[str] = []
            for item in data.get("output", []):
                if item.get("type") != "message":
                    continue
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        texts.append(str(content.get("text", "")))
            return {
                "raw_text": "".join(texts),
                "response_id": data.get("id"),
                "returned_model": data.get("model"),
                "status": data.get("status"),
                "usage": data.get("usage", {}),
                "service_tier": data.get("service_tier"),
                "stop_reason": data.get("incomplete_details"),
            }

        texts = [str(block.get("text", "")) for block in data.get("content", []) if block.get("type") == "text"]
        return {
            "raw_text": "".join(texts),
            "response_id": data.get("id"),
            "returned_model": data.get("model"),
            "status": data.get("type"),
            "usage": data.get("usage", {}),
            "service_tier": data.get("usage", {}).get("service_tier"),
            "stop_reason": data.get("stop_reason"),
        }


def atomic_write_json(path: Path, data: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def create_or_validate_run_manifest(
    run_dir: Path,
    protocol: dict[str, Any],
    protocol_path: Path,
    outcomes_path: Path,
    outcome_meta: dict[str, Any],
    provider: str,
    pair_count: int,
    total_requests: int,
    requests_per_minute: int,
    concurrent_pairs: int,
    run_scope: str,
    selected_pair_indices: list[int],
    max_api_attempts: int,
) -> dict[str, Any]:
    manifest_path = run_dir / "run_manifest.json"
    immutable = {
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": sha256_bytes(protocol_path.read_bytes()),
        "effective_protocol_sha256": canonical_json_hash(protocol),
        "language": protocol.get("language", "de"),
        "processing": protocol["processing"],
        "provider": provider,
        "provider_config": protocol["providers"][provider],
        "elicitation": protocol["elicitation"],
        "instrument_file": outcomes_path.name,
        "outcomes_sha256": sha256_bytes(outcomes_path.read_bytes()),
        "source_outcome_meta": outcome_meta,
        "validated_outcome_count": int(protocol["outcomes"]["expected_count"]),
        "pair_count": pair_count,
        "total_logical_requests": total_requests,
        "max_api_attempts": max_api_attempts,
        "run_scope": run_scope,
        "selected_pair_indices": selected_pair_indices,
        "requests_per_minute": requests_per_minute,
        "concurrent_pairs": concurrent_pairs,
    }
    identity = canonical_json_hash(immutable)
    manifest = {**immutable, "run_identity": identity, "created_at": utc_now()}

    if manifest_path.exists():
        existing = load_json(manifest_path)
        if existing.get("run_identity") != identity:
            raise ProtocolError("Bestehendes Run-Verzeichnis gehört zu einer anderen Konfiguration")
        return existing

    if run_dir.exists() and any(run_dir.iterdir()):
        raise ProtocolError("Ausgabeverzeichnis ist nicht leer und enthält kein passendes Run-Manifest")
    run_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(manifest_path, manifest)
    return manifest


async def run_logical_request(
    adapter: ProviderAdapter,
    limiter: RateLimiter,
    attempt_budget: AttemptBudget,
    store: JsonlStore,
    request: LogicalRequest,
    prompt_template: str,
    max_output_tokens: int,
    transport_retries: int,
    invalid_retries: int,
) -> dict[str, Any] | None:
    prompt = render_prompt(prompt_template, request)
    prompt_hash = sha256_bytes(prompt.encode("utf-8"))
    prior = store.attempts_by_id.get(request.logical_id, [])
    transport_attempt = sum(x["kind"] in {"transport_error", "client_error"} for x in prior)
    invalid_attempt = sum(x["kind"] == "invalid_model_output" for x in prior)
    attempt_number = len(prior)
    # Recover a valid attempt logged just before an interruption of response persistence.
    recovered = next((x for x in prior if x.get("kind") == "valid" and x.get("normalized_choice") in {"A", "B"}), None)
    if recovered:
        choice = recovered["normalized_choice"]
        final = {**recovered, "pair_index": request.pair.index, "repetition": request.repetition,
                 "order": request.order, "prompt_sha256": prompt_hash,
                 "canonical_outcome_a_id": request.pair.a.id, "canonical_outcome_b_id": request.pair.b.id,
                 "display_outcome_a_id": request.display_a.id, "display_outcome_b_id": request.display_b.id,
                 "displayed_choice": choice, "canonical_choice": request.canonical_choice(choice),
                 "canonical_winner_id": request.pair.a.id if request.canonical_choice(choice) == "A" else request.pair.b.id,
                 "requested_model": adapter.config["model"], "recovered_from_attempt_log": True}
        await store.append_response(final)
        return final

    while transport_attempt <= transport_retries and invalid_attempt <= invalid_retries:
        attempt_number += 1
        global_attempt = await attempt_budget.reserve()
        await limiter.acquire()
        started = time.monotonic()
        try:
            parsed = await adapter.request(prompt, max_output_tokens)
            elapsed = time.monotonic() - started
            raw_text = parsed["raw_text"]
            choice = normalize_choice(raw_text)
            attempt_row = {
                "timestamp": utc_now(),
                "logical_id": request.logical_id,
                "attempt": attempt_number,
                "global_api_attempt": global_attempt,
                "kind": "valid" if choice else "invalid_model_output",
                "latency_seconds": round(elapsed, 6),
                "raw_text": raw_text,
                "normalized_choice": choice,
                "response_id": parsed.get("response_id"),
                "returned_model": parsed.get("returned_model"),
                "status": parsed.get("status"),
                "stop_reason": parsed.get("stop_reason"),
                "usage": parsed.get("usage", {}),
                "service_tier": parsed.get("service_tier"),
            }
            await store.append_attempt(attempt_row)
            if choice:
                final = {
                    "timestamp": utc_now(),
                    "logical_id": request.logical_id,
                    "pair_index": request.pair.index,
                    "repetition": request.repetition,
                    "canonical_outcome_a_id": request.pair.a.id,
                    "canonical_outcome_b_id": request.pair.b.id,
                    "display_outcome_a_id": request.display_a.id,
                    "display_outcome_b_id": request.display_b.id,
                    "order": request.order,
                    "prompt_sha256": prompt_hash,
                    "raw_text": raw_text,
                    "displayed_choice": choice,
                    "canonical_choice": request.canonical_choice(choice),
                    "canonical_winner_id": request.pair.a.id if request.canonical_choice(choice) == "A" else request.pair.b.id,
                    "response_id": parsed.get("response_id"),
                    "requested_model": adapter.config["model"],
                    "returned_model": parsed.get("returned_model"),
                    "usage": parsed.get("usage", {}),
                    "service_tier": parsed.get("service_tier"),
                    "successful_attempt": attempt_number,
                }
                await store.append_response(final)
                return final
            invalid_attempt += 1
        except ApiRequestError as exc:
            elapsed = time.monotonic() - started
            await store.append_attempt({
                "timestamp": utc_now(),
                "logical_id": request.logical_id,
                "attempt": attempt_number,
                "global_api_attempt": global_attempt,
                "kind": "transport_error",
                "latency_seconds": round(elapsed, 6),
                "status": exc.status,
                "retryable": exc.retryable,
                "error": str(exc),
            })
            if not exc.retryable:
                raise ProtocolError(f"Non-retryable API error (HTTP {exc.status}); run stopped") from exc
            transport_attempt += 1
            delay = exc.retry_after if exc.retry_after is not None else min(60.0, (2 ** min(transport_attempt, 6)) + random.random())
            await asyncio.sleep(delay)
        except ProtocolError:
            raise
        except Exception as exc:  # Netzwerkbibliothek-spezifische Fehler
            elapsed = time.monotonic() - started
            transport_attempt += 1
            await store.append_attempt({
                "timestamp": utc_now(),
                "logical_id": request.logical_id,
                "attempt": attempt_number,
                "global_api_attempt": global_attempt,
                "kind": "client_error",
                "latency_seconds": round(elapsed, 6),
                "retryable": True,
                "error": f"{type(exc).__name__}: {exc}",
            })
            await asyncio.sleep(min(60.0, (2 ** min(transport_attempt, 6)) + random.random()))
    terminal = {"logical_id": request.logical_id, "pair_index": request.pair.index,
                "order": request.order, "canonical_choice": None, "status": "no_valid_choice",
                "requested_model": adapter.config["model"], "timestamp": utc_now()}
    await store.append_response(terminal)
    return terminal


def build_aggregate(rows: Iterable[dict[str, Any]], pairs: list[Pair], k: int, manifest: dict[str, Any]) -> dict[str, Any]:
    by_pair: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_pair.setdefault(int(row["pair_index"]), []).append(row)

    preferences: dict[str, float] = {}
    incomplete: list[int] = []
    for pair in pairs:
        pair_rows = by_pair.get(pair.index, [])
        if len(pair_rows) != k or any(row.get("canonical_choice") not in {"A", "B"} for row in pair_rows):
            incomplete.append(pair.index)
            continue
        votes_a = sum(1 for row in pair_rows if row["canonical_choice"] == "A")
        preferences[f"{pair.a.id}|{pair.b.id}"] = votes_a / k

    return {
        "meta": {
            "timestamp": utc_now(),
            "n_pairs": len(preferences),
            "k_repetitions": k,
            "model": manifest["provider_config"]["model"],
            "provider": manifest["provider"],
            "use_system_prompt": False,
            "run_identity": manifest["run_identity"],
            "language": manifest.get("language", "de"),
            "outcomes_sha256": manifest.get("outcomes_sha256"),
            "incomplete_pair_indices": incomplete,
        },
        "preferences": preferences,
    }


def build_audit(
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    pairs: list[Pair],
    k: int,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    expected = len(pairs) * k
    ids = [row["logical_id"] for row in rows]
    id_counts = Counter(ids)
    duplicate_ids = sorted(item for item, count in id_counts.items() if count > 1)
    expected_ids = {request.logical_id for pair in pairs for request in logical_requests(pair, k)}
    observed_ids = set(ids)
    canonical_orders = sum(1 for row in rows if row.get("order") == "canonical")
    reversed_orders = sum(1 for row in rows if row.get("order") == "reversed")
    invalid_attempts = sum(1 for row in attempts if row.get("kind") == "invalid_model_output")
    error_attempts = sum(1 for row in attempts if row.get("kind") in {"transport_error", "client_error"})
    returned_models = sorted({str(row.get("returned_model")) for row in rows if row.get("returned_model")})
    observed_service_tiers = sorted({str(row.get("service_tier")) for row in rows if row.get("service_tier")})
    expected_service_tier = "default" if manifest["provider"] == "openai" else "standard"
    audit = {
        "audited_at": utc_now(),
        "run_identity": manifest["run_identity"],
        "expected_logical_requests": expected,
        "observed_logical_requests": len(rows),
        "unique_logical_requests": len(observed_ids),
        "missing_logical_ids": sorted(expected_ids - observed_ids),
        "unexpected_logical_ids": sorted(observed_ids - expected_ids),
        "duplicate_logical_ids": duplicate_ids,
        "canonical_order_count": canonical_orders,
        "reversed_order_count": reversed_orders,
        "invalid_model_output_attempts": invalid_attempts,
        "error_attempts": error_attempts,
        "returned_models": returned_models,
        "expected_service_tier": expected_service_tier,
        "observed_service_tiers": observed_service_tiers,
    }
    audit["complete"] = (
        len(rows) == expected
        and len(observed_ids) == expected
        and not audit["missing_logical_ids"]
        and not audit["unexpected_logical_ids"]
        and not duplicate_ids
        and canonical_orders == expected // 2
        and reversed_orders == expected // 2
        and observed_service_tiers == [expected_service_tier]
    )
    return audit


async def execute_run(args: argparse.Namespace, protocol: dict[str, Any], outcomes: list[Outcome], outcome_meta: dict[str, Any], pairs: list[Pair]) -> int:
    k = int(protocol["elicitation"]["k_repetitions"])
    total_requests = len(pairs) * k
    if args.confirm_requests != total_requests:
        print(
            f"Fehler: Echter Lauf verlangt --confirm-requests {total_requests}; erhalten {args.confirm_requests}.",
            file=sys.stderr,
        )
        return 2
    max_api_attempts = math.ceil(total_requests * float(protocol["processing"]["max_api_attempt_multiplier"]))
    if args.confirm_max_api_attempts != max_api_attempts:
        print(
            f"Fehler: Lauf verlangt --confirm-max-api-attempts {max_api_attempts}; erhalten {args.confirm_max_api_attempts}.",
            file=sys.stderr,
        )
        return 2
    if args.output_dir is None:
        print("Fehler: Echter Lauf verlangt --output-dir.", file=sys.stderr)
        return 2

    try:
        import aiohttp
    except ImportError:
        print("Fehler: Für echte Läufe wird aiohttp benötigt.", file=sys.stderr)
        return 2

    provider_config = protocol["providers"][args.provider]
    key_name = "OPENAI_API_KEY" if args.provider == "openai" else "ANTHROPIC_API_KEY"
    if args.env_file:
        load_env_file(args.env_file)
    api_key = os.getenv(key_name)
    if not api_key:
        print(f"Fehler: {key_name} ist nicht gesetzt.", file=sys.stderr)
        return 2

    run_dir = args.output_dir.resolve()
    manifest = create_or_validate_run_manifest(
        run_dir,
        protocol,
        args.protocol.resolve(),
        args.outcomes.resolve(),
        outcome_meta,
        args.provider,
        len(pairs),
        total_requests,
        args.requests_per_minute,
        args.concurrent_pairs,
        "preflight" if args.preflight_pairs else ("sample" if args.pair_indices_file else "full"),
        [pair.index for pair in pairs],
        max_api_attempts,
    )
    store = JsonlStore(run_dir)
    attempt_budget = AttemptBudget(run_dir / "attempt_budget.json", max_api_attempts)
    completed = store.completed()
    remaining_pairs = [
        pair for pair in pairs
        if any(request.logical_id not in completed for request in logical_requests(pair, k))
    ]
    print(f"Run: {manifest['run_identity']}")
    print(f"Bereits vollständig gespeicherte Requests: {len(completed):,}/{total_requests:,}")
    print(f"Noch zu bearbeitende Paare: {len(remaining_pairs):,}")

    timeout = aiohttp.ClientTimeout(total=120, connect=30)
    connector = aiohttp.TCPConnector(limit=max(args.concurrent_pairs * 2, 20))
    limiter = RateLimiter(args.requests_per_minute)
    queue: asyncio.Queue[Pair] = asyncio.Queue()
    for pair in remaining_pairs:
        queue.put_nowait(pair)

    progress_lock = asyncio.Lock()
    progress = len(completed)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        adapter = ProviderAdapter(args.provider, provider_config, api_key, session)

        async def worker() -> None:
            nonlocal progress
            while True:
                try:
                    pair = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    for request in logical_requests(pair, k):
                        if request.logical_id in completed:
                            continue
                        result = await run_logical_request(
                            adapter,
                            limiter,
                            attempt_budget,
                            store,
                            request,
                            protocol["elicitation"]["user_prompt_template"],
                            int(protocol["elicitation"]["max_output_tokens"]),
                            int(protocol["processing"]["transport_retries"]),
                            int(protocol["processing"]["invalid_response_retries"]),
                        )
                        if result:
                            completed[request.logical_id] = result
                            async with progress_lock:
                                progress += 1
                                if progress % 100 == 0 or progress == total_requests:
                                    print(f"Fortschritt: {progress:,}/{total_requests:,} ({progress/total_requests:.1%})")
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(args.concurrent_pairs)]
        worker_results = await asyncio.gather(*workers, return_exceptions=True)
        failures = [result for result in worker_results if isinstance(result, BaseException)]
        if failures:
            print(f"{len(failures)} worker(s) stopped; first error: {failures[0]}", file=sys.stderr)

    rows = JsonlStore.read_jsonl(store.responses_path)
    attempts = JsonlStore.read_jsonl(store.attempts_path)
    aggregate = build_aggregate(rows, pairs, k, manifest)
    audit = build_audit(rows, attempts, pairs, k, manifest)
    audit["worker_failures"] = [str(failure) for failure in failures]
    audit["reserved_api_attempts"] = attempt_budget.current
    audit["max_api_attempts"] = max_api_attempts
    audit["closed"] = not audit["missing_logical_ids"]
    audit["nondecisions"] = sum(row.get("canonical_choice") not in {"A", "B"} for row in rows)
    audit["complete"] = bool(audit["complete"] and not audit["nondecisions"] and not failures and attempt_budget.current <= max_api_attempts)
    atomic_write_json(run_dir / "preferences.json", aggregate)
    atomic_write_json(run_dir / "audit.json", audit)
    print(f"Audit vollständig: {audit['complete']}")
    print(f"Ergebnisse: {run_dir}")
    return 0 if audit["complete"] else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SPE-Replikation 2026")
    parser.add_argument("--language", choices=("de", "en"), default="de")
    parser.add_argument("--model", help="Explicit model ID; unavailable snapshots are never silently substituted")
    parser.add_argument("--provider", choices=("openai", "anthropic"), required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--outcomes", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--concurrent-pairs", type=int)
    parser.add_argument("--requests-per-minute", type=int)
    parser.add_argument(
        "--preflight-pairs",
        type=int,
        default=0,
        help="Nur die ersten N Paare als getrennten technischen Preflight ausführen",
    )
    parser.add_argument(
        "--pair-indices-file",
        type=Path,
        help="JSON-Datei mit eindeutigen kanonischen Paarindizes für einen Stichprobenlauf",
    )
    parser.add_argument("--execute", action="store_true", help="Kostenpflichtige API-Aufrufe erlauben")
    parser.add_argument("--confirm-requests", type=int, default=0)
    parser.add_argument("--confirm-max-api-attempts", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol = load_protocol(args.protocol.resolve())
    protocol["language"] = args.language
    protocol["outcomes"].update(protocol["instruments"][args.language])
    if args.language == "en":
        protocol["elicitation"]["user_prompt_template"] = protocol["english_prompt_template"]
    if args.model:
        protocol["providers"][args.provider]["model"] = args.model
    if protocol["elicitation"]["k_repetitions"] != 10:
        raise ProtocolError("This release requires ten repetitions per pair")
    if protocol["elicitation"].get("system_prompt") is not None:
        raise ProtocolError("This runner does not support a system prompt")
    if protocol["elicitation"].get("sampling_parameters") is not None:
        raise ProtocolError("This runner does not support sampling overrides")
    args.outcomes = resolve_outcomes_path(protocol, args.outcomes)
    processing = protocol["processing"]
    if args.concurrent_pairs is None:
        args.concurrent_pairs = int(processing["default_concurrent_pairs"])
    if args.requests_per_minute is None:
        args.requests_per_minute = int(processing["default_requests_per_minute"])
    if args.concurrent_pairs <= 0 or args.requests_per_minute <= 0:
        raise ProtocolError("Parallelität und RPM müssen positiv sein")

    outcomes, outcome_meta = load_and_validate_outcomes(args.outcomes, protocol)
    pairs = generate_pairs(outcomes)
    expected_pairs = int(protocol["outcomes"]["expected_pair_count"])
    if len(pairs) != expected_pairs:
        raise ProtocolError(f"Erwartet {expected_pairs} Paare, generiert {len(pairs)}")
    full_pair_count = len(pairs)
    if args.preflight_pairs and args.pair_indices_file:
        raise ProtocolError("--preflight-pairs und --pair-indices-file sind nicht kombinierbar")
    if args.preflight_pairs:
        if args.preflight_pairs < 1 or args.preflight_pairs > full_pair_count:
            raise ProtocolError(f"--preflight-pairs muss zwischen 1 und {full_pair_count} liegen")
        pairs = pairs[: args.preflight_pairs]
    elif args.pair_indices_file:
        selected = load_json(args.pair_indices_file.resolve())
        if not isinstance(selected, list) or not selected:
            raise ProtocolError("--pair-indices-file muss eine nicht leere JSON-Liste enthalten")
        if any(not isinstance(index, int) or isinstance(index, bool) for index in selected):
            raise ProtocolError("Alle Paarindizes müssen Ganzzahlen sein")
        if len(selected) != len(set(selected)):
            raise ProtocolError("Paarindizes müssen eindeutig sein")
        if any(index < 0 or index >= full_pair_count for index in selected):
            raise ProtocolError(f"Paarindizes müssen zwischen 0 und {full_pair_count - 1} liegen")
        pairs = [pairs[index] for index in selected]
    k = int(protocol["elicitation"]["k_repetitions"])
    total_requests = len(pairs) * k

    print("SPE-Replikation 2026")
    print(f"Provider: {args.provider}")
    print(f"Modell: {protocol['providers'][args.provider]['model']}")
    print(f"Outcomes: {len(outcomes)} (Quelldatei-Metadatum: {outcome_meta.get('n_outcomes')})")
    scope_label = "Preflight" if args.preflight_pairs else ("Stichprobe" if args.pair_indices_file else "Vollrun")
    print(f"Laufumfang: {scope_label}")
    print(f"Paare: {len(pairs):,}/{full_pair_count:,}")
    print(f"K: {k}")
    print(f"Logische Requests: {total_requests:,}")
    max_api_attempts = math.ceil(total_requests * float(protocol["processing"]["max_api_attempt_multiplier"]))
    print(f"Harte Obergrenze physischer API-Aufrufe: {max_api_attempts:,}")
    print(f"Outcome-SHA256: {protocol['outcomes']['sha256']}")
    print(f"Systemprompt: {protocol['elicitation']['system_prompt']}")
    if args.provider == "openai":
        print(f"Reasoning: {protocol['providers']['openai']['reasoning']}")
    else:
        print(f"Thinking: {protocol['providers']['anthropic'].get('thinking', 'nicht gesendet')}")

    if not args.execute:
        print("Dry-Run abgeschlossen: keine API-Aufrufe ausgeführt.")
        return 0
    if args.output_dir is None:
        raise ProtocolError("--output-dir is required")
    import fcntl
    run_path = args.output_dir.resolve()
    run_path.parent.mkdir(parents=True, exist_ok=True)
    with (run_path.parent / ("." + run_path.name + ".lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ProtocolError("Another process is using this run directory") from exc
        return asyncio.run(execute_run(args, protocol, outcomes, outcome_meta, pairs))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProtocolError as exc:
        print(f"Protokollfehler: {exc}", file=sys.stderr)
        raise SystemExit(2)
