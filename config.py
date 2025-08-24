import telebot
from dotenv import load_dotenv
import os

load_dotenv()

bot = telebot.TeleBot(os.getenv('TOKEN'))
DEV_CHAT_ID = os.getenv('DEV_CHAT_ID')
