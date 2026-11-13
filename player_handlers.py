"""
Handlers para o sistema de Contas Globais (Player API)
"""

import datetime
import html
import json
import os
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import player_api
import player_categories
import database


# IDs de emojis premium para Contas Globais
PLAYER_PREMIUM_EMOJIS = {
    'globe': '5447410659077661506',        # 🌍 Globo
    'sparkles': '5370784581341422520',     # ✨ Estrela/Brilho
    'warning': '5447644880824181073',      # ⚠️ Aviso
    'blue_circle': '5350486389806868244',  # 🔵 Círculo azul
    'green_circle': '5350693961281314631', # 🟢 Círculo verde
    'red_circle': '5350710934992069206',   # 🔴 Círculo vermelho
    'arrow_right': '5370784581341422520',  # ▶️ Seta
    'search': '5210956306952758910',       # 🔍 Lupa
    'refresh': '5229064374403998351',      # 🔄 Atualizar
    'back': '5447644880824181073',         # 🔙 Voltar
    'cart': '5229064374403998351',         # 🛒 Carrinho
    'money': '5456140674028019486',        # 💰 Dinheiro
    'fire': '5370784581341422520',         # 🔥 Fogo
    'check': '5350486389806868244',        # ✅ Check
    'home': '5447410659077661506',         # 🏠 Casa
    'package': '5231200819986047254',      # 📦 Pacote
    'email': '5210956306952758910',        # 📧 Email
    'lock': '5440660757194744323',         # 🔒 Cadeado
}

