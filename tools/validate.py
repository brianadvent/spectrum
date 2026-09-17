#!/usr/bin/env python3
"""Validate both released language versions, hashes, dimensions and CSV parity."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from math import comb


def main():
    root=Path(__file__).resolve().parents[1]
    p=json.loads((root/'tools/protocol.json').read_text());versions={}
    for lang in ['de','en']:
        info=p['instruments'][lang];f=root/info['relative_path'];raw=f.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==info['sha256'],f'Hash mismatch: {lang}'
        d=json.loads(raw);rows=d['outcomes'];ids=[x['id'] for x in rows]
        assert len(rows)==len(set(ids))==144
        assert d['meta']['language']==lang
        assert len(set(x['text'] for x in rows))==144
        assert set(Counter(x['item'] for x in rows).values())=={3}
        assert len(set(x['item'] for x in rows))==48
        assert len(set(x['dimension'] for x in rows))==8
        assert all(x['text'].strip() and x['dimension']==x['id'].split('_')[0] and x['item']=='v_'+x['id'].split('_')[1][1:] for x in rows)
        with (root/f'instrument/outcomes.{lang}.csv').open() as f:assert list(csv.DictReader(f))==rows
        assert comb(len(rows),2)==10296
        versions[lang]=[(x['id'],x['item'],x['dimension']) for x in rows]
    assert versions['de']==versions['en']
    print('Validated DE and EN: 144 aligned IDs, 48 principles, 8 dimensions, 10,296 pairs; hashes and CSV parity passed.')
if __name__=='__main__':main()
