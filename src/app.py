import asyncio
import logging
import os

import telebot
from dotenv import load_dotenv

from telebot import types as telebot_types, async_telebot
from history import History, chat_id_from_message
from chat_bot import ChatBot, LLM_FUNCTIONS_DESCRIPTION
from config import AppConfig

# Initialize our configuration
appConfig = AppConfig()

# TODO: spin out state into a separate module
# TODO: make these modules take appConfig as a parameter. For now they all just import it directly
# These constants comprise application global state

# The bot instance
BOT = async_telebot.AsyncTeleBot(appConfig.get_tg_token())
# The logger to use
LOGGER = appConfig.get_logger()
# Instance of history for recording and pulling chat history
HISTORY = History(appConfig)
# The chat bot agent
CHAT_BOT = ChatBot(appConfig)
# List of chat bot names to target in group chats
#  This should cover common misspellings and variations on the bot's name
#   as well as other things that might be used to refer to the bot
CHAT_BOT_NAME_TARGETS = [
    # Common monikers for the chat bot
    "chatbot", "chat-bot", "chat bot", "chatbot", "chat-bot", "chat bot", "bot", "assistant", "ai", 
]

def populate_bot_name_targets(name: str):
    """
    Populate the list of chat bot name targets with the bot's name and username.
    """
    CHAT_BOT_NAME_TARGETS.extend([
        # The chat bot's persona name
        name,
        name.lower(),
        name.upper(),
        # A bunch of potential misspellings
        name.replace(" ", ""), name.replace("-", ""), name.replace(" ", "-"), name.replace("-", " "), name.replace(" ", "_"), name.replace("_", " "), name.replace("_", "-"), name.replace("-", "_"),
        # # Missing letters at the edges of words
        name[1:], name[:-1],
        # Swapped letters at the edges of words
        name[1:] + name[0], name[-1] + name[:-1]
    ])


# COMMON COMMANDS AND HANDLERS

# Register Common Chat Commands here
COMMON_COMMANDS = {
    "help": "Show this help",
    "clear": "Clear the chat history from the chat bot",
    "info": "Show info about the bot configuration",
    # TODO: index last message
    #  this marks the last message as indexed so that it's is included in prompt generation
    # TODO: define a word command
    #  this command should take a word as an argument and return a definition of the word

    # TODO: implement a scheme for calling abstract commands
    #  what i mean is, that all commands should be explicitly defined in the
    #   chat bot configuration, and not handled by the llm. For example, if want to implement
    #    something like '/joke', it should be defined in the chat bot configuration as a command route,
    #     which in turn may just call the llm with a predefined prompt. This way, we can have a clear separation 
    #      of concerns and a clear definition of what the llm should do and what the chat bot should do. 
}

# TODO: for now these are the same, but 
#  I anticipate needing to define different 
#   commands for different chat types

# Register Private Chat Commands here
PRIVATE_CHAT_COMMANDS = {
    **COMMON_COMMANDS,
}

# Register Group Chat Commands here
GROUP_CHAT_COMMANDS = {
    **COMMON_COMMANDS,
}

# Command Handlers

