#!/usr/bin/env python3
"""Analyze one run's complete pairs; missing choices are never assigned to B."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from statistics import exact_transitivity, fit_thurstone, outcome_scores


def analyze(payload, instrument):
    rows = instrument['outcomes']; ids = [r['id'] for r in rows]; order = {x:i for i,x in enumerate(ids)}
    preferences = {}
    for key, value in payload['preferences'].items():
        parts = key.split('|')
        if len(parts) != 2 or any(x not in order for x in parts) or parts[0] == parts[1]:
            raise ValueError(f'Invalid pair: {key}')
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f'Invalid probability: {key}')
        a,b=parts
        if order[a] > order[b]:a,b,value=b,a,1-value
        canonical=f'{a}|{b}'
        if canonical in preferences:raise ValueError(f'Duplicate unordered pair: {key}')
        preferences[canonical]=value
    if not preferences:raise ValueError('No complete pairs to analyze')
    active = {x for key in preferences for x in key.split('|')}
    used = [x for x in ids if x in active]
    # A disconnected graph does not identify one common utility scale.
    reached={used[0]}
    while True:
        expanded=reached | {x for k in preferences if reached.intersection(k.split('|')) for x in k.split('|')}
        if expanded == reached:break
        reached=expanded
    if reached != active:raise ValueError('Disconnected comparison graph; analyze connected components separately')
    keys=sorted(preferences); values=list(preferences.values())
    fit=fit_thurstone(preferences,keys,used)
    if not fit['converged']:raise ValueError('Thurstone optimization did not converge: '+fit['message'])
    scores=outcome_scores(preferences,keys,used)
    return {'meta':payload.get('meta',{}),'n_complete_pairs':len(keys),'n_instrument_outcomes':len(ids),
            'n_analyzed_outcomes':len(used),'excluded_outcome_ids':[x for x in ids if x not in active],
            'tie_rate':sum(x==.5 for x in values)/len(values),
            'clear_rate':sum(x>.7 or x<.3 for x in values)/len(values),
            'thurstone':fit,'coherence':exact_transitivity(preferences,used),'win_scores':scores,
            'definitions':{'fit':'Equal-weight complete pairs; sigma=1; mean utility=0; in-sample directional accuracy excludes observed 5:5 ties.','coherence':'All triples with three observed strict majorities; ties and missing edges excluded.','win_scores':'Mean observed win probability against available opponents.','limits':'Relative preference, not pedagogical quality. Sparse samples and separated preferences may yield unstable utility magnitudes.'}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--language',choices=['de','en'],default='de');p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();root=Path(__file__).resolve().parents[1]
    f=root/f'instrument/outcomes.{a.language}.json';raw=f.read_bytes();instrument=json.loads(raw)
    payload=json.loads(a.input.read_text());meta=payload.get('meta',{})
    if meta.get('language',a.language)!=a.language:raise ValueError('Language mismatch')
    if meta.get('outcomes_sha256') and meta['outcomes_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('Instrument hash mismatch')
    result=analyze(payload,instrument)
    result['input_sha256']=hashlib.sha256(a.input.read_bytes()).hexdigest();result['instrument_sha256']=hashlib.sha256(raw).hexdigest()
    a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    with (a.output_dir/'utilities.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['rank','id','utility','mean_win_probability'])
        for rank,(oid,u) in enumerate(sorted(result['thurstone']['utilities'].items(),key=lambda x:-x[1]),1):w.writerow([rank,oid,u,result['win_scores'][oid]])
    print(f"Analyzed {result['n_complete_pairs']} complete pairs; results: {a.output_dir}")

if __name__=='__main__':main()
