import os
import tempfile
import unittest
from unittest.mock import patch

import whatsapp_api as api


class WhatsAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(api, 'DB_PATH', os.path.join(self.tmp.name, 'links.sqlite3'))
        self.db.start()
        self.user = {'username': 'teste', 'saldo': 23.4, 'compras': [
            {'servico': 'Produto', 'valor': 10, 'senha': 'secreto', 'email': 'privado'}]}
        self.loader = patch.object(api.database, 'load_user_data', return_value=self.user)
        self.loader.start()

    def tearDown(self):
        self.loader.stop()
        self.db.stop()
        self.tmp.cleanup()

    def link(self, uid=123, number='5511999999999'):
        code = api.profile_code(uid)['codigo']
        return code, api.dispatch('POST', '/api/whatsapp/v1/vincular',
                                  {'codigo': code, 'whatsapp': number}, lambda: [])

    def test_link_live_balance_history_and_no_reuse(self):
        code = api.profile_code(123)['codigo']
        self.assertEqual(code, api.profile_code(123)['codigo'])
        self.link()
        self.assertTrue(api.profile_code(123)['vinculado'])
        self.assertIsNone(api.profile_code(123)['codigo'])
        self.user['saldo'] = 99
        data = api.dispatch('GET', '/api/whatsapp/v1/clientes/5511999999999', {}, lambda: [])
        self.assertEqual(data['saldo'], 99)
        history = api.dispatch('GET', '/api/whatsapp/v1/clientes/5511999999999/historico', {}, lambda: [])
        self.assertNotIn('senha', history['compras'][0])
        self.assertNotIn('email', history['compras'][0])
        with self.assertRaises(api.APIError) as error:
            api.dispatch('POST', '/api/whatsapp/v1/vincular', {'codigo': code, 'whatsapp': '5511888888888'}, lambda: [])
        self.assertEqual(error.exception.status, 409)

    def test_expiration_and_unique_number(self):
        code, _ = self.link()
        code2 = api.profile_code(456)['codigo']
        with self.assertRaises(api.APIError):
            api.dispatch('POST', '/api/whatsapp/v1/vincular', {'codigo': code2, 'whatsapp': '5511999999999'}, lambda: [])
        with api.connect() as con:
            con.execute('UPDATE links SET expires=0 WHERE user_id=?', ('456',))
        with self.assertRaises(api.APIError):
            api.dispatch('POST', '/api/whatsapp/v1/vincular', {'codigo': code2, 'whatsapp': '5511888888888'}, lambda: [])
        self.assertNotEqual(code2, api.profile_code(456)['codigo'])

    def test_catalog_whitelist(self):
        result = api.dispatch('GET', '/api/whatsapp/v1/produtos', {},
                              lambda: [{'nome': 'P', 'preco': 12, 'estoque': 2, 'senha': 'segredo'}])
        self.assertEqual(result['produtos'][0]['preco'], 12)
        self.assertNotIn('senha', result['produtos'][0])


if __name__ == '__main__':
    unittest.main()
