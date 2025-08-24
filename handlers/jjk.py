from datetime import datetime, timedelta
import telebot
from telebot import types
from config import bot
from config import DEV_CHAT_ID

# --- Вспомогательная функция парсинга времени ---
def parse_time(time_str: str) -> datetime:
    """
    Принимает строку вида '30m', '2h', '1d' и возвращает datetime окончания наказания.
    """
    now = datetime.now()
    unit = time_str[-1]
    value = int(time_str[:-1])
    if unit == 'm':
        return now + timedelta(minutes=value)
    elif unit == 'h':
        return now + timedelta(hours=value)
    elif unit == 'd':
        return now + timedelta(days=value)
    else:
        raise ValueError("Неверный формат времени. Используйте m/h/d.")

# --- Логирование ---
def log_action(admin, action, target, chat):
    text = (
        f"🛠 <b>Лог админ-команды</b>\n"
        f"👮‍♂️ Админ: {admin.first_name} ({admin.id})\n"
        f"🎯 Цель: {target.first_name} ({target.id})\n"
        f"📌 Действие: {action}\n"
        f"💬 Чат: {chat.title} ({chat.id})\n"
        f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    bot.send_message(DEV_CHAT_ID, text, parse_mode="HTML")


# --- 1. Приветствие нового пользователя ---
@bot.chat_member_handler()
def greet_new_member(message: types.ChatMemberUpdated):
    if message.new_chat_member.status == "member":
        bot.send_message(
            message.chat.id,
            f"👋 Добро пожаловать, {message.new_chat_member.user.first_name}!"
        )

# --- 2. Автодобавление ссылок при постах из канала ---
@bot.message_handler(
    content_types=['text', 'photo', 'video', 'document'],
    func=lambda m: m.is_automatic_forward
)
def add_social_links(message):
    if message.is_automatic_forward:
        social_links = (
            "\n📌 Наши соцсети:\n"
            "VK: https://vk.com/...\n"
            "TG: https://t.me/...\n"
        )
        bot.send_message(message.chat.id, social_links)

# --- 3. Удаление сообщений пользователей + команды админа ---
@bot.message_handler(commands=['del'])
def delete_user_message(message):
    member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status in ("administrator", "creator") and message.reply_to_message:
        bot.delete_message(message.chat.id, message.reply_to_message.message_id)
        bot.delete_message(message.chat.id, message.message_id)
        log_action(message.from_user, "Удаление сообщения", message.reply_to_message.from_user, message.chat)

# --- 4. Мут ---
@bot.message_handler(commands=['mute'])
def mute_user(message):
    member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status in ("administrator", "creator") and message.reply_to_message:
        try:
            args = message.text.split()
            until = parse_time(args[1]) if len(args) > 1 else datetime.now() + timedelta(hours=1)
            user_id = message.reply_to_message.from_user.id

            # Мутим пользователя
            bot.restrict_chat_member(
                message.chat.id,
                user_id,
                until_date=until,
                can_send_messages=False
            )

            # Удаляем сообщения
            bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            bot.delete_message(message.chat.id, message.message_id)

            # Лог в DEV_CHAT_ID
            log_action(
                message.from_user,
                f"Мут до {until}",
                message.reply_to_message.from_user,
                message.chat
            )

            # Публичное уведомление в чат
            until_str = until.strftime('%d.%m.%Y %H:%M:%S')
            bot.send_message(
                message.chat.id,
                f"🔇 Пользователь <a href='tg://user?id={user_id}'>"
                f"{message.reply_to_message.from_user.first_name}</a> "
                f"замучен до <b>{until_str}</b>.",
                parse_mode="HTML"
            )

        except Exception as e:
            bot.reply_to(message, f"Ошибка: {e}")


# --- 5. Размут ---
@bot.message_handler(commands=['unmute'])
def unmute_user(message):
    member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("administrator", "creator"):
        return  # Не админ — выходим

    target_user = None

    # 1️⃣ Если команда как ответ на сообщение
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user

    # 2️⃣ Если указан @username в тексте команды
    else:
        args = message.text.split()
        if len(args) > 1 and args[1].startswith("@"):
            username = args[1][1:]  # убираем @
            try:
                # Получаем список участников чата (работает только в супергруппах)
                # или ищем через get_chat_member
                # В pyTelegramBotAPI нет прямого поиска по username, поэтому:
                #  - если бот недавно видел этого пользователя в чате, он сможет его найти
                #  - иначе Telegram API не даст ID
                for member_info in bot.get_chat_administrators(message.chat.id) + \
                                    [bot.get_chat_member(message.chat.id, message.from_user.id)]:
                    if member_info.user.username and member_info.user.username.lower() == username.lower():
                        target_user = member_info.user
                        break
                # Если не нашли среди админов — пробуем через историю сообщений (если бот её видел)
                # Здесь можно хранить username->id в своей базе при каждом сообщении
            except Exception as e:
                bot.reply_to(message, f"Не удалось найти пользователя @{username}: {e}")
                return

    if not target_user:
        bot.reply_to(message, "Не удалось определить пользователя. Ответьте на его сообщение или укажите @username.")
        return

    try:
        bot.restrict_chat_member(
            message.chat.id,
            target_user.id,
            can_send_messages=True
        )
        bot.delete_message(message.chat.id, message.message_id)

        # Лог
        log_action(message.from_user, "Размут", target_user, message.chat)

        # Публичное уведомление
        bot.send_message(
            message.chat.id,
            f"🔊 Пользователь <a href='tg://user?id={target_user.id}'>"
            f"{target_user.first_name}</a> теперь может писать в чат.",
            parse_mode="HTML"
        )

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")


# --- 6. Бан ---
@bot.message_handler(commands=['ban'])
def ban_user(message):
    member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status in ("administrator", "creator") and message.reply_to_message:
        try:
            args = message.text.split()
            until = parse_time(args[1]) if len(args) > 1 else None
            user_id = message.reply_to_message.from_user.id

            # Баним пользователя
            bot.ban_chat_member(message.chat.id, user_id, until_date=until, revoke_messages=False)

            # Удаляем сообщения
            bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            bot.delete_message(message.chat.id, message.message_id)

            # Лог в DEV_CHAT_ID
            log_action(
                message.from_user,
                f"Бан до {until if until else 'навсегда'}",
                message.reply_to_message.from_user,
                message.chat
            )

            # Публичное уведомление в чат
            if until:
                until_str = until.strftime('%d.%m.%Y %H:%M:%S')
                ban_text = f"⛔ Пользователь <a href='tg://user?id={user_id}'>" \
                           f"{message.reply_to_message.from_user.first_name}</a> " \
                           f"забанен до <b>{until_str}</b>."
            else:
                ban_text = f"⛔ Пользователь <a href='tg://user?id={user_id}'>" \
                           f"{message.reply_to_message.from_user.first_name}</a> " \
                           f"забанен <b>навсегда</b>."

            bot.send_message(message.chat.id, ban_text, parse_mode="HTML")

        except Exception as e:
            bot.reply_to(message, f"Ошибка: {e}")


# --- 7. Разбан ---
@bot.message_handler(commands=['unban'])
def unban_user(message):
    # Проверка прав
    member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("administrator", "creator"):
        return

    target_user = None

    # 1️⃣ Если команда как ответ на сообщение
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user

    # 2️⃣ Если указан @username в тексте команды
    else:
        args = message.text.split()
        if len(args) > 1 and args[1].startswith("@"):
            username = args[1][1:]  # убираем @
            try:
                # Перебираем участников, которых бот "знает"
                # (в идеале — хранить username->id в своей базе при каждом сообщении)
                chat_members = bot.get_chat_administrators(message.chat.id)
                for admin_info in chat_members:
                    if admin_info.user.username and admin_info.user.username.lower() == username.lower():
                        target_user = admin_info.user
                        break
            except Exception as e:
                bot.reply_to(message, f"Не удалось найти пользователя @{username}: {e}")
                return

    if not target_user:
        bot.reply_to(message, "Не удалось определить пользователя. Ответьте на его сообщение или укажите @username.")
        return

    try:
        # Разбан
        bot.unban_chat_member(message.chat.id, target_user.id)

        # Удаляем команду
        bot.delete_message(message.chat.id, message.message_id)

        # Лог в DEV_CHAT_ID
        log_action(message.from_user, "Разбан", target_user, message.chat)

        # Публичное уведомление
        bot.send_message(
            message.chat.id,
            f"✅ Пользователь <a href='tg://user?id={target_user.id}'>"
            f"{target_user.first_name}</a> был разбанен.",
            parse_mode="HTML"
        )

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")


