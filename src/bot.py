import asyncio
from telebot import types as telebot_types, async_telebot

from database import Database
from logger import Logger
from agent import Agent
from config import Config

# Common monikers for the chat bot or what one might call it
BOT_NAMES = [
    # Common monikers for the chat bot
    "chatbot",
    "chat-bot",
    "chat bot",
    "chatbot",
    "chat-bot",
    "chat bot",
    "bot",
    "assistant",
    "ai",
]


class Bot:
    bot: async_telebot.AsyncTeleBot
    logger: Logger
    database: Database
    # agent: Agent
    bot_names: list

    def __init__(self, config: Config):
        tg_token = config.tg_token
        database_url = config.database_url
        debug = config.debug
        log_path = config.log_path
        agent_config = config.agent_config

        # Create our Async
        try:
            self.logger = Logger(log_path, debug)
            self.logger.info("Setting up Bot...")
            self.bot = async_telebot.AsyncTeleBot(tg_token)
            self.logger.info("Setting up Database...")
            self.database = Database(database_url)
            self.logger.info("Setting up Agent...")
            self.agent = Agent(agent_config)
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during setup: {e}")
            raise e

    # NOTE (amiller68): This is called later since not doing so would require __init__ to be async
    #  This is used to provide the bot with a base against which to determine if it's being addressed
    def set_name(self, name: str):
        # Set the name of the bot on the agent -- this is it's telegram username and persona name
        self.agent.set_persona_name(name)
        names = BOT_NAMES
        names.append(name)
        bot_names = []
        for n in names:
            bot_names.extend(
                [
                    n,
                    n.lower(),
                    n.upper(),
                    # bunch of potential misspellings
                    n.replace(" ", ""),
                    n.replace("-", ""),
                    n.replace(" ", "-"),
                    n.replace("-", " "),
                    n.replace(" ", "_"),
                    n.replace("_", " "),
                    n.replace("_", "-"),
                    n.replace("-", "_"),
                    # Missing letters at the edges of words
                    n[1:],
                    n[:-1],
                    # apped letters at the edges of words
                    n[1:] + n[0],
                    n[-1] + n[:-1],
                ]
            )
        self.bot_names = bot_names

    # Message Handlers

    # NOTE (amiller68): to some extent, i want this to use dynamic values, but now let's just hard code it
    #  Make sure to update this if you add new commands!
    async def _help_command_handler(self, message: telebot_types.Message):
        """
        Send a message to the user with a list of commands and their descriptions.
        """
        commands = [
            {"help": "Show this help"},
            {"clear": "Clear the chat history from the chat bot"},
        ]
        # TODO: if we need to split commands based on chat type, we can do that here
        help_text = "The following commands are available:\n\n"
        for command, command_info in commands:
            help_text += f"/{command} - {command_info}\n"
        await self.bot.reply_to(message, help_text)
        return None

    async def _clear_command_handlers(self, message: telebot_types.Message):
        """
        Clear the history of messages for a given chat.
        """
        chat_id = message.chat.id
        self.logger.info("/clear called", chat_id=chat_id, message_id=message.message_id)
        reply = await self.bot.reply_to(message, "Clearing chat history...")
        self.database.clear_chat_history(chat_id)
        await self.bot.edit_message_text(
            chat_id=chat_id, message_id=reply.message_id, text="Chat history cleared."
        )
        return None

    async def _text_message_handler(self, message: telebot_types.Message):
        """
        Handle all text messages.
        Use the chatbot to construct an informed response
        """
        chat_id = message.chat.id
        self.logger.info("Received text message", chat_id=chat_id, message_id=message.message_id)
        # Add the message to the chat history
        self.database.add_message(message)
        # If the message is not a private message, check if the message mentions the bot
        if message.chat.type not in ["private"]:
            # Don't let the bot respond to messages which don't mention the bot
            found = False
            for target in self.bot_names:
                if target in message.text:
                    found = True
                    break
            if not found:
                return None
            # Don't let the bot respond to messages that are replies to itself
            if (
                (message.reply_to_message is not None)
                and message.reply_to_message.from_user.username
                == self.agent.persona_name
            ):
                return None

        # Send an initial message to the user
        result = "I'm thinking..."
        reply = await self.bot.reply_to(message, result)
        # Attempt to reply to the message
        try:
            async for _code, content in self.agent.yield_response(
                message, self.database, self.logger
            ):
                # Check for an updated response, otherwise just do nothing
                if content != result:
                    result = content
                    # Update the message
                    reply = await self.bot.edit_message_text(
                        chat_id=chat_id, message_id=reply.message_id, text=result
                    )
        except Exception as e:
            self.logger.error(
                f"error handling text message: {e}",
                chat_id=chat_id,
                message_id=message.message_id,
            )
            reply = await self.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=reply.message_id,
                text="I'm sorry, I got confused. Please try again.",
            )
        finally:
            self.database.add_message(reply, reply_to_message_id=message.message_id)
            return None

    # NOTE (amiller68): This is where all of the handlers and command get registered and set on the bot
    #  This is a little verbose and duplicative, but it works and implements a sharp separation of concerns
    #   between internal bot logic and how it hooks into the telebot
    async def register_handlers(self):
        # COMMANDS

        # Register the handlers themselves
        # handle /help
        @self.bot.message_handler(commands=["help"])
        async def _help_command_handler(message: telebot_types.Message):
            await self._help_command_handler(message)

        # handle /clear
        @self.bot.message_handler(commands=["clear"])
        async def clear_command_handler(message: telebot_types.Message):
            await self._clear_command_handlers(message)

        # Make the commands available and scoped
        # NOTE (amiller68): For now we can give everything the default scope, but we might want to change that
        #  If you implment a command that should only be available in private chats, you can do that here
        await self.bot.set_my_commands(
            [
                telebot_types.BotCommand(command, description)
                for command, description in [
                    ("help", "Show this help"),
                    ("clear", "Clear the chat history from the chat bot"),
                ]
            ],
            scope=telebot_types.BotCommandScopeDefault(),
        )

        # General Message Handler

        # Handle all text messages
        @self.bot.message_handler(content_types=["text"])
        async def text_message_handler(message: telebot_types.Message):
            await self._text_message_handler(message)

        # TODO: Implement scheme for responding to more types of messages
        #  For example, we might want to respond to images or other media
        #  We might also want to respond to stickers or other types of messages

    async def run(self):
        self.logger.info("Starting Bot...")
        try:
            # Get the bot's user name
            bot_info = await self.bot.get_me()
            self.logger.info(f"Bot started: {bot_info.username}")
            self.set_name(bot_info.username)
            await self.register_handlers()
            await self.bot.polling()
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}")
        finally:
            self.logger.info("Stopping Bot...")
            await self.agent.close_sessions()
