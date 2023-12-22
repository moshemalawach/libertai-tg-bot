import re
import os
import json
import requests
import telebot
import asyncio
from telebot.async_telebot import AsyncTeleBot
from functools import cache
from telebot import types
from dotenv import load_dotenv

from logs import recover as recover_logs, save as save_logs, HISTORIES
from inference import complete, prepare_prompt
from settings import ACTIVE_MODEL, ACTIVE_PROMPT, COMMANDS_DICT

load_dotenv()

TOKEN = os.getenv("TG_TOKEN")
bot = AsyncTeleBot(TOKEN)

current_history = {} # Store the current chat history count for each chat


last_read_message = None  # Store the ID of the last processed message

SLOTS = {}
CHATS = {}
""" Example chat message:
{'content_type': 'text', 'id': 69, 'message_id': 69, 'from_user': {'id': 414434471, 'is_bot': False, 'first_name': 'Moshe', 'username': 'Jonnyjonnyjon', 'last_name': 'Malawach [AlephIM]', 'language_code': 'fr', 'can_join_groups': None, 'can_read_all_group_messages': None, 'supports_inline_queries': None, 'is_premium': True, 'added_to_attachment_menu': None}, 'date': 1699449497, 'chat': {'id': -4050541508, 'type': 'group', 'title': 'me testing shit', 'username': None, 'first_name': None, 'last_name': None, 'is_forum': None, 'photo': None, 'bio': None, 'join_to_send_messages': None, 'join_by_request': None, 'has_private_forwards': None, 'has_restricted_voice_and_video_messages': None, 'description': None, 'invite_link': None, 'pinned_message': None, 'permissions': None, 'slow_mode_delay': None, 'message_auto_delete_time': None, 'has_protected_content': None, 'sticker_set_name': None, 'can_set_sticker_set': None, 'linked_chat_id': None, 'location': None, 'active_usernames': None, 'emoji_status_custom_emoji_id': None, 'has_hidden_members': None, 'has_aggressive_anti_spam_enabled': None, 'emoji_status_expiration_date': None}, 'sender_chat': None, 'forward_from': None, 'forward_from_chat': None, 'forward_from_message_id': None, 'forward_signature': None, 'forward_sender_name': None, 'forward_date': None, 'is_automatic_forward': None, 'reply_to_message': None, 'via_bot': None, 'edit_date': None, 'has_protected_content': None, 'media_group_id': None, 'author_signature': None, 'text': 'what is aleph.im, does someone know?', 'entities': [<telebot.types.MessageEntity object at 0x7f4aa97033d0>], 'caption_entities': None, 'audio': None, 'document': None, 'photo': None, 'sticker': None, 'video': None, 'video_note': None, 'voice': None, 'caption': None, 'contact': None, 'location': None, 'venue': None, 'animation': None, 'dice': None, 'new_chat_member': None, 'new_chat_members': None, 'left_chat_member': None, 'new_chat_title': None, 'new_chat_photo': None, 'delete_chat_photo': None, 'group_chat_created': None, 'supergroup_chat_created': None, 'channel_chat_created': None, 'migrate_to_chat_id': None, 'migrate_from_chat_id': None, 'pinned_message': None, 'invoice': None, 'successful_payment': None, 'connected_website': None, 'reply_markup': None, 'message_thread_id': None, 'is_topic_message': None, 'forum_topic_created': None, 'forum_topic_closed': None, 'forum_topic_reopened': None, 'has_media_spoiler': None, 'forum_topic_edited': None, 'general_forum_topic_hidden': None, 'general_forum_topic_unhidden': None, 'write_access_allowed': None, 'user_shared': None, 'chat_shared': None, 'story': None, 'json': {'message_id': 69, 'from': {'id': 414434471, 'is_bot': False, 'first_name': 'Moshe', 'last_name': 'Malawach [AlephIM]', 'username': 'Jonnyjonnyjon', 'language_code': 'fr', 'is_premium': True}, 'chat': {'id': -4050541508, 'title': 'me testing shit', 'type': 'group', 'all_members_are_administrators': True}, 'date': 1699449497, 'text': 'what is aleph.im, does someone know?', 'entities': [{'offset': 8, 'length': 8, 'type': 'url'}]}}"""

# @cache
async def get_chat(chat_id):
    if chat_id in CHATS:
        return CHATS[chat_id]
    
    return await bot.get_chat(chat_id)

@bot.message_handler(commands=['clear'])
async def clear_history(message):
    chat_id = str(message.chat.id)
    reply = bot.reply_to(message, "Clearing history.")
    HISTORIES[chat_id] = []
    current_history[chat_id] = 0
    await save_logs()
    return

