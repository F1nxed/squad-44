import os
from dotenv import load_dotenv
from client import Client

load_dotenv()
API_KEY = os.getenv("API_KEY")
# Insert UI In here if needed


# Starting the bot
bot = Client()
bot.run(API_KEY)
