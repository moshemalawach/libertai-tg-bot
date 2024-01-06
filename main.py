import os
import telebot
import asyncio
from dotenv import load_dotenv
import logging

logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

from telebot import types as telebot_types, async_telebot
from history import History, chat_id_from_message
from chat_bot_model import ChatBotModel

load_dotenv()
TOKEN = os.getenv("TG_TOKEN")
BOT = async_telebot.AsyncTeleBot(TOKEN, colorful_logs=True)
HISTORY = History()
# TODO: should I need to pull the BOT name from the BOT object?
#  or can we just configure this?
CHAT_BOT_MODEL = ChatBotModel()

# Register Common Chat Commands here
COMMON_COMMANDS = {
    "help": "Show this help",
    "clear": "Clear the chat history from the chat bot",
}

# Register Private Chat Commands here
PRIVATE_CHAT_COMMANDS = {
    **COMMON_COMMANDS,
}

# Register Group Chat Commands here
GROUP_CHAT_COMMANDS = {
    **COMMON_COMMANDS,
    "ask": "Ask a question of the BOT",
}

"""
Handlers
TODO: find way more ergonomic way to bind handlers to the telebot -- its annoying we can't split
apart this module into multiple files with decorators ... or at least I don't know how to do it
It's also annoyting that I can't control state or pass arguments to the handlers, so I have to use
a global variable to control the active prompt and model too...
"""

# COMMON COMMANDS AND HANDLERS

@BOT.message_handler(commands=['help'])
async def help_command(message: telebot_types.Message):
    """
    Send a message to the user with a list of commands and their descriptions.
    """

    # Get a handle on the proper chat object
    chat = message.chat

    if chat.type == 'private':
        commands = PRIVATE_CHAT_COMMANDS
    else:
        commands = GROUP_CHAT_COMMANDS

    help_text = "The following commands are available:\n\n"
    for command, command_info in commands.items():
        help_text += f"/{command} - {command_info}\n"
    await BOT.reply_to(message, help_text)
    return None

@BOT.message_handler(commands=['clear'])
async def clear_command(message: telebot_types.Message):
    """
    Clear the HISTORY of messages for a given chat.
    """

    # Get a handle on the proper chat object
    chat_id = chat_id_from_message(message)
    reply = await BOT.reply_to(message, "Clearing chat history...")
    HISTORY.clear_chat_history(chat_id)
    await BOT.edit_message_text(chat_id=message.chat.id, message_id=reply.message_id, text="Chat history cleared.")
    None


@BOT.edited_message_handler(content_types=['text'])
def edit_message(message):
    """
    Handle edits to text messages sent too all chats.
    """
    # TODO: evaluate safety of this / invariants / side effects
    HISTORY.update_message(message)

# PRIVATE CHAT COMMANDS AND HANDLERS

@BOT.message_handler(content_types=['text'])
async def handle_private_text_messages(message: telebot_types.Message):
    """
    Handle all text messages sent on prviate chats.
    Use the chatbot to construct an informed response
    """

    # # TODO: enable check
    # # Filter for unhandled messages
    # if message.chat.type not in ['private']:
    #     BOT.reply_to(message, 
    #         "Hi there!, I'm a BOT, and I'm not programmed to handle this type of message yet.\n",
    #         "Please engage me in a private chat or a group chat.\n"
    #     )
    #     return

    chat_id = HISTORY.add_message(message)

    result = "Bot is thinking..."
    reply = await BOT.reply_to(message, result)

    async for (code, content) in CHAT_BOT_MODEL.yield_response(HISTORY, chat_id):
        print(f"code: {code}, content: {content}")

        if content != result:
            result = content
            reply = await BOT.edit_message_text(chat_id=message.chat.id, message_id=reply.message_id, text=result)

    HISTORY.add_message(reply)
    return None

# GROUP CHAT COMMANDS AND HANDLERS

# TODO: ASK
@BOT.message_handler(content_types=['text'], commands=['ask'])
async def ask_command(message: telebot_types.Message):
    """
    Handle all text messages sent on group chats.
    Use the chatbot to construct an informed response
    """

    await BOT.reply_to(message, 
        "Hi there!, I'm a bot, and I'm not programmed to handle this type of message yet.\n",
    )
    return None

# Run the Bot
async def run_bot():
    print("Starting Bot...")

    # Set the persona name for the bot
    me = await BOT.get_me()
    persona_name = me.username
    print(f"Bot persona name: {persona_name}")
    CHAT_BOT_MODEL.set_persona_name(persona_name)

    # Register commands for private and group chats
    await BOT.set_my_commands([
        telebot_types.BotCommand(command, description)
        for command, description in PRIVATE_CHAT_COMMANDS.items()
    ], scope=telebot_types.BotCommandScopeAllPrivateChats())
    # Set commands for private chats
    await BOT.set_my_commands([
        telebot_types.BotCommand(command, description)
        for command, description in GROUP_CHAT_COMMANDS.items()
    ], scope=telebot_types.BotCommandScopeAllGroupChats())
    
    # Start the BOT
    print("Bot started.")
    await BOT.polling()
    
if __name__ == '__main__':
    asyncio.run(run_bot())

