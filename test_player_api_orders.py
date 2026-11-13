import unittest
from unittest.mock import Mock, patch
import requests
import player_api


class PlayerOrderApiTests(unittest.TestCase):
    def setUp(self):
        for target, value in [('is_player_enabled', True), ('get_headers', {'Authorization': 'Bearer test'})]:
            p = patch.object(player_api, target, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.post = patch.object(player_api.requests, 'post').start()
        self.get = patch.object(player_api.requests, 'get').start()
        self.addCleanup(patch.stopall)
        self.post.return_value = Mock(status_code=200)
        self.post.return_value.json.return_value = {
            'success': True, 'order_id': 'ord-test', 'status': 'delivered'}
        self.get.return_value = Mock(status_code=200, text='Email: user@test\nSenha: example')

    def test_purchase_endpoint_idempotency_and_txt_delivery(self):
        order = player_api.create_order('product-1', user_telegram_id=123)
        self.assertTrue(self.post.call_args.args[0].endswith('/purchase'))
        payload = self.post.call_args.kwargs['json']
        self.assertEqual(payload['product_id'], 'product-1')
        self.assertTrue(payload['external_order_id'].startswith('telegram-123-'))
        self.assertNotIn('customer_id', payload)
        self.assertEqual(order['id'], 'ord-test')
        self.assertIn('Email: user@test', order['credentials']['acesso'])
        self.assertTrue(self.get.call_args.args[0].endswith('/orders/ord-test/download'))

    def test_rejected_purchase_logs_http_reason_without_credentials(self):
        self.post.return_value.status_code = 402
        with patch('builtins.print') as output:
            self.assertIsNone(player_api.create_order('product-1'))
        self.assertIn('HTTP 402', str(output.call_args))
        self.assertIn('saldo do revendedor insuficiente', str(output.call_args))
        self.assertNotIn('Bearer test', str(output.call_args))
        self.get.assert_not_called()

    def test_download_failure_preserves_paid_order(self):
        self.get.side_effect = requests.Timeout()
        order = player_api.create_order('product-1')
        self.assertEqual(order['id'], 'ord-test')
        self.post.assert_called_once()

    def test_pending_delivery_preserves_order_without_downloading(self):
        self.post.return_value.json.return_value['status'] = 'awaiting_delivery'
        self.assertEqual(player_api.create_order('product-1')['id'], 'ord-test')
        self.get.assert_not_called()

    def test_post_timeout_logs_reference_without_retrying(self):
        self.post.side_effect = requests.Timeout()
        with patch('builtins.print') as output:
            self.assertIsNone(player_api.create_order('product-1'))
        self.assertIn('Timeout', str(output.call_args))
        self.assertIn('referência=', str(output.call_args))
        self.post.assert_called_once()
        self.get.assert_not_called()

    def test_success_false_is_rejected(self):
        self.post.return_value.json.return_value = {'success': False}
        self.assertIsNone(player_api.create_order('product-1'))
        self.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
