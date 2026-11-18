import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import whatsapp_api as api

class TransactionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(api, 'DB_PATH', os.path.join(self.tmp.name, 'links.sqlite3'))
        self.db.start()
        self.user = {'username': 'teste', 'saldo': 92.5, 'total_compras': 1}
        self.loader = patch.object(api.database, 'load_user_data', return_value=self.user)
        self.loader.start()
        self.phone = '5511999999999'
        code = api.profile_code(123)['codigo']
        api.dispatch('POST', '/api/whatsapp/v1/vincular', {'whatsapp': self.phone, 'codigo': code}, lambda: [])
        self.calls = 0
        self.services = {'comprar': self.buy, 'pix': self.pix, 'status_pix': lambda u, p: {'pago': True, 'saldo': self.user['saldo']}}

    def tearDown(self):
        self.loader.stop()
        self.db.stop()
        self.tmp.cleanup()

    def buy(self, user, items):
        self.calls += 1
        self.assertEqual(user.id, 123)
        self.user['saldo'] -= items[0]['preco']
        self.user['total_compras'] += 1
        return {'saldo': self.user['saldo'], 'entregues': [{'nome': 'Produto', 'email': 'acesso', 'senha': 'segredo'}]}

    def pix(self, user, value):
        self.calls += 1
        return {'id_pag': 'pay-1', 'copia': 'fake-pix', 'valor': value, 'total': value}

    def request(self, action='comprar', op='a' * 64, **changes):
        payload = {'operacao': op, 'produto': 'Produto', 'preco': 10} if action == 'comprar' else {'operacao': op, 'valor': 10}
        payload.update(changes)
        return api.dispatch('POST', f'/api/whatsapp/v1/clientes/{self.phone}/{action}', payload, lambda: [], self.services)

    def test_same_account_and_replay(self):
        first = self.request()
        second = self.request()
        self.assertEqual(first, second)
        self.assertEqual(self.calls, 1)
        self.assertEqual(self.user['saldo'], 82.5)
        data = api.dispatch('GET', f'/api/whatsapp/v1/clientes/{self.phone}', {}, lambda: [])
        self.assertEqual(data['saldo'], 82.5)
        self.assertEqual(data['total_compras'], 2)
        operation = api.dispatch('GET', f'/api/whatsapp/v1/clientes/{self.phone}/operacoes/' + 'a' * 64, {}, lambda: [], self.services)
        self.assertEqual(operation['resultado']['entregues'][0]['senha'], 'segredo')
        with self.assertRaises(api.APIError): self.request(preco=20)

    def test_uncertain_failure_is_never_repeated_or_refunded(self):
        def lost(*args):
            self.calls += 1
            self.user['saldo'] -= 10
            raise RuntimeError('connection lost after debit')
        self.services['comprar'] = lost
        self.assertEqual(self.request()['status'], 'REVIEW')
        self.assertEqual(self.request()['status'], 'REVIEW')
        with self.assertRaises(api.APIError): self.request(op='b' * 64)
        self.assertEqual(self.calls, 1)
        self.assertEqual(self.user['saldo'], 82.5)

    def test_concurrent_duplicate_executes_only_once(self):
        entered, finish = threading.Event(), threading.Event()
        original = self.services['comprar']
        def delayed(*args):
            entered.set()
            self.assertTrue(finish.wait(5))
            return original(*args)
        self.services['comprar'] = delayed
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(self.request)
            self.assertTrue(entered.wait(5))
            self.assertEqual(self.request()['status'], 'PROCESSING')
            finish.set()
            self.assertEqual(future.result()['status'], 'DONE')
        self.assertEqual(self.calls, 1)

    def test_pix_ownership(self):
        result = self.request('pix')
        self.assertEqual(result['status'], 'DONE')
        self.request('pix')
        self.assertEqual(self.calls, 1)
        url = f'/api/whatsapp/v1/clientes/{self.phone}/pix/pay-1/status'
        self.assertTrue(api.dispatch('GET', url, {}, lambda: [], self.services)['pago'])
        with self.assertRaises(api.APIError):
            api.dispatch('GET', url.replace('pay-1', 'other-payment'), {}, lambda: [], self.services)

    def test_rejected_purchase_is_not_repeated(self):
        def insufficient(*args):
            self.calls += 1
            raise api.APIError(402, 'saldo insuficiente')
        self.services['comprar'] = insufficient
        first = self.request()
        self.assertEqual(first['status'], 'REJECTED')
        self.assertEqual(first['erro_status'], 402)
        self.assertEqual(self.request(), first)
        self.assertEqual(self.calls, 1)
        self.assertEqual(self.user['saldo'], 92.5)

    def test_operation_result_belongs_to_linked_customer(self):
        self.request()
        code = api.profile_code(456)['codigo']
        number = '5511888888888'
        api.dispatch('POST', '/api/whatsapp/v1/vincular',
                     {'codigo': code, 'whatsapp': number}, lambda: [])
        with self.assertRaises(api.APIError) as error:
            api.dispatch('GET', f'/api/whatsapp/v1/clientes/{number}/operacoes/' + 'a' * 64,
                         {}, lambda: [], self.services)
        self.assertEqual(error.exception.status, 404)

    def test_invalid_amount_unlinked_and_unavailable_callbacks(self):
        for invalid in (True, -1, float('nan'), float('inf')):
            with self.assertRaises(api.APIError): self.request(preco=invalid)
        with self.assertRaises(api.APIError):
            api.dispatch('POST', '/api/whatsapp/v1/clientes/5511888888888/comprar', {}, lambda: [], self.services)
        with self.assertRaises(api.APIError):
            api.dispatch('POST', f'/api/whatsapp/v1/clientes/{self.phone}/comprar', {}, lambda: [])
        self.assertEqual(self.calls, 0)

if __name__ == '__main__': unittest.main()