@bot.message_handler(content_types=['text'])
async def handle_text_message(message):
    if message.chat.type in ['group', 'supergroup', 'private']:  # Check if the chat is a group
        # if message.chat.type == 'private':
        #     chat = message.chat.id
        # else:
        chat = await get_chat(message.chat.id)

        chat_id = str(message.chat.id)

        if message.is_topic_message:
            chat_id = str(message.chat.id) + "_" + str(message.message_thread_id)
        if (chat_id not in HISTORIES):
            HISTORIES[chat_id] = []
            current_history[chat_id] = 0
        elif chat_id not in current_history:
            # We take the lowest number between 40 and the current history length
            current_history[chat_id] = min(ACTIVE_MODEL['low_message_water'], len(HISTORIES[chat_id]))
        else:
            # if it's higher than 80, we set to 40
            if current_history[chat_id] > ACTIVE_MODEL['high_message_water']:
                current_history[chat_id] = ACTIVE_MODEL['low_message_water']


        if isinstance(message, types.Message):  # Check if it's a real message (ignores edited messages)
            HISTORIES[chat_id].append(message)
            current_history[chat_id] += 1
            await save_logs()
           
            # now we can process the message, using our AI model
            # we will use the last history messages as context
            messages = HISTORIES[chat_id][-current_history[chat_id]:]
            # messages = HISTORIES[chat_id][-30:]
            if chat.type != 'private' and not (await should_answer(messages, ACTIVE_PROMPT, ACTIVE_MODEL)):
                return
            reply = None
            async for result in generate_answer(messages, ACTIVE_PROMPT, ACTIVE_MODEL, chat_id=chat_id, chat=chat):
                got_null = (result.strip('\n').strip().strip('"') == "NULL")
                if got_null: break

                if reply is None:
                    reply = await bot.reply_to(message, result)
                else:
                    # update the reply
                    print("updating message")
                    await bot.edit_message_text(chat_id=message.chat.id, message_id=reply.message_id, text=result)

            if reply is not None:
                HISTORIES[chat_id].append(reply)
                current_history[chat_id] += 1
            await save_logs()
            
    else:
        print(message)

async def generate_answer(messages, active_prompt, model, chat_id="0", chat=None):
    persona_name = active_prompt['persona_name']
    prompt = await prepare_prompt(messages, active_prompt, model, chat=chat)

    is_unfinished = True
    tries = 0
    compounded_result = ""
    stop_sequences = [*model['stop_sequences']]

    if not len(stop_sequences):
        stop_sequences = [f"{model['user_prepend']}"]

    alternative_stop_sequence = f"{model['user_prepend']}{persona_name}:"
    stop_sequences.append(alternative_stop_sequence)

    # alternative_stop_sequence_2 = f"{user_name}:"
    # stop_sequences.append(alternative_stop_sequence_2)

    while is_unfinished and tries < model['max_tries']:
        tries += 1
        stopped, last_result = await complete(prompt + compounded_result, model, stop_sequences, chat_id=chat_id)
        full_result = compounded_result + last_result
        results = full_result
        print(results)

        for stop_seq in stop_sequences:
            results = "|||||".join(results.split(f"\n{stop_seq}"))
            results = "|||||".join(results.split(f"{stop_seq}"))

        results = results.split("|||||")

        first_message = results[0].rstrip()
        compounded_result = first_message
        to_yield = compounded_result

        if stopped or results[1:] or len(last_result) < model['max_length']:
            is_unfinished = False
        else:
            is_unfinished = True

            if tries < model['max_tries']:
                to_yield += "..."

        yield to_yield
        
async def basic_answer_checks(messages, active_prompt):
    last_message = messages[-1]
    if "bot" in last_message.text or active_prompt['persona_name'] in last_message.text:
        return True
    
    if (last_message.reply_to_message is not None) and last_message.reply_to_message.from_user.username == active_prompt['persona_name']:
        return True
    
    for command in COMMANDS_DICT.keys():
        if last_message.text.startswith(command.split(" ")[0]):
            return True
    
    return False

async def should_answer(messages, active_prompt, model):
    if not await basic_answer_checks(messages, active_prompt):
        return False
    
    return True
    
    # prompt = prepare_prompt(messages, active_prompt, model, add_persona=False)
    # prompt = f"{prompt}{model['user_prepend']}"

    # stopped, answer = complete(prompt, model, ["YES", "NO"])
    # print(answer)
    # if answer.startswith(active_prompt['persona_name']) and not answer.strip().strip('"').endswith("NULL"):
    #     return True
    # else:
    #     return False

@bot.edited_message_handler(content_types=['text'])
def edit_message(message):
    for topics, messages in HISTORIES.items():
        for msg in messages:
            if msg.message_id == message.message_id:
                msg.text = message.text
                break
    print(message)

# @bot.deleted_message_handler(content_types=['text'])
# def delete_message(message):
#     for topics, messages in HISTORIES.items():
#         for msg in messages:
#             if msg.message_id == message.message_id:
#                 messages.remove(msg)
#                 break
#     print(message)

async def run_bot():
    recover_logs()
    ACTIVE_PROMPT['persona_name'] = (await bot.get_me()).username

    # use the commands dict to set the commands for the bot
    await bot.set_my_commands([
        types.BotCommand(command[1:].split(' ')[0], description)
        for command, description in COMMANDS_DICT.items()
    ], scope=types.BotCommandScopeAllPrivateChats())

    await bot.set_my_commands([
        types.BotCommand(command[1:].split(' ')[0], description)
        for command, description in COMMANDS_DICT.items()
    ], scope=types.BotCommandScopeAllGroupChats())
    
    await bot.polling()
    
if __name__ == '__main__':

    asyncio.run(run_bot())
    save_logs()