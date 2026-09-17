"""Offline contract and integration checks for Chat Completions endpoints."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_run_spe import run_spe
from aiohttp import web

ROOT = Path(__file__).resolve().parents[1]


def configure(*extra):
    args = run_spe.parse_args(['--provider', 'compatible', '--model', 'local-model',
                              '--base-url', 'http://localhost:11434/v1', *extra])
    protocol = run_spe.load_protocol(ROOT / 'tools/protocol.json')
    run_spe.configure_provider(args, protocol)
    return args, protocol


class CompatibleTests(unittest.TestCase):
    def test_payload_auth_and_response_metadata(self):
        _, protocol = configure('--no-auth')
        adapter = run_spe.ProviderAdapter('compatible', protocol['providers']['compatible'], '', None)
        self.assertEqual(adapter.payload('pick', 32), {'model': 'local-model', 'messages': [{'role': 'user', 'content': 'pick'}], 'max_tokens': 32})
        self.assertNotIn('Authorization', adapter.headers())
        adapter.api_key = 'synthetic-test-key'
        self.assertEqual(adapter.headers()['Authorization'], 'Bearer synthetic-test-key')
        parsed = adapter.parse({'id': '1', 'model': 'returned-model', 'choices': [{'message': {'content': 'B'}, 'finish_reason': 'stop'}], 'usage': {'completion_tokens': 1}})
        self.assertEqual(parsed['raw_text'], 'B')
        self.assertEqual(parsed['returned_model'], 'returned-model')
        self.assertEqual(parsed['stop_reason'], 'stop')
        self.assertEqual(parsed['usage'], {'completion_tokens': 1})
        for response in ({}, {'choices': []}, {'choices': [{'message': {'content': None, 'reasoning': 'A'}}]}):
            self.assertEqual(adapter.parse(response)['raw_text'], '')

    def test_endpoint_configuration_rejects_credentials_and_remote_plaintext(self):
        for url in ['https://user:secret@example.org/v1', 'https://example.org/v1?key=secret', 'http://example.org/v1', 'file:///tmp/model']:
            with self.subTest(url=url), self.assertRaises(run_spe.ProtocolError):
                configure('--base-url', url)
        with self.assertRaises(run_spe.ProtocolError):
            configure('--base-url', 'https://example.org/v1', '--no-auth')
        with self.assertRaises(run_spe.ProtocolError):
            configure('--api-key-env', 'not a variable')
        _, protocol = configure('--base-url', 'https://example.org/v1/', '--api-key-env', 'CUSTOM_API_KEY')
        self.assertEqual(protocol['providers']['compatible']['endpoint'], 'https://example.org/v1/chat/completions')

    def test_dry_run_never_contacts_endpoint(self):
        with patch.object(run_spe.ProviderAdapter, 'request', side_effect=AssertionError('network')):
            self.assertEqual(run_spe.main(['--provider', 'compatible', '--model', 'mock', '--base-url', 'http://localhost:11434/v1', '--no-auth', '--max-output-tokens', '128']), 0)


class CompatibleHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def test_letter_balance_resume_and_endpoint_guard(self):
        calls = []
        async def handle(request):
            self.assertNotIn('Authorization', request.headers)
            payload = await request.json()
            calls.append(payload)
            # An invalid output exercises retry handling, then persistent letter A.
            return web.json_response({'model': 'local-model', 'choices': [{'message': {'content': '?' if len(calls) == 1 else 'A'}, 'finish_reason': 'stop'}], 'usage': {'completion_tokens': 1}})
        app = web.Application()
        app.router.add_post('/v1/chat/completions', handle)
        server = web.AppRunner(app)
        await server.setup()
        site = web.TCPSite(server, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            with tempfile.TemporaryDirectory() as d:
                args, protocol = configure('--base-url', f'http://127.0.0.1:{port}/v1', '--no-auth', '--output-dir', str(Path(d) / 'run'), '--preflight-pairs', '1', '--confirm-requests', '10', '--confirm-max-api-attempts', '12')
                args.outcomes = ROOT / 'instrument/outcomes.de.json'
                args.requests_per_minute = 100000
                args.concurrent_pairs = 1
                outcomes, meta = run_spe.load_and_validate_outcomes(args.outcomes, protocol)
                pairs = run_spe.generate_pairs(outcomes)[:1]
                self.assertEqual(await run_spe.execute_run(args, protocol, outcomes, meta, pairs), 0)
                self.assertEqual(len(calls), 11)
                self.assertEqual(await run_spe.execute_run(args, protocol, outcomes, meta, pairs), 0)
                self.assertEqual(len(calls), 11)
                preferences = json.loads((args.output_dir / 'preferences.json').read_text())
                self.assertEqual(list(preferences['preferences'].values()), [.5])
                audit = json.loads((args.output_dir / 'audit.json').read_text())
                self.assertTrue(audit['complete'])
                self.assertIsNone(audit['expected_service_tier'])
                altered = copy.deepcopy(protocol)
                altered['providers']['compatible']['endpoint'] += '/changed'
                with self.assertRaises(run_spe.ProtocolError):
                    await run_spe.execute_run(args, altered, outcomes, meta, pairs)
                self.assertEqual(len(calls), 11)
        finally:
            await server.cleanup()

    async def test_redirect_does_not_forward_key(self):
        seen = []
        async def redirect(request):
            raise web.HTTPTemporaryRedirect('/destination')
        async def destination(request):
            seen.append(True)
            return web.json_response({})
        app = web.Application()
        app.router.add_post('/v1/chat/completions', redirect)
        app.router.add_post('/destination', destination)
        server = web.AppRunner(app)
        await server.setup()
        site = web.TCPSite(server, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                adapter = run_spe.ProviderAdapter('compatible', {'model': 'mock', 'endpoint': f'http://127.0.0.1:{port}/v1/chat/completions'}, 'synthetic-key', session)
                with self.assertRaises(run_spe.ApiRequestError):
                    await adapter.request('pick', 16)
            self.assertEqual(seen, [])
        finally:
            await server.cleanup()
