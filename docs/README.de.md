# SPEctrum – SPE im eigenen Kontext einsetzen

Welche Handlungen priorisiert ein Sprachmodell? SPEctrum hilft, diese Frage für einen eigenen Anwendungsbereich zu untersuchen: Handlungsbeschreibungen entwickeln, paarweise Entscheidungen erheben und eine relative Präferenzstruktur auswerten.

Der enthaltene Bildungsdatensatz umfasst 144 Handlungsbeschreibungen zu 48 Prinzipien aus einer Delphi-Studie über KI in der Bildung. Er enthält sowohl konsentierte Prinzipien als auch Prinzipien mit fortbestehendem Dissens. Die deutschen Originaltexte und englischen Übersetzungen stehen als JSON und CSV bereit. Für andere Kontexte kannst du eigene Beschreibungen verwenden. Die Forschungsresultate stehen im [SPE Explorer](https://spe-explorer.autenrieth-partner.de).

## Kostenlos beginnen

Python ab 3.12 und uv unter macOS/Linux beziehungsweise Windows mit WSL:

```sh
git clone https://github.com/brianadvent/spectrum.git
cd spectrum
uv sync --frozen
uv run python tools/prepare.py --input examples/team-decisions.json \
  --output-dir studies/team-decisions --title "Teamentscheidungen" --language en
uv run python tools/run_spe.py --provider openai \
  --protocol studies/team-decisions/protocol.json --model YOUR_MODEL_ID
```

Das Beispiel enthält vier englische Handlungsbeschreibungen: sechs Paare mit je zehn Wiederholungen. Diese Befehle führen keine Modellaufrufe aus. Eigene JSON-Dateien benötigen je Handlung eine eindeutige `id` und einen `text`; `dimension` und `item` sind optional. `--language de` wählt für eigene deutsche Texte eine neutrale deutsche Fragestellung. Eine eigene Kontextfrage lässt sich mit `--prompt-file` ergänzen.

Der [Leitfaden zur Übertragung](your-context.md) erklärt Instrumententwicklung, Pilotierung und Reichweite.

## Erheben und auswerten

Die [Hauptanleitung](../README.md) enthält vollständige Befehle. Echte Erhebungen benötigen `--execute`, einen API-Schlüssel und ausdrücklich bestätigte Anfragebudgets. A/B wird balanciert, jeder Versuch protokolliert, unterbrochene Läufe lassen sich fortsetzen. Modell, Sprache, Instrumenthash und Protokoll verhindern eine versehentliche Mischung von Bedingungen.

```sh
uv run python tools/analyze.py --input runs/team-decisions/preferences.json \
  --instrument studies/team-decisions/instrument.json --output-dir results/team-decisions
```

Utilities beschreiben relative Priorisierung innerhalb des Instruments. Sie sind keine absoluten Qualitätswerte. Nichtentscheidungen werden nicht imputiert; Gleichstände werden in gerichteten Kennzahlen entsprechend behandelt. Details stehen in der [Methodendokumentation](protocol.md).

## Pädagogisches Instrument verwenden

```sh
uv run python tools/validate.py
uv run python tools/run_spe.py --provider openai
uv run python tools/run_spe.py --provider anthropic --language en
```

Deutsch ist das Originalprotokoll: 48 Prinzipien, 144 Beschreibungen, 10.296 Paare, zehn Wiederholungen. Englisch ist eine redaktionell geprüfte eigene Sprachbedingung ohne belegte Messäquivalenz. JSON und CSV liegen unter `instrument/`.

## Weitere Modelle

Neben OpenAI und Anthropic unterstützt der Runner Chat-Completions-kompatible APIs, etwa Gemini oder einen lokalen Ollama-Server. Modell und Basis-URL werden ausdrücklich angegeben. Die [Hauptanleitung](../README.md#other-models-and-local-servers) enthält Befehle und unterstützte API-Felder.

## Lizenzen

- Code, Tests und CI: [MIT](../LICENSE).
- Bildungsdatensatz, Beispielinstrumente und Dokumentation: [CC BY 4.0](../LICENSE-DATA).

Copyright © 2026 Daniel Autenrieth. Die vollständigen Lizenztexte liegen im Repository; die Zuordnung zu Dateien steht in [REUSE.toml](../REUSE.toml). Bei Nachnutzung des Datensatzes Daniel Autenrieth nennen, Repository und Lizenz verlinken und Änderungen kennzeichnen. Zitierinformationen: [CITATION.cff](../CITATION.cff).
