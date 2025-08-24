import telebot
import handlers
from config import bot


print("Бот запущен (синхронный режим)...")
if __name__ == "__main__":
    bot.infinity_polling()
