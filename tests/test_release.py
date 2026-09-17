import asyncio,copy,hashlib,importlib.util,json,math,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import run_spe
# analyze imports the local statistics module.
import analyze
from statistics import exact_transitivity

class AnalysisTests(unittest.TestCase):
    def setUp(self):self.instrument={'outcomes':[{'id':x} for x in ['a','b','c']]}
    def test_known_order(self):
        result=analyze.analyze({'preferences':{'a|b':.8,'b|c':.8,'a|c':.95}},self.instrument)
        u=result['thurstone']['utilities'];self.assertGreater(u['a'],u['b']);self.assertGreater(u['b'],u['c'])
        self.assertAlmostEqual(sum(u.values()),0);self.assertEqual(result['coherence']['transitivity_rate'],1)
    def test_ties_have_no_directional_accuracy(self):
        result=analyze.analyze({'preferences':{'a|b':.5,'b|c':.5,'a|c':.5}},self.instrument)
        self.assertIsNone(result['thurstone']['direction_accuracy_excluding_ties']);self.assertIsNone(result['coherence']['transitivity_rate'])
        json.dumps(result,allow_nan=False)
    def test_missing_edge_is_not_imputed(self):
        result=analyze.analyze({'preferences':{'a|b':.8,'b|c':.8}},self.instrument)
        self.assertEqual(result['n_complete_pairs'],2);self.assertEqual(result['coherence']['evaluable_strict_majority_triplets'],0)
    def test_cycle(self):
        self.assertEqual(exact_transitivity({'a|b':.8,'b|c':.8,'a|c':.2},['a','b','c'])['intransitive_cycles'],1)
    def test_reversed_pair_normalization(self):
        a=analyze.analyze({'preferences':{'a|b':.8,'b|c':.8,'a|c':.95}},self.instrument)
        b=analyze.analyze({'preferences':{'b|a':.2,'b|c':.8,'a|c':.95}},self.instrument)
        self.assertEqual(a['thurstone']['utilities'],b['thurstone']['utilities'])
    def test_bad_inputs(self):
        for pref in [{'a|b':float('nan')},{'a|a':.5},{'a|b':2},{'a|b':.2,'b|a':.8},{'a|z':.3}]:
            with self.assertRaises(ValueError):analyze.analyze({'preferences':pref},self.instrument)
        with self.assertRaises(ValueError):analyze.analyze({'preferences':{'a|b':.8,'c|d':.8}},{'outcomes':[{'id':x} for x in 'abcd']})

class ReleaseTests(unittest.TestCase):
    def test_both_language_dry_runs_never_execute(self):
        for lang in ['de','en']:
            with patch.object(run_spe,'execute_run',side_effect=AssertionError('network execution')):
                self.assertEqual(run_spe.main(['--provider','openai','--language',lang]),0)
    def test_language_model_protocol_resume_guards(self):
        protocol=run_spe.load_protocol(ROOT/'tools/protocol.json')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run'
            def create(p):return run_spe.create_or_validate_run_manifest(out,p,ROOT/'tools/protocol.json',ROOT/'instrument/outcomes.de.json',{},'openai',2,20,300,2,'preflight',[0,1],24)
            first=create(protocol);self.assertEqual(first['run_identity'],create(protocol)['run_identity'])
            for field in ['language','model','retry']:
                p=copy.deepcopy(protocol)
                if field=='language':p['language']='en'
                elif field=='model':p['providers']['openai']['model']='another'
                else:p['processing']['invalid_response_retries']=1
                with self.assertRaises(run_spe.ProtocolError):create(p)
    def test_nondecision_not_counted_as_b(self):
        pair=run_spe.Pair(0,run_spe.Outcome('a','A'),run_spe.Outcome('b','B'))
        rows=[{'pair_index':0,'canonical_choice':'A'},{'pair_index':0,'canonical_choice':None}]
        result=run_spe.build_aggregate(rows,[pair],2,{'provider_config':{'model':'mock'},'provider':'openai','run_identity':'mock'})
        self.assertEqual(result['preferences'],{});self.assertEqual(result['meta']['incomplete_pair_indices'],[0])
    def test_instrument_hash_guard(self):
        p=run_spe.load_protocol(ROOT/'tools/protocol.json')
        with self.assertRaises(run_spe.ProtocolError):run_spe.load_and_validate_outcomes(ROOT/'instrument/outcomes.en.json',p)

class ResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistent_attempt_ceiling(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'budget.json';b=run_spe.AttemptBudget(path,2);await b.reserve();await b.reserve()
            b=run_spe.AttemptBudget(path,2)
            with self.assertRaises(run_spe.AttemptBudgetExceeded):await b.reserve()
    async def test_invalid_retry_limit_survives_restart(self):
        class Adapter:
            config={'model':'mock'}
            async def request(self,*args):raise AssertionError('retry limit must survive restart')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);store=run_spe.JsonlStore(root)
            await store.append_attempt({'logical_id':'p00000-r00','kind':'invalid_model_output'})
            store=run_spe.JsonlStore(root)
            pair=run_spe.Pair(0,run_spe.Outcome('a','A'),run_spe.Outcome('b','B'))
            result=await run_spe.run_logical_request(Adapter(),run_spe.RateLimiter(100000),run_spe.AttemptBudget(root/'budget.json',3),store,run_spe.logical_requests(pair,1)[0],'{outcome_a} {outcome_b}',16,0,0)
            self.assertIsNone(result['canonical_choice']);self.assertEqual(len(store.completed()),1)

if __name__=='__main__':unittest.main()

class CrashRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_logged_attempt_is_recovered_without_network(self):
        class Adapter:
            config={'model':'mock'}
            async def request(self,*args):raise AssertionError('must recover, not call again')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);store=run_spe.JsonlStore(root)
            await store.append_attempt({'logical_id':'p00000-r01','kind':'valid','normalized_choice':'A','raw_text':'A'})
            store=run_spe.JsonlStore(root);budget=run_spe.AttemptBudget(root/'budget.json',3)
            pair=run_spe.Pair(0,run_spe.Outcome('a','A'),run_spe.Outcome('b','B'))
            result=await run_spe.run_logical_request(Adapter(),run_spe.RateLimiter(100000),budget,store,run_spe.logical_requests(pair,2)[1],'{outcome_a} {outcome_b}',16,0,0)
            self.assertEqual(result['canonical_choice'],'B');self.assertEqual(budget.current,0)

class EndToEndTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_http_collection_resume_and_analysis(self):
        from aiohttp import web
        calls=[]
        async def handle(request):
            data=await request.json();calls.append(data)
            return web.json_response({'id':str(len(calls)), 'model':'mock-model','status':'completed','service_tier':'default',
                'output':[{'type':'message','content':[{'type':'output_text','text':'invalid' if len(calls)==1 else 'A'}]}], 'usage':{'input_tokens':1,'output_tokens':1}})
        app=web.Application();app.router.add_post('/responses',handle);server=web.AppRunner(app);await server.setup()
        site=web.TCPSite(server,'127.0.0.1',0);await site.start();port=site._server.sockets[0].getsockname()[1]
        try:
            with tempfile.TemporaryDirectory() as temp:
                temp=Path(temp);protocol=run_spe.load_protocol(ROOT/'tools/protocol.json');protocol['providers']['openai']['endpoint']=f'http://127.0.0.1:{port}/responses';protocol['providers']['openai']['model']='mock-model';protocol['processing']['default_requests_per_minute']=100000
                path=temp/'protocol.json';path.write_text(json.dumps(protocol));outcomes,meta=run_spe.load_and_validate_outcomes(ROOT/'instrument/outcomes.de.json',protocol);pairs=run_spe.generate_pairs(outcomes)[:1]
                args=run_spe.parse_args(['--provider','openai','--protocol',str(path),'--output-dir',str(temp/'run'),'--preflight-pairs','1','--confirm-requests','10','--confirm-max-api-attempts','12'])
                args.outcomes=ROOT/'instrument/outcomes.de.json';args.requests_per_minute=100000;args.concurrent_pairs=1
                with patch.dict('os.environ',{'OPENAI_API_KEY':'synthetic-local-test'}):
                    self.assertEqual(await run_spe.execute_run(args,protocol,outcomes,meta,pairs),0)
                    count=len(calls);self.assertEqual(count,11)
                    self.assertEqual(await run_spe.execute_run(args,protocol,outcomes,meta,pairs),0)
                    self.assertEqual(len(calls),count)
                pref=json.loads((temp/'run/preferences.json').read_text());self.assertEqual(list(pref['preferences'].values()),[.5])
                result=analyze.analyze(pref,json.loads((ROOT/'instrument/outcomes.de.json').read_text()));self.assertEqual(result['n_analyzed_outcomes'],2)
                self.assertIsNone(result['thurstone']['direction_accuracy_excluding_ties'])
        finally:await server.cleanup()