PRODUCT_THUMBNAILS = {
    'netflix': 'https://cdn.icon-icons.com/icons2/2699/PNG/512/netflix_logo_icon_170919.png',
    'spotify': 'https://cdn.icon-icons.com/icons2/2699/PNG/512/spotify_logo_icon_170919.png',
    'chatgpt': 'https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg',
    'canva': 'https://cdn.icon-icons.com/icons2/3504/PNG/512/canva_icon_220714.png',
    'crunchyroll': 'https://cdn.icon-icons.com/icons2/3132/PNG/512/crunchyroll_social_network_network_connection_communication_icon_192251.png',
    'prime': 'https://cdn.icon-icons.com/icons2/2699/PNG/512/amazon_prime_logo_icon_170916.png',
    'capcut': 'https://www.moneytimes.com.br/uploads/2024/01/mt-capcut-2-1024x576.jpg',
}
DEFAULT_THUMBNAIL = 'https://cdn.icon-icons.com/icons2/72/PNG/256/unknown_alert_14463.png'
STANDARD_EMOJI_PATTERN = re.compile(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+')


def strip_standard_emojis(text) -> str:
    """Remove emojis comuns do texto (o botão mostra só o ícone premium)."""
    cleaned = STANDARD_EMOJI_PATTERN.sub(' ', str(text or ''))
    return ' '.join(cleaned.split())


def custom_emoji(emoji_id: str, fallback: str) -> str:
    """Cria tag de emoji premium"""
    emoji_id = str(emoji_id).strip()
    return f'<tg-emoji emoji-id="{html.escape(emoji_id)}">{html.escape(str(fallback))}</tg-emoji>'


def display_name(value: str) -> str:
    """Remove emojis comuns vindos da API; o ícone do botão é premium."""
    return STANDARD_EMOJI_PATTERN.sub('', str(value)).strip() or 'Produto'


def product_premium_emoji(product_name: str, in_stock: bool) -> str:
    """Ícone premium do serviço (compatibilidade); usa o status como reserva."""
    return service_emoji_id_for(product_name) or (
        PLAYER_PREMIUM_EMOJIS['green_circle' if in_stock else 'red_circle']
    )


def service_emoji_id_for(product_name: str) -> str:
    """ID premium do serviço, casando nome sem acento e por palavra inteira.

    Antes a comparação era um `in` simples do casefold, então chaves curtas
    como 'SKY' casavam dentro de 'dashboard' e aplicavam o ícone errado.
    """
    try:
        with open(os.path.join('settings', 'credenciais.json'), 'r', encoding='utf-8-sig') as file:
            emoji_map = json.load(file).get('service_emoji_map', {})
    except (OSError, ValueError, TypeError):
        emoji_map = {}
    if not isinstance(emoji_map, dict):
        emoji_map = {}
    try:
        with open(os.path.join('settings', 'player_service_emojis.json'), 'r', encoding='utf-8-sig') as file:
            defaults = json.load(file)
        if isinstance(defaults, dict):
            emoji_map = {**defaults, **emoji_map}
    except (OSError, ValueError, TypeError):
        pass

    normalized_name = player_categories._normalize(product_name)
    if not normalized_name:
        return ''

    best_id, best_len = '', 0
    for service, emoji_id in emoji_map.items():
        key = player_categories._normalize(service)
        emoji_id = str(emoji_id).strip()
        if not key or not emoji_id.isdigit():
            continue
        if re.search(rf'(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])', normalized_name):
            if len(key) > best_len:
                best_id, best_len = emoji_id, len(key)
    return best_id


def product_thumbnail(product_name: str) -> str:
    normalized_name = str(product_name).casefold()
    for service, url in PRODUCT_THUMBNAILS.items():
        if service in normalized_name:
            return url
    return DEFAULT_THUMBNAIL


def build_inline_search_results(types_module, term: str):
    """Monta resultados inline do catálogo Player para a busca do bot."""
    normalized_term = str(term or '').casefold().strip()
    if not normalized_term:
        return []

    results = []
    for product in player_api.get_products() or []:
        name = str(product.get('name', 'Produto'))
        visible_name = display_name(name)
        if normalized_term not in name.casefold():
            continue

        product_id = str(product.get('id', ''))
        if not product_id:
            continue
        price = player_api.get_sale_price(product.get('price', 0))
        stock = int(product.get('stock') or 0)
        description = player_api.product_description(product) or 'Descrição não informada pelo fornecedor.'
        availability = 'Disponível' if stock > 0 else 'Esgotado'
        globe = custom_emoji(PLAYER_PREMIUM_EMOJIS['globe'], '🌍')
        money = custom_emoji(PLAYER_PREMIUM_EMOJIS['money'], '💰')
        package = custom_emoji(PLAYER_PREMIUM_EMOJIS['package'], '📦')
        check = custom_emoji(PLAYER_PREMIUM_EMOJIS['check'], '✅')
        note = custom_emoji(PLAYER_PREMIUM_EMOJIS['sparkles'], '✨')
        cart = custom_emoji(PLAYER_PREMIUM_EMOJIS['cart'], '🛒')
        text = (
            f"{globe} <b>Conta Global: {html.escape(visible_name)}</b>\n"
            f"{money} <b>Valor:</b> R$ {price:.2f}\n"
            f"{package} <b>Estoque:</b> {stock}\n"
            f"{check} <b>Status:</b> {availability}\n\n"
            f"{note} {html.escape(description)}\n\n"
            f"{cart} <i>Entrega automática no chat após a compra.</i>"
        )
        keyboard = types_module.InlineKeyboardMarkup()
        if stock > 0:
            buy_button = types_module.InlineKeyboardButton(
                f'Comprar R${price:.2f}', callback_data=f'player_buy:{product_id}'
            )
            buy_button.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['cart']
            keyboard.row(buy_button)
        cancel_button = types_module.InlineKeyboardButton('Cancelar', callback_data='cancelarInline')
        cancel_button.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['back']
        keyboard.row(cancel_button)
        results.append(types_module.InlineQueryResultArticle(
            id=f'player-{product_id}',
            title=visible_name,
            description=f'R$ {price:.2f} · estoque {stock}',
            input_message_content=types_module.InputTextMessageContent(text, parse_mode='HTML'),
            reply_markup=keyboard,
            thumbnail_url=product_thumbnail(name),
        ))
        if len(results) >= 25:
            break
    return results


def registrar_handlers(bot, api, cancelar_followup, _build_personal_mention, get_sales_notification_chat_id):
    """
    Registra os handlers de contas globais no bot
    
    Args:
        bot: Instância do bot
        api: Módulo central de API
        cancelar_followup: Função para cancelar follow-up
        _build_personal_mention: Função para mencionar usuário
        get_sales_notification_chat_id: Função para pegar ID do grupo de vendas
    """
    
    @bot.callback_query_handler(func=lambda c: c.data == 'contas_globais_menu' or c.data.startswith('contas_globais_page:'))
    def menu_contas_globais(call):
        """Menu principal de Contas Globais - Lista todos os produtos paginados"""
        bot.answer_callback_query(call.id)
        
        # Detecta a página (compatibilidade com links antigos contas_globais_page:)
        page = 0
        if call.data.startswith('contas_globais_page:'):
            try:
                page = int(call.data.split(':')[1])
            except:
                page = 0
        
        if not player_api.is_player_enabled():
            globe = custom_emoji(PLAYER_PREMIUM_EMOJIS['globe'], '🌍')
            warning = custom_emoji(PLAYER_PREMIUM_EMOJIS['warning'], '⚠️')
            
            texto = (
                f"{globe} <b>CONTAS GLOBAIS</b>\n\n"
                f"{warning} A integração com o Player está desativada no momento.\n\n"
                "Entre em contato com o suporte para mais informações."
            )
            markup = InlineKeyboardMarkup()
            back_btn = InlineKeyboardButton('Voltar', callback_data='menu_start')
            back_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['back']
            markup.add(back_btn)
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=texto,
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except:
                bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
            return
        
        # Busca produtos da API Player
        products = player_api.get_products()
        
        if not products:
            globe = custom_emoji(PLAYER_PREMIUM_EMOJIS['globe'], '🌍')
            warning = custom_emoji(PLAYER_PREMIUM_EMOJIS['warning'], '⚠️')
            
            texto = (
                f"{globe} <b>CONTAS GLOBAIS</b>\n\n"
                f"{warning} Não foi possível carregar os produtos no momento.\n"
                "Tente novamente mais tarde."
            )
            markup = InlineKeyboardMarkup()
            
            retry_btn = InlineKeyboardButton('Tentar Novamente', callback_data='contas_globais_menu')
            retry_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['refresh']
            markup.add(retry_btn)
            
            back_btn = InlineKeyboardButton('Voltar', callback_data='menu_start')
            back_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['back']
            markup.add(back_btn)
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=texto,
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except:
                bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
            return
        
        # Produtos organizados por serviço (só as origens permitidas em
        # settings/player_categories.json: por padrão, apenas 'global')
        categorias = player_categories.category_summary(products)
        produtos_no_menu = [item for itens in player_categories.group_products(products).values()
                            for item in itens]
        total_items = len(produtos_no_menu)
        em_estoque = sum(1 for p in produtos_no_menu if int(p.get('stock') or 0) > 0)
        unidades = sum(max(0, int(p.get('stock') or 0)) for p in produtos_no_menu)
        
        # Emojis premium para o cabeçalho
        sparkles = custom_emoji(PLAYER_PREMIUM_EMOJIS['sparkles'], '✨')
        globe = custom_emoji(PLAYER_PREMIUM_EMOJIS['globe'], '🌍')
        warning = custom_emoji(PLAYER_PREMIUM_EMOJIS['warning'], '⚠️')
        green_circle = custom_emoji(PLAYER_PREMIUM_EMOJIS['green_circle'], '🟢')
        red_circle = custom_emoji(PLAYER_PREMIUM_EMOJIS['red_circle'], '🔴')
        
        # Monta o cabeçalho
        texto = (
            f"{sparkles} <b>CONTAS GLOBAIS</b>\n"
            f"{total_items} produtos · {em_estoque} com estoque · {unidades} unidades\n"
            "Organizados por serviço — "
            "entrega automática pelo seu saldo.\n\n"
            f"{warning} <b>Antes de comprar, LEIA as informações do produto</b> (toque no item pra ver detalhes, garantia e como ativar).\n\n"
            f"{green_circle} Em estoque   {red_circle} Esgotado\n\n"
            f"{globe} Escolha um serviço:"
        )
        
        markup = InlineKeyboardMarkup(row_width=1)
        
        # Um botão por categoria; os produtos abrem dentro dela.
        # O texto vai SEM emoji: o ícone animado entra por icon_custom_emoji_id,
        # senão o Telegram mostra o premium e o padrão juntos.
        total_pages = max(1, (len(categorias) + 11) // 12)
        page = max(0, min(page, total_pages - 1))
        for resumo in categorias[page * 12:(page + 1) * 12]:
            botao_categoria = InlineKeyboardButton(
                f"{resumo['category']} › {resumo['count']} produtos",
                callback_data=f"player_cat:{resumo['slug']}"
            )
            botao_categoria.icon_custom_emoji_id = (
                service_emoji_id_for(resumo['category']) or resumo.get('premium_emoji_id')
                or PLAYER_PREMIUM_EMOJIS['green_circle' if resumo['in_stock'] > 0 else 'red_circle']
            )
            markup.add(botao_categoria)
        
        if total_pages > 1:
            navigation = []
            if page > 0:
                previous = InlineKeyboardButton('Anterior', callback_data=f'contas_globais_page:{page - 1}')
                previous.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['back']
                navigation.append(previous)
            navigation.append(InlineKeyboardButton(f'{page + 1}/{total_pages}', callback_data='noop'))
            if page + 1 < total_pages:
                following = InlineKeyboardButton('Próximo', callback_data=f'contas_globais_page:{page + 1}')
                following.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['arrow_right']
                navigation.append(following)
            markup.row(*navigation)

        # Botão de pesquisa
        search_btn = InlineKeyboardButton(
            'Pesquisar produto', switch_inline_query_current_chat='buscar_loguin '
        )
        search_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['search']
        markup.add(search_btn)
        
        # Rodapé
        refresh_btn = InlineKeyboardButton('Atualizar', callback_data='contas_globais_menu')
        refresh_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['refresh']
        
        back_btn = InlineKeyboardButton('Voltar ao menu', callback_data='menu_start')
        back_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['back']
        
        markup.row(refresh_btn, back_btn)
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
    
    
    def _abrir_categoria(call, slug_categoria, page=0):
        """Lista os produtos de uma categoria, paginados."""
        products = player_api.get_products() or []
        categoria = player_categories.resolve_category(slug_categoria, products)
        
        globe = custom_emoji(PLAYER_PREMIUM_EMOJIS['globe'], '🌍')
        warning = custom_emoji(PLAYER_PREMIUM_EMOJIS['warning'], '⚠️')
        green_circle = custom_emoji(PLAYER_PREMIUM_EMOJIS['green_circle'], '🟢')
        red_circle = custom_emoji(PLAYER_PREMIUM_EMOJIS['red_circle'], '🔴')
        arrow_right = custom_emoji(PLAYER_PREMIUM_EMOJIS['arrow_right'], '▶️')
        
        if not categoria:
            texto = (
                f"{globe} <b>CONTAS GLOBAIS</b>\n\n"
                f"{warning} Categoria não encontrada — o catálogo pode ter sido atualizado.\n"
                "Volte e escolha novamente."
            )
            markup = InlineKeyboardMarkup()
            back_btn = InlineKeyboardButton('Voltar às categorias', callback_data='contas_globais_menu')
            back_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['back']
            markup.add(back_btn)
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=texto, parse_mode='HTML', reply_markup=markup
                )
            except:
                bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
            return
        
        items = player_categories.group_products(products).get(categoria, [])
        items_per_page = 12
        total_items = len(items)
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
        page = max(0, min(page, total_pages - 1))
        start_idx = page * items_per_page
        page_products = items[start_idx:start_idx + items_per_page]
        em_estoque = sum(1 for p in items if int(p.get('stock') or 0) > 0)
        unidades = sum(max(0, int(p.get('stock') or 0)) for p in items)
        
        texto = (
            f"{player_categories.category_emoji(categoria)} <b>{html.escape(categoria.upper())}</b>"
            f" (pág. {page + 1}/{total_pages})\n"            f"{total_items} produtos · {em_estoque} com estoque · {unidades} unidades\n\n"
            f"{green_circle} Em estoque   {red_circle} Esgotado\n"
            f"{arrow_right} para ver mais produtos\n\n"
            f"{globe} Escolha o produto:"
        )
        
        markup = InlineKeyboardMarkup(row_width=1)
        for product in page_products:
            product_id = product.get('id', '')
            name = str(product.get('name', 'Produto'))
            visible_name = display_name(name)
            price = player_api.get_sale_price(product.get('price', 0))
            stock = int(product.get('stock') or 0)
            button = InlineKeyboardButton(
                f"{strip_standard_emojis(visible_name)} — R${price:.2f} · {stock} un.",
                callback_data=f'player_prod:{product_id}'
            )
            button.icon_custom_emoji_id = product_premium_emoji(name, stock > 0)
            markup.add(button)
        
        # Navegação entre páginas dentro da categoria
        nav_buttons = []
        if page > 0:
            prev_btn = InlineKeyboardButton('Anterior', callback_data=f'player_cat:{slug_categoria}:{page - 1}')
            prev_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['back']
            nav_buttons.append(prev_btn)
        page_info_btn = InlineKeyboardButton(f'· {page + 1}/{total_pages} ·', callback_data='noop')
        nav_buttons.append(page_info_btn)
        if page < total_pages - 1:
            next_btn = InlineKeyboardButton('Próximo', callback_data=f'player_cat:{slug_categoria}:{page + 1}')
            next_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['arrow_right']
            nav_buttons.append(next_btn)
        if nav_buttons:
            markup.row(*nav_buttons)
        
        refresh_btn = InlineKeyboardButton('Atualizar', callback_data=f'player_cat:{slug_categoria}:{page}')
        refresh_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['refresh']
        back_btn = InlineKeyboardButton('Categorias', callback_data='contas_globais_menu')
        back_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['back']
        markup.row(refresh_btn, back_btn)
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto, parse_mode='HTML', reply_markup=markup
            )
        except:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
    
    
    @bot.callback_query_handler(func=lambda c: c.data == 'player_search')
    def player_search_handler(call):
        """Handler para pesquisa de produtos (placeholder)"""
        bot.answer_callback_query(call.id, "🔍 Pesquisa em desenvolvimento", show_alert=True)
    
    
    @bot.callback_query_handler(func=lambda c: c.data == 'noop')
    def noop_handler(call):
        """Handler vazio para botões informativos"""
        bot.answer_callback_query(call.id)
    
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith('player_cat:'))
    def menu_player_categoria(call):
        """Lista os produtos da categoria escolhida em Contas Globais"""
        bot.answer_callback_query(call.id)
        parts = call.data.split(':')
        slug_categoria = parts[1] if len(parts) > 1 else ''
        try:
            page = int(parts[2]) if len(parts) > 2 else 0
        except ValueError:
            page = 0
        _abrir_categoria(call, slug_categoria, page)
    
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith('player_prod:'))
    def detalhes_produto_player(call):
        """Mostra detalhes de um produto específico"""
        bot.answer_callback_query(call.id)
        
        product_id = call.data.replace('player_prod:', '')
        product = player_api.get_product_details(product_id)
        
        if not product:
            bot.answer_callback_query(call.id, "Produto não encontrado", show_alert=True)
            return
        
        # Formata com emojis premium
        globe = custom_emoji(PLAYER_PREMIUM_EMOJIS['globe'], '🌍')
        money = custom_emoji(PLAYER_PREMIUM_EMOJIS['money'], '💰')
        package = custom_emoji(PLAYER_PREMIUM_EMOJIS['package'], '📦')
        warning = custom_emoji(PLAYER_PREMIUM_EMOJIS['warning'], '⚠️')
        check = custom_emoji(PLAYER_PREMIUM_EMOJIS['check'], '✅')
        
        name = display_name(product.get('name', 'Produto'))
        price = player_api.get_sale_price(product.get('price', 0))
        description = player_api.product_description(product) or 'Descrição não informada pelo fornecedor.'
        stock = int(product.get('stock') or 0)
        
        texto = f"{globe} <b>{html.escape(name)}</b>\n"
        texto += f"{money} Preço: R$ {price:.2f}\n"
        
        if description:
            note = custom_emoji(PLAYER_PREMIUM_EMOJIS['sparkles'], '✨')
            texto += f"\n{note} <b>Descrição do fornecedor:</b>\n{html.escape(description)}\n"
        
        if stock > 0:
            texto += f"\n{package} Estoque: {stock} disponível(is)\n"
            texto += f"{check} <b>Produto disponível para compra!</b>"
        else:
            texto += f"\n{warning} <b>Sem estoque no momento</b>"
        
        markup = InlineKeyboardMarkup()
        
        if stock > 0:
            buy_btn = InlineKeyboardButton('Comprar Agora', callback_data=f'player_buy:{product_id}')
            buy_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['cart']
            markup.add(buy_btn)
        
        # Volta para a categoria de onde o produto veio
        categoria_produto = player_categories.product_group(product)
        back_btn = InlineKeyboardButton(
            'Voltar', callback_data=f"player_cat:{player_categories.slug(categoria_produto)}"
        )
        back_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['back']
        markup.add(back_btn)
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
    
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith('player_buy:'))
    def comprar_produto_player(call):
        """Processa a compra de um produto Player"""
        # Compras pela busca inline não têm call.message; entrega no privado.
        chat_id = call.message.chat.id if call.message else call.from_user.id

        def mostrar(texto, markup=None):
            if call.message:
                try:
                    bot.edit_message_text(
                        chat_id=chat_id, message_id=call.message.message_id,
                        text=texto, parse_mode='HTML', reply_markup=markup
                    )
                    return
                except Exception:
                    pass
            bot.send_message(chat_id, texto, parse_mode='HTML', reply_markup=markup)

        try:
            bot.answer_callback_query(call.id, "Processando compra...")
        except Exception:
            pass
        
        product_id = call.data.replace('player_buy:', '')
        product = player_api.get_product_details(product_id)
        
        if not product:
            mostrar("Produto indisponível no momento. Volte ao catálogo e tente novamente.")
            return
        
        price = player_api.get_sale_price(product.get('price', 0))
        user_balance = api.InfoUser.saldo(call.from_user.id)
        
        # Emojis premium
        money = custom_emoji(PLAYER_PREMIUM_EMOJIS['money'], '💰')
        warning = custom_emoji(PLAYER_PREMIUM_EMOJIS['warning'], '⚠️')
        
        if user_balance < price:
            texto = (
                f"{money} <b>Saldo Insuficiente</b>\n\n"
                f"Produto: {html.escape(str(product.get('name', 'Produto')))}\n"
                f"Preço: R$ {price:.2f}\n"
                f"Seu saldo: R$ {user_balance:.2f}\n"
                f"Faltam: R$ {price - user_balance:.2f}\n\n"
                f"{warning} Adicione saldo para continuar."
            )
            
            markup = InlineKeyboardMarkup()
            
            add_money_btn = InlineKeyboardButton('Adicionar Saldo', callback_data='addsaldo')
            add_money_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['money']
            markup.add(add_money_btn)
            
            back_btn = InlineKeyboardButton('Voltar', callback_data=f'player_prod:{product_id}')
            back_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['back']
            markup.add(back_btn)
            
            mostrar(texto, markup)
            return
        
        # Cria o pedido na API Player
        order = player_api.create_order(product_id, quantity=1, user_telegram_id=call.from_user.id)
        
        if not isinstance(order, dict) or order.get('success') is False:
            mostrar("Não foi possível concluir a compra com o fornecedor. Seu saldo não foi descontado. Tente novamente mais tarde ou fale com o suporte.")
            return
        order = order.get('data', order)
        if not isinstance(order, dict) or not order:
            mostrar("O fornecedor retornou um pedido inválido. Seu saldo não foi descontado. Entre em contato com o suporte.")
            return
        credentials = order.get('credentials') or {}
        if not isinstance(credentials, dict):
            credentials = {'acesso': credentials}
        
        # Desconta o saldo do usuário
        api.InfoUser.tirar_saldo(call.from_user.id, price)
        
        # Registra a compra
        user_data = database.load_user_data(call.from_user.id)
        if not user_data:
            user_data = {'compras': []}
        
        if 'compras' not in user_data:
            user_data['compras'] = []
        
        compra_data = {
            'servico': product.get('name', 'Conta Global'),
            'email': credentials.get('email', credentials.get('login', 'N/A')),
            'senha': credentials.get('password', credentials.get('senha', 'N/A')),
            'preco': price,
            'data': datetime.datetime.now().isoformat(),
            'order_id': order.get('id', ''),
            'credentials': credentials,
            'tipo': 'player_global'
        }
        
        user_data['compras'].append(compra_data)
        user_data['total_compras'] = user_data.get('total_compras', 0) + 1
        database.save_user_data(call.from_user.id, user_data)
        
        # Cancela follow-up
        cancelar_followup(call.from_user.id)
        
        # Emojis premium para mensagem de sucesso
        check = custom_emoji(PLAYER_PREMIUM_EMOJIS['check'], '✅')
        globe = custom_emoji(PLAYER_PREMIUM_EMOJIS['globe'], '🌍')
        money = custom_emoji(PLAYER_PREMIUM_EMOJIS['money'], '💰')
        email_emoji = custom_emoji(PLAYER_PREMIUM_EMOJIS['email'], '📧')
        lock = custom_emoji(PLAYER_PREMIUM_EMOJIS['lock'], '🔒')
        package = custom_emoji(PLAYER_PREMIUM_EMOJIS['package'], '📦')
        support = custom_emoji(PLAYER_PREMIUM_EMOJIS['warning'], '⚠️')
        
        # Monta mensagem de sucesso
        texto = (
            f"{check} <b>Compra Realizada com Sucesso!</b>\n\n"
            f"{globe} Produto: {html.escape(display_name(product.get('name', 'Conta Global')))}\n"
            f"{money} Valor: R$ {price:.2f}\n\n"
            f"{email_emoji} <b>Dados de Acesso:</b>\n"
        )
        
        for label, value in credentials.items():
            if value is not None:
                texto += f"{html.escape(str(label))}: <code>{html.escape(str(value))}</code>\n"
        if order.get('id'):
            texto += f"Pedido: <code>{html.escape(str(order['id']))}</code>\n"
        if not credentials:
            texto += "Pedido recebido pelo fornecedor. Consulte o suporte com o número do pedido.\n"

        texto += f"\n{money} Saldo restante: R$ {user_balance - price:.2f}\n\n"
        texto += f"{support} Precisa de ajuda? Entre em contato com o suporte!"
        
        markup = InlineKeyboardMarkup()
        
        buy_more_btn = InlineKeyboardButton('Comprar Mais', callback_data='contas_globais_menu')
        buy_more_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['globe']
        markup.add(buy_more_btn)
        
        home_btn = InlineKeyboardButton('Menu Principal', callback_data='menu_start')
        home_btn.icon_custom_emoji_id = PLAYER_PREMIUM_EMOJIS['home']
        markup.add(home_btn)
        
        mostrar(texto, markup)
        
        # Notifica no grupo de vendas
        try:
            sales_group_id = get_sales_notification_chat_id()
            customer = custom_emoji(PLAYER_PREMIUM_EMOJIS['email'], '📧')
            date = custom_emoji(PLAYER_PREMIUM_EMOJIS['sparkles'], '✨')
            notif_texto = (
                f"{globe} <b>VENDA - CONTA GLOBAL</b>\n\n"
                f"{customer} Cliente: {_build_personal_mention(call.from_user.id)}\n"
                f"{package} Produto: {html.escape(display_name(product.get('name', 'Conta Global')))}\n"
                f"{money} Valor: R$ {price:.2f}\n"
                f"{date} Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
            )
            bot.send_message(sales_group_id, notif_texto, parse_mode='HTML')
        except:
            pass
