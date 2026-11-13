import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import player_handlers


class GlobalBotPurchaseTests(unittest.TestCase):
    def setUp(self):
        self.bot = Mock()
        self.handlers = {}
        def register(**filters):
            def decorator(fn):
                self.handlers[fn.__name__] = fn
                return fn
            return decorator
        self.bot.callback_query_handler.side_effect = register
        self.info = Mock()
        self.info.saldo.return_value = 100.0
        self.followup = Mock()
        player_handlers.registrar_handlers(self.bot, SimpleNamespace(InfoUser=self.info),
                                          self.followup, lambda uid: 'Cliente', lambda: 99)
        self.call = SimpleNamespace(id='callback', data='player_buy:office',
            from_user=SimpleNamespace(id=123),
            message=SimpleNamespace(chat=SimpleNamespace(id=123), message_id=7))

    def buy(self, order, inline=False, balance=100):
        self.info.saldo.return_value = balance
        if inline:
            self.call.message = None
        with patch.object(player_handlers.player_api, 'get_product_details',
                          return_value={'name': 'Office <Global>', 'price': 20}), \
             patch.object(player_handlers.player_api, 'get_sale_price', return_value=20), \
             patch.object(player_handlers.player_api, 'create_order', return_value=order) as create, \
             patch.object(player_handlers.database, 'load_user_data', return_value={'saldo': 80}) , \
             patch.object(player_handlers.database, 'save_user_data') as save:
            self.handlers['comprar_produto_player'](self.call)
        return create, save

    def test_current_response_delivers_and_records_credentials(self):
        _, save = self.buy({'success': True, 'data': {'id': 'order-1',
            'credentials': {'email': 'user@test', 'password': '<secret&>', 'license': 'key-1'}}})
        self.info.tirar_saldo.assert_called_once_with(123, 20)
        purchase = save.call_args.args[1]['compras'][0]
        self.assertEqual(purchase['order_id'], 'order-1')
        self.assertEqual(purchase['senha'], '<secret&>')
        text = self.bot.edit_message_text.call_args.kwargs['text']
        self.assertIn('&lt;secret&amp;&gt;', text)
        self.assertIn('key-1', text)
        self.assertIn('Office &lt;Global&gt;', text)

    def test_rejection_does_not_charge_and_shows_error_in_chat(self):
        _, save = self.buy({'success': False, 'message': 'unavailable'})
        self.info.tirar_saldo.assert_not_called()
        save.assert_not_called()
        self.assertIn('saldo', self.bot.edit_message_text.call_args.kwargs['text'])
        self.bot.answer_callback_query.assert_called_once()

    def test_network_failure_does_not_charge(self):
        self.buy(None)
        self.info.tirar_saldo.assert_not_called()
        self.bot.edit_message_text.assert_called_once()

    def test_insufficient_funds_does_not_order(self):
        create, _ = self.buy(None, balance=5)
        create.assert_not_called()
        self.info.tirar_saldo.assert_not_called()
        self.assertIn('Saldo Insuficiente', self.bot.edit_message_text.call_args.kwargs['text'])

    def test_inline_purchase_delivers_privately(self):
        self.buy({'id': 'order-2', 'credentials': 'license-value'}, inline=True)
        self.info.tirar_saldo.assert_called_once_with(123, 20)
        delivery = self.bot.send_message.call_args_list[0]
        self.assertEqual(delivery.args[0], 123)
        self.assertIn('license-value', delivery.args[1])
        self.bot.edit_message_text.assert_not_called()

    def test_invalid_response_does_not_charge(self):
        self.buy({'success': True, 'data': None})
        self.info.tirar_saldo.assert_not_called()


if __name__ == '__main__':
    unittest.main()