@BOT.message_handler(commands=['help'])
async def help_command(message: telebot_types.Message):
    """
    Send a message to the user with a list of commands and their descriptions.
    """

    chat = message.chat
    message_id = message.id 
    chat_id = chat.id

    LOGGER.debug("/help called", extra={"chat_id": chat_id, "message_id": message_id})

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
    Clear the history of messages for a given chat.
    """
    
    message_id = message.id 
    chat_id = message.chat.id

    LOGGER.info("/clear called", extra={"chat_id": chat_id, "message_id": message_id})

    reply = await BOT.reply_to(message, "Clearing chat history...")
    HISTORY.clear_chat_history(chat_id)
    await BOT.edit_message_text(chat_id=chat_id, message_id=reply.message_id, text="Chat history cleared.")
    None

@BOT.message_handler(commands=['info'])
async def info_command(message: telebot_types.Message):
    """
    Send a message to the user with information about the bot.
    """

    chat = message.chat
    message_id = message.id 
    chat_id = chat.id

    LOGGER.debug("/info called", extra={"chat_id": chat_id, "message_id": message_id})

    info_text = "This bot is a chat bot built on top of the Libertai platform. It uses a large language model to generate responses to user messages. The bot is designed to be helpful and informative, and can perform a variety of tasks."
    # Append Model Parameters to the info text
    info_text += "\n\nThe current model parameters are as follows:\n"
    for param, value in appConfig.get_config()['model'].items():
        info_text += f"{param}: {value}\n"
    info_text += "Currently it has access to the following functions (which you can ask it to perform):\n"
    info_text += "\n" + LLM_FUNCTIONS_DESCRIPTION + "\n"
    info_text += "For more information, please see the source code at: https://github.com/amiller68/libertai-tg-bot"
    await BOT.reply_to(message, info_text)
    return None

# All other mesage handlers

# Edit Message Handler
@BOT.edited_message_handler(content_types=['text'])
def edit_message(message):
    """
    Handle edits to text messages sent to all chats. Should update the chat history with the new message.
    """
    message_id = message.id
    chat_id = message.chat.id

    LOGGER.debug("editing text message", extra={"chat_id": chat_id, "message_id": message_id})
    
    # TODO: evaluate safety of this / invariants / side effects
    HISTORY.update_message(message)

# Text Message Handler -- where messages get passed to the LLM
@BOT.message_handler(content_types=['text'])
async def handle_text_messages(message: telebot_types.Message):
    """
    Handle all text messages.
    Use the chatbot to construct an informed response
    """

    message_id = message.id
    chat_id = message.chat.id

    LOGGER.debug("handling text message", extra={"chat_id": chat_id, "message_id": message_id})
    
    # TODO: proper error handling
    # Add the message to the chat history
    HISTORY.add_message(message)

    # If the message is not a private message, check if the message mentions the bot
    if message.chat.type not in ['private']:
        # Don't let the bot respond to messages which don't mention the bot
        found = False
        for target in CHAT_BOT_NAME_TARGETS:
            if target in message.text:
                found = True
                break
        if not found:
            return None
        # Don't let the bot respond to messages that are replies to itself
        if (
                message.reply_to_message is not None) and message.reply_to_message.from_user.username == CHAT_BOT.persona_name:
            print(f"message.reply_to_message.from_user.username: {message.reply_to_message.from_user.username}")
            return None

    print(f"message.text: {message.text}")
    # TODO: some sort of animation to indicate that the bot is thinking
    # Send an initial message to the user
    result = "I'm thinking..."
    reply = await BOT.reply_to(message, result)

    # Attempt to reply to the message
    try:
        async for (code, content) in CHAT_BOT.yield_response(HISTORY, message): 
            # Check for an updated response, otherwise just do nothing
            if content != result:
                result = content
                # Update the message
                reply = await BOT.edit_message_text(chat_id=chat_id, message_id=reply.message_id, text=result)
    except Exception as e:
        LOGGER.error(f"error handling text message: {e}", extra={"chat_id": chat_id, "message_id": message_id})
        await BOT.edit_message_text(chat_id=message.chat.id, message_id=reply.message_id, text="I'm sorry, I got confused. Please try again.")
    finally:
        HISTORY.add_message(reply)
        return None


# Run the Bot
async def run_bot():
    LOGGER.info("Starting Bot...")
    try:
        # Get the bot's user name
        bot_info = await BOT.get_me()
        LOGGER.info(f"Bot started: {bot_info.username}")
        CHAT_BOT.set_persona_name(bot_info.username)
        populate_bot_name_targets(bot_info.username)

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
        await BOT.polling()
    except Exception as e:
        LOGGER.critical(f"An unexpected error occurred: {e}")
    finally:
        LOGGER.info("Stopping Bot...")
        await CHAT_BOT.close_sessions()

if __name__ == '__main__':
    asyncio.run(run_bot())
