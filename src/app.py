import asyncio

from config import Config
from bot import Bot

if __name__ == "__main__":
    config = Config()
    bot = Bot(config)
    asyncio.run(bot.run())
