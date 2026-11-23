"""Regressões dos prêmios sem iniciar o bot ou acessar serviços externos."""
import ast
import html
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import Mock


class PremiosTests(TestCase):
    def setUp(self):
        names = {'safe_edit_message', 'mostrar_central_premios',
                 'mostrar_caixas_premios', 'mostrar_bonus_premios',
                 'mostrar_promocoes_premios', 'entregar_premio_servico'}
        tree = ast.parse(Path('bot.py').read_text(encoding='utf-8-sig'))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.bot = Mock()
        self.info = SimpleNamespace(saldo=Mock(return_value=20), tirar_saldo=Mock(), add_compra=Mock())
        self.stock = Mock(return_value=('Produto', 10, 'login', 'senha', 'Descrição', 30))
        self.env = dict(bot=self.bot, html=html,
                        api=SimpleNamespace(InfoUser=self.info, ControleLogins=SimpleNamespace(pegar_primeiro_disponivel=self.stock)),
                        database=SimpleNamespace(load_user_data=Mock(return_value={'saldo': 20})),
                        aplicar_cashback_vip=Mock(), InlineKeyboardMarkup=Mock(), InlineKeyboardButton=Mock(),
                        botao_personalizado=lambda key, default: default,
                        texto_tarefas_premios=lambda uid: 'Tarefas',
                        carregar_config_premios=lambda: {
                            'botoes': dict(caixa='Caixa', bonus='Bônus', promocoes='Promoções', cashback='VIP', voltar='Voltar'),
                            'textos': dict(menu='Prêmios', caixas='{caixas}', bonus='{tarefas}', promocoes='Promoções'),
                            'caixas': [{'nome': 'Básica', 'valor': 5}]})
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'bot.py', 'exec'), self.env)
        self.call = SimpleNamespace(id='callback', from_user=SimpleNamespace(id=1),
                                    message=SimpleNamespace(chat=SimpleNamespace(id=1), message_id=2, content_type='photo', caption='Menu'))

    def test_all_prize_menus_open_from_photo(self):
        for name in ('mostrar_central_premios', 'mostrar_caixas_premios', 'mostrar_bonus_premios', 'mostrar_promocoes_premios'):
            with self.subTest(menu=name):
                self.bot.reset_mock()
                self.env[name](self.call)
                self.bot.edit_message_caption.assert_called_once()
                self.bot.edit_message_text.assert_not_called()

    def test_purchase_records_access_and_sends_credentials(self):
        self.env['entregar_premio_servico'](self.call, 'Produto', 5, 'Caixa')
        self.info.tirar_saldo.assert_called_once_with(1, 5)
        self.info.add_compra.assert_called_once_with(1, 'Produto', 5, 'login', 'senha', duracao=30)
        self.bot.send_message.assert_called_once()
        self.assertIn('<code>login</code>', self.bot.send_message.call_args.args[1])
        self.assertIn('<code>senha</code>', self.bot.send_message.call_args.args[1])

    def test_insufficient_balance_does_not_reserve_or_charge(self):
        self.info.saldo.return_value = 0
        self.env['entregar_premio_servico'](self.call, 'Produto', 5, 'Caixa')
        self.stock.assert_not_called()
        self.info.tirar_saldo.assert_not_called()
        self.bot.send_message.assert_not_called()

    def test_empty_stock_does_not_charge(self):
        self.stock.return_value = None
        self.env['entregar_premio_servico'](self.call, 'Produto', 5, 'Caixa')
        self.info.tirar_saldo.assert_not_called()
        self.info.add_compra.assert_not_called()


if __name__ == '__main__':
    main()
