"""Testa o menu sem importar bot.py, que inicia serviços externos."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import Mock


class CatalogMessageTests(TestCase):
    def setUp(self):
        tree = ast.parse(Path('bot.py').read_text(encoding='utf-8-sig'))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('safe_edit_message', 'servicos')]
        self.bot = Mock()
        self.markup = Mock()
        api = SimpleNamespace(
            ControleLogins=SimpleNamespace(pegar_servicos=lambda: []),
            Botoes=SimpleNamespace(voltar=lambda: 'Voltar'),
            Textos=SimpleNamespace(menu_comprar=lambda msg: 'Catálogo'))
        self.env = {'bot': self.bot, 'api': api,
                    'InlineKeyboardMarkup': lambda: self.markup,
                    'InlineKeyboardButton': Mock()}
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'bot.py', 'exec'), self.env)

    def open_catalog(self, content_type='text', caption=None):
        message = SimpleNamespace(chat=SimpleNamespace(id=1), message_id=2,
                                  content_type=content_type, caption=caption)
        self.env['servicos'](message)

    def test_photo_edits_caption(self):
        self.open_catalog('photo', 'Menu')
        self.bot.edit_message_caption.assert_called_once_with(
            chat_id=1, message_id=2, caption='Catálogo', parse_mode='HTML',
            reply_markup=self.markup)
        self.bot.edit_message_text.assert_not_called()

    def test_animation_without_caption_edits_caption(self):
        self.open_catalog('animation')
        self.bot.edit_message_caption.assert_called_once()
        self.bot.edit_message_text.assert_not_called()

    def test_text_edits_text(self):
        self.open_catalog()
        self.bot.edit_message_text.assert_called_once()
        self.bot.edit_message_caption.assert_not_called()

    def test_failed_edit_sends_catalog(self):
        self.bot.edit_message_caption.side_effect = RuntimeError('cannot edit')
        self.open_catalog('photo')
        self.bot.send_message.assert_called_once_with(
            chat_id=1, text='Catálogo', parse_mode='HTML', reply_markup=self.markup)

    def test_unchanged_message_does_not_duplicate_catalog(self):
        self.bot.edit_message_text.side_effect = RuntimeError('message is not modified')
        self.open_catalog()
        self.bot.send_message.assert_not_called()


if __name__ == '__main__':
    main()
