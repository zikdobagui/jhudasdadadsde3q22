# casino.py

import telebot
import random
import logging
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os

# Caminho para o arquivo de dados dos usuários
USERS_FILE = 'users.json'

# Configuração de Logging
logger = logging.getLogger('casino')
logger.setLevel(logging.INFO)

# Crie um manipulador de arquivos para o logger
file_handler = logging.FileHandler('casino.log')
file_handler.setLevel(logging.INFO)

# Crie um formatador e adicione ao manipulador
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Adicione o manipulador ao logger
if not logger.hasHandlers():
    logger.addHandler(file_handler)

# Lista de stickers para Slot Machine (Substitua pelos File IDs reais)
STICKERS_SLOT = [
    "CA1_STICKER_FILE_ID",
    "CA2_STICKER_FILE_ID",
    "CA3_STICKER_FILE_ID",
    "CA4_STICKER_FILE_ID",
    "CA5_STICKER_FILE_ID"
]

# Lista de stickers para Roda da Fortuna (Substitua pelos File IDs reais)
STICKERS_RODA = [
    "RODA1_STICKER_FILE_ID",
    "RODA2_STICKER_FILE_ID",
    "RODA3_STICKER_FILE_ID",
    "RODA4_STICKER_FILE_ID",
    "RODA5_STICKER_FILE_ID"
]

# Chance de ganhar (20%)
WIN_CHANCE = 0.2

# Funções de Gerenciamento de Dados

def load_user_data(user_id):
    """Carrega os dados de um usuário específico."""
    if not os.path.exists(USERS_FILE):
        return None
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        try:
            users = json.load(f)
        except json.JSONDecodeError:
            users = {}
    return users.get(str(user_id), None)

def save_user_data(user_id, data):
    """Salva os dados de um usuário específico."""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            try:
                users = json.load(f)
            except json.JSONDecodeError:
                users = {}
    else:
        users = {}
    users[str(user_id)] = data
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def initialize_user(user_id, username=None):
    """Inicializa os dados de um novo usuário."""
    user_data = {
        "id": user_id,
        "username": username if username else f"User{user_id}",
        "saldo": 100.0,  # Saldo inicial definido como R$100,00
        "ganhos_cassino": 0.0,  # Ganhos no cassino
        "perdas_cassino": 0.0   # Perdas no cassino
    }
    save_user_data(user_id, user_data)
    return user_data

def update_saldo(user_id, amount):
    """Atualiza o saldo do usuário."""
    user_data = load_user_data(user_id)
    if user_data is None:
        user_data = initialize_user(user_id)
    user_data['saldo'] += amount
    save_user_data(user_id, user_data)

def update_ganhos_cassino(user_id, amount):
    """Atualiza os ganhos no cassino do usuário."""
    user_data = load_user_data(user_id)
    if user_data is None:
        user_data = initialize_user(user_id)
    user_data['ganhos_cassino'] += amount
    save_user_data(user_id, user_data)

def update_perdas_cassino(user_id, amount):
    """Atualiza as perdas no cassino do usuário."""
    user_data = load_user_data(user_id)
    if user_data is None:
        user_data = initialize_user(user_id)
    user_data['perdas_cassino'] += amount
    save_user_data(user_id, user_data)

# Funções de Jogos

def slot_machine(bot, message, bet):
    """
    Executa a Slot Machine com aposta variável.
    """
    user_id = message.from_user.id
    username = message.from_user.username
    user_data = load_user_data(user_id)
    
    if user_data is None:
        user_data = initialize_user(user_id, username=username)
    
    saldo = user_data.get('saldo', 0.0)

    if saldo < bet:
        bot.reply_to(message, "❌ Você não tem saldo suficiente para jogar na Slot Machine. Aposte mais para participar.")
        logger.info(f"Usuário {user_id} tentou jogar Slot Machine sem saldo suficiente.")
        return
    
    # Deduz a aposta
    update_saldo(user_id, -bet)
    update_perdas_cassino(user_id, bet)
    
    # Gira os slots
    result = [random.choice(STICKERS_SLOT) for _ in range(3)]
    
    # Envia os stickers
    for sticker in result:
        bot.send_sticker(message.chat.id, sticker)
    
    # Determina se o usuário ganha
    if random.random() < WIN_CHANCE:
        winnings = bet * 2  # Dobra a aposta
        update_saldo(user_id, winnings)
        update_ganhos_cassino(user_id, winnings)
        bot.reply_to(message, f"🎉 Parabéns! Você ganhou R${winnings:.2f} na Slot Machine!")
        logger.info(f"Usuário {user_id} ganhou R${winnings:.2f} na Slot Machine.")
    else:
        bot.reply_to(message, "😞 Que pena! Você não ganhou dessa vez. Tente novamente!")
        logger.info(f"Usuário {user_id} perdeu R${bet:.2f} na Slot Machine.")
    
    # Envia o saldo atualizado
    saldo_atual = load_user_data(user_id)['saldo']
    bot.send_message(user_id, f"🔄 Seu saldo atual é: R${saldo_atual:.2f}")
    logger.info(f"Saldo atualizado para o usuário {user_id}: R${saldo_atual:.2f}")

