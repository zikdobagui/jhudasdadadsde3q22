import unittest
from unittest.mock import Mock, patch

import api_catalogo
import central


class ApiSaleNotificationsTests(unittest.TestCase):
    def setUp(self):
        self.access = {
            'nome': 'Produto <teste>', 'valor': 10, 'email': 'login',
            'senha': 'segredo', 'descricao': 'Descrição',
            'reserved_by': {'reseller_admin_id': '999', 'buyer_id': '456'},
        }

    def notify(self, bot):
        with patch('telebot.TeleBot', return_value=bot), \
             patch.object(central.CredentialsChange, 'token_bot', return_value='token'), \
             patch.object(central.CredentialsChange, 'id_dono', return_value=1), \
             patch.object(central.CredentialsChange, 'user_bot', return_value='atual_bot'), \
             patch.object(central.Notificacoes, 'id_grupo', return_value=-100), \
             patch.object(api_catalogo.database, 'load_user_data', return_value={
                 'username': 'comprador', 'saldo': 25,
             }) as load:
            api_catalogo.notificar_venda_api(self.access, '123')
            load.assert_called_once_with('123')

    def test_admin_identifies_key_owner_and_channel_has_no_secrets_or_photo(self):
        bot = Mock()
        self.notify(bot)
        self.assertEqual(bot.send_message.call_count, 2)
        admin, channel = bot.send_message.call_args_list
        self.assertEqual(admin.args[0], 1)
        for text in ('@comprador', '123', 'API / Key', '456', '25.00'):
            self.assertIn(text, admin.args[1])
        self.assertEqual(channel.args[0], -100)
        self.assertIn('Produto &lt;teste&gt;', channel.args[1])
        self.assertNotIn('segredo', channel.args[1])
        self.assertNotIn('API / Key', channel.args[1])
        markup = channel.kwargs['reply_markup'].to_dict()
        self.assertEqual(markup['inline_keyboard'][0][0]['url'], 'https://t.me/atual_bot')
        bot.send_photo.assert_not_called()

    def test_admin_failure_does_not_prevent_channel_notification(self):
        bot = Mock()
        bot.send_message.side_effect = [RuntimeError('unavailable'), None]
        self.notify(bot)
        self.assertEqual(bot.send_message.call_count, 2)

    def request(self, success=True, notify_error=None):
        handler = object.__new__(api_catalogo.Handler)
        handler.path = '/api/stock/reserve'
        handler.headers = {}
        handler.client_address = ('127.0.0.1', 1234)
        handler._autorizado = Mock(return_value='123')
        handler._ler_json = Mock(return_value={'service': 'Produto', 'reseller_admin_id': '999'})
        handler._responder_json = Mock()
        result = (True, 'reserved', self.access) if success else (False, 'out_of_stock', None)
        with patch.object(api_catalogo, '_rate_limited', return_value=False), \
             patch.object(api_catalogo, 'reservar_primeiro_acesso', return_value=result) as reserve, \
             patch.object(api_catalogo, 'notificar_venda_api', side_effect=notify_error) as notify:
            handler.do_POST()
            self.assertEqual(reserve.call_args.args[-1], '123')
            if success:
                notify.assert_called_once_with(self.access, '123')
                handler._responder_json.assert_called_once_with(200, {'access': self.access})
            else:
                notify.assert_not_called()
                handler._responder_json.assert_called_once_with(404, {'error': 'out_of_stock'})

    def test_successful_purchase_notifies(self):
        self.request()

    def test_failed_purchase_does_not_notify(self):
        self.request(success=False)

    def test_notification_failure_does_not_fail_completed_purchase(self):
        self.request(notify_error=RuntimeError('unavailable'))


if __name__ == '__main__':
    unittest.main()
