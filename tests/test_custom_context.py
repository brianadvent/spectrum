import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import prepare
import run_spe


class CustomContextTests(unittest.TestCase):
    def test_portable_custom_dry_run_and_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); study = root / 'study'
            protocol = prepare.prepare(ROOT / 'examples/team-decisions.json', study, 'en', 'Team decisions', 4)
            self.assertEqual(protocol['outcomes']['expected_pair_count'], 6)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), patch.object(run_spe, 'execute_run', side_effect=AssertionError('Network')):
                self.assertEqual(run_spe.main(['--provider', 'openai', '--protocol', str(study/'protocol.json')]), 0)
            self.assertIn('Logische Requests: 24', out.getvalue())
            instrument_path = run_spe.resolve_outcomes_path(protocol, None, study/'protocol.json')
            outcomes, meta = run_spe.load_and_validate_outcomes(instrument_path, protocol)
            rows = []
            for pair in run_spe.generate_pairs(outcomes):
                reqs = run_spe.logical_requests(pair, 4)
                self.assertEqual([r.order for r in reqs], ['canonical', 'reversed']*2)
                # Synthetic displayed A produces an equal-count tie after back-coding.
                rows.extend({'pair_index': pair.index, 'canonical_choice': r.canonical_choice('A')} for r in reqs)
            manifest = {'provider_config': {'model': 'synthetic'}, 'provider': 'openai', 'run_identity': 'test',
                        'language': 'en', 'outcomes_sha256': protocol['outcomes']['sha256']}
            aggregate = run_spe.build_aggregate(rows, run_spe.generate_pairs(outcomes), 4, manifest)
            self.assertEqual(set(aggregate['preferences'].values()), {.5})
            preferences = root/'preferences.json'; preferences.write_text(json.dumps(aggregate))
            command = [sys.executable, str(ROOT/'tools/analyze.py'), '--input', str(preferences),
                       '--instrument', str(instrument_path), '--output-dir', str(root/'analysis')]
            subprocess.run(command, check=True, capture_output=True, cwd=root)
            result = json.loads((root/'analysis/analysis.json').read_text())
            self.assertEqual(result['n_analyzed_outcomes'], 4)
            self.assertEqual(result['tie_rate'], 1)
            instrument = json.loads(instrument_path.read_text()); instrument['outcomes'][0]['text'] += ' Changed'
            instrument_path.write_text(json.dumps(instrument))
            self.assertNotEqual(subprocess.run(command, capture_output=True, cwd=root).returncode, 0)
            with self.assertRaises(run_spe.ProtocolError):
                run_spe.main(['--provider', 'openai', '--protocol', str(study/'protocol.json')])

    def test_language_condition_and_output_guards(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)/'study'; source = ROOT/'examples/team-decisions.json'
            prepare.prepare(source, target, 'en', 'Example')
            with self.assertRaises(FileExistsError):prepare.prepare(source, target, 'en', 'Replacement')
            with self.assertRaises(run_spe.ProtocolError):
                run_spe.main(['--provider', 'anthropic', '--protocol', str(target/'protocol.json'), '--language', 'de'])

    def test_invalid_custom_inputs(self):
        valid = json.loads((ROOT/'examples/team-decisions.json').read_text())
        for field, value in [('id', 'contains|separator'), ('id', ''), ('text', None), ('dimension', 3)]:
            data = copy.deepcopy(valid); data['outcomes'][0][field] = value
            with self.assertRaises(run_spe.ProtocolError):prepare.validate_instrument(data)
        data=copy.deepcopy(valid);data['outcomes'][1]['id']=data['outcomes'][0]['id']
        with self.assertRaises(run_spe.ProtocolError):prepare.validate_instrument(data)
        with tempfile.TemporaryDirectory() as d:
            for k in [0, 3, -2, True]:
                with self.assertRaises(run_spe.ProtocolError):
                    prepare.prepare(ROOT/'examples/team-decisions.json', Path(d)/'study', 'en', 'Title', k)
            for prompt in ['No actions here', '{outcome_a} {outcome_c}', '{outcome_a} {outcome_b} {outcome_b}']:
                with self.assertRaises(run_spe.ProtocolError):
                    prepare.prepare(ROOT/'examples/team-decisions.json', Path(d)/'study', 'en', 'Title', prompt=prompt)

if __name__ == '__main__':unittest.main()