def roda_da_fortuna(bot, message, bet):
    """
    Executa a Roda da Fortuna com aposta variável.
    """
    user_id = message.from_user.id
    username = message.from_user.username
    user_data = load_user_data(user_id)
    
    if user_data is None:
        user_data = initialize_user(user_id, username=username)
    
    saldo = user_data.get('saldo', 0.0)

    if saldo < bet:
        bot.reply_to(message, "❌ Você não tem saldo suficiente para jogar na Roda da Fortuna. Aposte mais para participar.")
        logger.info(f"Usuário {user_id} tentou jogar Roda da Fortuna sem saldo suficiente.")
        return
    
    # Deduz a aposta
    update_saldo(user_id, -bet)
    update_perdas_cassino(user_id, bet)
    
    # Gira a roda (simulada com stickers)
    if random.random() < WIN_CHANCE:
        winnings = bet * 3  # Triplica a aposta
        update_saldo(user_id, winnings)
        update_ganhos_cassino(user_id, winnings)
        bot.send_sticker(message.chat.id, random.choice(STICKERS_RODA))
        bot.reply_to(message, f"🎉 Parabéns! Você ganhou R${winnings:.2f} na Roda da Fortuna!")
        logger.info(f"Usuário {user_id} ganhou R${winnings:.2f} na Roda da Fortuna.")
    else:
        bot.send_sticker(message.chat.id, random.choice(STICKERS_RODA))
        bot.reply_to(message, "😞 Que pena! Você não ganhou dessa vez. Tente novamente!")
        logger.info(f"Usuário {user_id} perdeu R${bet:.2f} na Roda da Fortuna.")
    
    # Envia o saldo atualizado
    saldo_atual = load_user_data(user_id)['saldo']
    bot.send_message(user_id, f"🔄 Seu saldo atual é: R${saldo_atual:.2f}")
    logger.info(f"Saldo atualizado para o usuário {user_id}: R${saldo_atual:.2f}")

def adicionar_jogo(bot, message):
    """
    Lista os jogos disponíveis no cassino.
    """
    jogos = [
        InlineKeyboardButton('🎰 Slot Machine', callback_data='jogo_slot'),
        InlineKeyboardButton('🎡 Roda da Fortuna', callback_data='jogo_roda')
    ]
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(*jogos)
    
    bot.send_message(
        message.chat.id,
        "🎲 <b>Bem-vindo ao Cassino!</b>\nEscolha um jogo para começar:",
        parse_mode='HTML',
        reply_markup=markup
    )
    logger.info(f"Usuário {message.from_user.id} abriu o Cassino.")

def handle_jogos(bot, call):
    """
    Handler para os callbacks dos jogos.
    """
    user_id = call.from_user.id
    if call.data == 'jogo_slot':
        bot.answer_callback_query(call.id, "🎰 Iniciando Slot Machine...", show_alert=False)
        msg = bot.send_message(user_id, "Por favor, envie o valor da aposta para a Slot Machine (1 a 100$):")
        bot.register_next_step_handler(msg, lambda m: process_slot_bet(bot, m))
        logger.info(f"Usuário {user_id} iniciou Slot Machine e aguardando aposta.")
    elif call.data == 'jogo_roda':
        bot.answer_callback_query(call.id, "🎡 Iniciando Roda da Fortuna...", show_alert=False)
        msg = bot.send_message(user_id, "Por favor, envie o valor da aposta para a Roda da Fortuna (1 a 100$):")
        bot.register_next_step_handler(msg, lambda m: process_roda_bet(bot, m))
        logger.info(f"Usuário {user_id} iniciou Roda da Fortuna e aguardando aposta.")

def process_slot_bet(bot, message):
    """
    Processa a aposta para a Slot Machine.
    """
    user_id = message.from_user.id
    text = message.text.strip()
    if text.isdigit():
        bet = int(text)
        if 1 <= bet <= 100:
            saldo = load_user_data(user_id)['saldo']
            if saldo >= bet:
                slot_machine(bot, message, bet)
            else:
                bot.reply_to(message, "❌ Você não tem saldo suficiente para essa aposta.")
                logger.info(f"Usuário {user_id} tentou apostar R${bet}, mas não tinha saldo suficiente.")
        else:
            bot.reply_to(message, "⚠️ A aposta deve ser entre 1 e 100$. Tente novamente.")
            msg = bot.send_message(user_id, "Por favor, envie o valor da aposta para a Slot Machine (1 a 100$):")
            bot.register_next_step_handler(msg, lambda m: process_slot_bet(bot, m))
    else:
        bot.reply_to(message, "⚠️ Por favor, envie um número válido para a aposta.")
        msg = bot.send_message(user_id, "Por favor, envie o valor da aposta para a Slot Machine (1 a 100$):")
        bot.register_next_step_handler(msg, lambda m: process_slot_bet(bot, m))

def process_roda_bet(bot, message):
    """
    Processa a aposta para a Roda da Fortuna.
    """
    user_id = message.from_user.id
    text = message.text.strip()
    if text.isdigit():
        bet = int(text)
        if 1 <= bet <= 100:
            saldo = load_user_data(user_id)['saldo']
            if saldo >= bet:
                roda_da_fortuna(bot, message, bet)
            else:
                bot.reply_to(message, "❌ Você não tem saldo suficiente para essa aposta.")
                logger.info(f"Usuário {user_id} tentou apostar R${bet}, mas não tinha saldo suficiente.")
        else:
            bot.reply_to(message, "⚠️ A aposta deve ser entre 1 e 100$. Tente novamente.")
            msg = bot.send_message(user_id, "Por favor, envie o valor da aposta para a Roda da Fortuna (1 a 100$):")
            bot.register_next_step_handler(msg, lambda m: process_roda_bet(bot, m))
    else:
        bot.reply_to(message, "⚠️ Por favor, envie um número válido para a aposta.")
        msg = bot.send_message(user_id, "Por favor, envie o valor da aposta para a Roda da Fortuna (1 a 100$):")
        bot.register_next_step_handler(msg, lambda m: process_roda_bet(bot, m))
