#!/usr/bin/env python3
"""Freeze a context-specific instrument and balanced SPE protocol (offline)."""
import argparse
import copy
import hashlib
import json
import re
import string
from pathlib import Path
from run_spe import DEFAULT_PROTOCOL, ProtocolError, load_protocol


def validate_instrument(payload):
    rows = payload.get('outcomes') if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) < 2:
        raise ProtocolError('Provide at least two action descriptions in an outcomes list')
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip() for k in ('id', 'text')):
            raise ProtocolError('Every action needs a nonempty string id and text')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', row['id']):
            raise ProtocolError('IDs must use letters, digits, dots, underscores or hyphens; no spaces or |')
        for field in ('dimension', 'item'):
            if field in row and (not isinstance(row[field], str) or not row[field].strip()):
                raise ProtocolError(f'{field} must be a nonempty string when supplied')
    for field in ('id', 'text'):
        if len({r[field].strip() for r in rows}) != len(rows):
            raise ProtocolError(f'Duplicate {field}')
    return rows


def prepare(input_path, output_dir, language, title, repetitions=10, prompt=None):
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 2 or repetitions % 2:
        raise ProtocolError('Repetitions must be a positive even integer (at least 2) for balanced A/B order')
    if not language.strip() or not title.strip():
        raise ProtocolError('Language and study title are required')
    payload = json.loads(input_path.read_text(encoding='utf-8'))
    rows = validate_instrument(payload)
    if prompt is None:
        if language not in ('de', 'en'):
            raise ProtocolError('Provide --prompt-file for languages other than de/en')
        prompt = ('Welche der folgenden Handlungen würdest du bevorzugen?\n\nOption A: {outcome_a}\n\nOption B: {outcome_b}\n\nAntworte nur mit A oder B.' if language == 'de' else
                  'Which of the following actions would you prefer?\n\nOption A: {outcome_a}\n\nOption B: {outcome_b}\n\nRespond only with A or B.')
    try:
        fields = [field for _, field, spec, conversion in string.Formatter().parse(prompt) if field is not None]
        if set(fields) != {'outcome_a', 'outcome_b'} or len(fields) != 2:
            raise ValueError('Use {outcome_a} and {outcome_b} exactly once each')
        prompt.format(outcome_a='A action', outcome_b='B action')
    except (ValueError, KeyError, IndexError, AttributeError) as exc:
        raise ProtocolError(f'Invalid prompt: {exc}') from exc
    instrument = {'meta': {'title': title, 'language': language, 'instrument_version': '1.0.0',
                           'n_outcomes': len(rows), 'condition': 'custom-context'}, 'outcomes': rows}
    raw = (json.dumps(instrument, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    protocol = copy.deepcopy(load_protocol(DEFAULT_PROTOCOL))
    protocol.pop('instruments'); protocol.pop('english_prompt_template'); protocol.pop('frozen_at', None)
    protocol.update(protocol_version='1.1.0', description=title, language=language, path_base='protocol')
    protocol['outcomes'] = {'relative_path': 'instrument.json', 'sha256': hashlib.sha256(raw).hexdigest(),
                            'expected_count': len(rows), 'expected_pair_count': len(rows)*(len(rows)-1)//2}
    protocol['elicitation'].update(k_repetitions=repetitions, user_prompt_template=prompt)
    # Refuse to replace an existing condition, even when only one artifact exists.
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir/'instrument.json').write_bytes(raw)
    (output_dir/'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return protocol


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--language', default='en')
    p.add_argument('--title', required=True)
    p.add_argument('--repetitions', type=int, default=10)
    p.add_argument('--prompt-file', type=Path)
    a = p.parse_args()
    try:
        protocol = prepare(a.input, a.output_dir, a.language, a.title, a.repetitions,
                           a.prompt_file.read_text(encoding='utf-8') if a.prompt_file else None)
    except (ProtocolError, FileExistsError) as exc:
        p.error(str(exc))
    n = protocol['outcomes']['expected_count']; pairs = protocol['outcomes']['expected_pair_count']
    print(f'Prepared {n} actions, {pairs} pairs, {pairs*a.repetitions} decisions. No API calls.')
    print(f'Protocol: {a.output_dir / "protocol.json"}')


if __name__ == '__main__':
    main()
