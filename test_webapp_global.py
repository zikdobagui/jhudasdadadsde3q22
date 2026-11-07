import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import webapp
import player_api


class GlobalStoreTests(unittest.TestCase):
    def setUp(self):
        self.balance = 100.0
        def debit(uid, amount):
            self.balance -= amount
        def credit(uid, amount):
            self.balance += amount
        self.info = SimpleNamespace(saldo=lambda uid: self.balance,
                                    tirar_saldo=debit, add_saldo=credit)
        self.deliver = Mock()
        self.context = patch.dict(webapp.G, {
            'api': SimpleNamespace(InfoUser=self.info,
                CredentialsChange=SimpleNamespace(id_dono=lambda: 1)),
            'bot': Mock(), 'entregar': self.deliver}, clear=True)
        self.context.start()
        self.addCleanup(self.context.stop)
        self.user = SimpleNamespace(id=123, nome='Cliente')
        self.product = {'nome': '🌐 Microsoft Office', 'player_id': 'office-1',
                        'categoria': 'global', 'preco': 20.0, 'valor': 20.0,
                        'estoque': 3, 'descricao': 'Licença anual', 'duracao': 0}

    def buy(self, order, price=20, quantity=1):
        with patch.object(webapp, '_catalogo', return_value=[self.product]), \
             patch.object(webapp, '_manutencao'), \
             patch.object(webapp, '_fake_msg', return_value=Mock()), \
             patch.object(player_api, 'create_order', return_value=order) as create:
            result = webapp._comprar(self.user, [{'nome': self.product['nome'],
                              'qtd': quantity, 'preco': price}])
        return result, create

    def test_catalog_uses_global_source_and_sale_price(self):
        products = [{'id': 'a', 'name': 'Microsoft Office', 'source': 'global', 'stock': 7, 'price': 10},
                    {'id': 'b', 'name': 'Netflix', 'source': 'manual', 'stock': 9, 'price': 10},
                    {'id': 'c', 'name': 'Spotify', 'source': 'global', 'stock': 0, 'price': 10}]
        with patch.object(player_api, 'is_player_enabled', return_value=True), \
             patch.object(player_api, 'get_products', return_value=products), \
             patch.object(player_api, 'get_sale_price', return_value=12.5), \
             patch.object(webapp, '_img_url', return_value='/img'):
            catalog = webapp._catalogo_global()
        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]['categoria'], 'global')
        self.assertEqual(catalog[0]['subcategoria'], 'Microsoft / Office')
        self.assertEqual(catalog[0]['preco'], 12.5)
        self.assertEqual(catalog[0]['estoque'], 7)

    def test_purchase_delivers_access_and_uses_server_price(self):
        result, create = self.buy({'success': True, 'data': {'id': 'order-1',
            'credentials': {'email': 'cliente@example.test', 'password': 'test', 'profile': '2'}}})
        self.assertEqual(result['saldo'], 80)
        self.assertIn('profile: 2', result['entregues'][0]['email'])
        self.assertEqual(result['entregues'][0]['senha'], 'test')
        self.assertIn('order-1', result['entregues'][0]['descricao'])
        create.assert_called_once_with('office-1', quantity=1, user_telegram_id=123)
        self.deliver.assert_called_once()
        self.assertEqual(self.deliver.call_args.args[-1], 0)

    def test_failed_purchase_refunds_balance(self):
        result, _ = self.buy(None)
        self.assertEqual(result['saldo'], 100)
        self.assertEqual(result['entregues'], [])
        self.deliver.assert_not_called()

    def test_rejected_purchase_refunds_balance(self):
        result, _ = self.buy({'success': False})
        self.assertEqual(result['saldo'], 100)
        self.assertEqual(result['entregues'], [])

    def test_changed_price_rejected_before_purchase(self):
        with self.assertRaises(webapp.Erro):
            self.buy({'id': 'order-1'}, price=1)
        self.assertEqual(self.balance, 100)

    def test_insufficient_balance_rejected(self):
        self.balance = 5
        with self.assertRaises(webapp.Erro):
            self.buy({'id': 'order-1'})
        self.assertEqual(self.balance, 5)


if __name__ == '__main__':
    unittest.main()
