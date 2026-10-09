"""Exercise access checks without starting the production bot or its workers."""
import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class ReserveAccessTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path(__file__).with_name('bot.py').read_text(encoding='utf-8-sig'))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('reserve_group_username', 'is_user_in_reserve_group')]
        self.bot = Mock()
        self.url = 'https://t.me/current_channel'
        self.env = {'re': re, 'bot': self.bot,
                    'reserve_group_url': lambda: self.url,
                    'reserve_group_id': lambda: -1001234567890}
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'bot.py', 'exec'), self.env)

    def check(self, status, **fields):
        self.bot.get_chat_member.return_value = SimpleNamespace(status=status, **fields)
        return self.env['is_user_in_reserve_group'](42)

    def test_public_channel_overrides_old_group_id(self):
        self.assertTrue(self.check('member'))
        self.bot.get_chat_member.assert_called_once_with('@current_channel', 42)

    def test_nonmembers_and_unknown_status_are_denied(self):
        for status in ('left', 'kicked', None, 'unknown'):
            with self.subTest(status=status):
                self.assertFalse(self.check(status))

    def test_member_roles(self):
        for status in ('member', 'administrator', 'creator'):
            self.assertTrue(self.check(status))
        self.assertTrue(self.check('restricted', is_member=True))
        self.assertFalse(self.check('restricted', is_member=False))
        self.assertFalse(self.check('restricted'))

    def test_private_invites_use_numeric_id(self):
        for url in ('https://t.me/+secret', 'https://t.me/joinchat/secret'):
            self.url = url
            self.assertTrue(self.check('member'))
            self.bot.get_chat_member.assert_called_with(-1001234567890, 42)

    def test_public_link_formats(self):
        for url in ('@current_channel', 'https://t.me/current_channel',
                    'https://t.me/s/current_channel', 'https://telegram.me/current_channel/?x=1'):
            self.url = url
            self.assertEqual(self.env['reserve_group_username'](), '@current_channel')

    def test_query_errors_do_not_fall_back_to_old_group(self):
        self.bot.get_chat_member.side_effect = RuntimeError('not enough rights')
        with self.assertRaises(RuntimeError):
            self.env['is_user_in_reserve_group'](42)
        self.bot.get_chat_member.assert_called_once_with('@current_channel', 42)


if __name__ == '__main__':
    unittest.main()
