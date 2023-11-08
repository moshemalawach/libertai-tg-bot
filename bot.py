import re
import json
import requests
import telebot
from telebot import types

from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TG_TOKEN")
bot = telebot.TeleBot(TOKEN)

ACTIVE_PROMPT = {
    "persona": """{{{char}}} doesn't talk if he doesn't need to, or if he isn't explicitely called. In that case he will just post "NULL" as a message (even when answering to someone, NULL messages will be discarded). Other names of {{char}} are Liberchat or assistant.""",
    "persona_name": "liberchat_bot",
}

LOGS_FILE = "logs.json"

JAR = requests.cookies.RequestsCookieJar()

ACTIVE_MODEL = {
    "max_length": 50,
    "max_tries": 4,
    "max_tokens": 16384,
    "temperature": 0.7,
    "sampler_order": [6, 0, 1, 3, 4, 2, 5],
    "top_p": 0.9,
    "top_k": 40,
    "model_type": "knowledge",
    "log_start": "",
    "group_base_prompt": """<|im_start|>system
Telegram chat log of a room.
Room title: {{room_title}}
Room description: {{room_description}}
The AI assistant ("{{char}}"), you, is called on all messages, but helps only if there is a need or he is being called. If not he will just post "NULL" as a message (even when replying).
If not, or users are just talking between themselves, the AI will just post "NULL" as a message (even when replying).
You are "{{char}}", a decentralized LLM, based on open-source models, running on libertai.io (inference platform on top of the aleph.im decentralized cloud).
You will answer concisely, in a cool and funny way. You will never remind that you are a large language model.\n""",
    "persona_start": "",
    "scenario_start": "",
    "user_prepend": "<|im_start|>",
    "user_append": "\n",
    "stop_sequences": ["<|im", "<|im_end|>","<|endoftext|>"],
    "line_separator": "<|im_end|>\n",

    "name": "OpenHermes 2.5 (7B)",
    "api_url": "https://curated.aleph.cloud/vm/a8b6d895cfe757d4bc5db9ba30675b5031fe3189a99a14f13d5210c473220caf/completion",
    "engine": "llamacpp",
    "pass_credentials": True,

    "slot_id": None,
}

last_read_message = None  # Store the ID of the last processed message
HISTORIES = {}
SLOTS = {}

""" Example chat message:
{'content_type': 'text', 'id': 69, 'message_id': 69, 'from_user': {'id': 414434471, 'is_bot': False, 'first_name': 'Moshe', 'username': 'Jonnyjonnyjon', 'last_name': 'Malawach [AlephIM]', 'language_code': 'fr', 'can_join_groups': None, 'can_read_all_group_messages': None, 'supports_inline_queries': None, 'is_premium': True, 'added_to_attachment_menu': None}, 'date': 1699449497, 'chat': {'id': -4050541508, 'type': 'group', 'title': 'me testing shit', 'username': None, 'first_name': None, 'last_name': None, 'is_forum': None, 'photo': None, 'bio': None, 'join_to_send_messages': None, 'join_by_request': None, 'has_private_forwards': None, 'has_restricted_voice_and_video_messages': None, 'description': None, 'invite_link': None, 'pinned_message': None, 'permissions': None, 'slow_mode_delay': None, 'message_auto_delete_time': None, 'has_protected_content': None, 'sticker_set_name': None, 'can_set_sticker_set': None, 'linked_chat_id': None, 'location': None, 'active_usernames': None, 'emoji_status_custom_emoji_id': None, 'has_hidden_members': None, 'has_aggressive_anti_spam_enabled': None, 'emoji_status_expiration_date': None}, 'sender_chat': None, 'forward_from': None, 'forward_from_chat': None, 'forward_from_message_id': None, 'forward_signature': None, 'forward_sender_name': None, 'forward_date': None, 'is_automatic_forward': None, 'reply_to_message': None, 'via_bot': None, 'edit_date': None, 'has_protected_content': None, 'media_group_id': None, 'author_signature': None, 'text': 'what is aleph.im, does someone know?', 'entities': [<telebot.types.MessageEntity object at 0x7f4aa97033d0>], 'caption_entities': None, 'audio': None, 'document': None, 'photo': None, 'sticker': None, 'video': None, 'video_note': None, 'voice': None, 'caption': None, 'contact': None, 'location': None, 'venue': None, 'animation': None, 'dice': None, 'new_chat_member': None, 'new_chat_members': None, 'left_chat_member': None, 'new_chat_title': None, 'new_chat_photo': None, 'delete_chat_photo': None, 'group_chat_created': None, 'supergroup_chat_created': None, 'channel_chat_created': None, 'migrate_to_chat_id': None, 'migrate_from_chat_id': None, 'pinned_message': None, 'invoice': None, 'successful_payment': None, 'connected_website': None, 'reply_markup': None, 'message_thread_id': None, 'is_topic_message': None, 'forum_topic_created': None, 'forum_topic_closed': None, 'forum_topic_reopened': None, 'has_media_spoiler': None, 'forum_topic_edited': None, 'general_forum_topic_hidden': None, 'general_forum_topic_unhidden': None, 'write_access_allowed': None, 'user_shared': None, 'chat_shared': None, 'story': None, 'json': {'message_id': 69, 'from': {'id': 414434471, 'is_bot': False, 'first_name': 'Moshe', 'last_name': 'Malawach [AlephIM]', 'username': 'Jonnyjonnyjon', 'language_code': 'fr', 'is_premium': True}, 'chat': {'id': -4050541508, 'title': 'me testing shit', 'type': 'group', 'all_members_are_administrators': True}, 'date': 1699449497, 'text': 'what is aleph.im, does someone know?', 'entities': [{'offset': 8, 'length': 8, 'type': 'url'}]}}"""


def write_history():
    """Writes the chat history to a file as a json object.
    For each chat only the last 100 messages are stored.
    """
    global HISTORIES
    to_write = {}
    for chat_id, history in HISTORIES.items():
        to_write[str(chat_id)] = [msg.json for msg in history[-100:]]
    with open(LOGS_FILE, "w") as f:
        json.dump(to_write, f)

def read_history():
    """Reads the chat history from a file as a json object.
    """
    global HISTORIES
    try:
        with open(LOGS_FILE, "r") as f:
            HISTORIES = json.load(f)
            for chat_id in HISTORIES.keys():
                HISTORIES[chat_id] = [
                    types.Message.de_json(item) for item in HISTORIES[chat_id]
                ]
    except FileNotFoundError:
        pass


def calculate_number_of_tokens(line):
    return len(line) / 2.7

def get_user_name(user):
    return user.username or (user.first_name + " " + user.last_name)

def prepare_prompt(messages, active_prompt, model, add_persona=True):
    chat_log = ""
    current_tokens = 0
    persona_name = active_prompt['persona_name']

    base_prompt = model['group_base_prompt'].replace("{{char}}", persona_name)\
        .replace("{{room_title}}", messages[-1].chat.title)\
        .replace("{{room_description}}", messages[-1].chat.bio or "")
    prompt_calc = f"{base_prompt}\n{model['log_start']}\n{model['user_prepend']}{persona_name}{model['user_append']}"
    initial_prompt_tokens = calculate_number_of_tokens(prompt_calc)
    max_tokens = model['max_tokens'] - initial_prompt_tokens

    chat_log_lines = []
    seen_info = set()

    for msg in messages:
        name = get_user_name(msg.from_user)
        # check if the message is from our telegram bot
        # if name == bot.get_me().username:
        #     name = persona_name
        # if name == active_prompt.users[0].username:
        #     name = user_name
        # elif name == active_prompt.users[1].username:
        #     name = persona_name
        if (msg.reply_to_message is not None):
            chat_log_lines.append(f"{model['user_prepend']}{name} (in reply to {get_user_name(msg.reply_to_message.from_user)}){model['user_append']}{msg.text}")
        else:
            chat_log_lines.append(f"{model['user_prepend']}{name}{model['user_append']}{msg.text}")

    for line in reversed(chat_log_lines):
        line_tokens = calculate_number_of_tokens(line)

        # matched_entries = find_matches(line)
        # info_tokens = 0
        # info_text = ''
        # for entry in matched_entries:
        #     if entry not in seen_info:
        #         formatted_entry = f"### INFO: {entry}"
        #         info_tokens += calculate_number_of_tokens(formatted_entry)
        #         info_text += f"{formatted_entry}\n"
        #         seen_info.add(entry)

        if (current_tokens + line_tokens) <= max_tokens:
            chat_log = f"{model['line_separator']}{line}\n{chat_log}"
            current_tokens += line_tokens

            # if info_text:
            #     print("adding info text", info_text)
            #     chat_log = f"{info_text}{chat_log}"
            #     current_tokens += info_tokens
        else:
            break
    
    if add_persona:
        return f"{base_prompt}\n{model['log_start']}\n{chat_log}{model['line_separator']}{model['user_prepend']}{persona_name} (in reply to {get_user_name(messages[-1].from_user)}){model['user_append']}"
    else:
        return f"{base_prompt}\n{model['log_start']}\n{chat_log}{model['line_separator']}"

def complete(prompt, model, stop_sequences, length=None):
    print(prompt)
    params = {
        "prompt": prompt,
        "temperature": model['temperature'],
        "top_p": model['top_p'],
        "top_k": model['top_k'],
    }

    if model['engine'] == "kobold":
        params.update({
            "n": 1,
            "max_context_length": model['max_tokens'],
            "max_length": length is None and model['max_length'] or length,
            "rep_pen": 1.08,
            "top_a": 0,
            "typical": 1,
            "tfs": 1,
            "rep_pen_range": 1024,
            "rep_pen_slope": 0.7,
            "sampler_order": model['sampler_order'],
            "quiet": True,
            "stop_sequence": stop_sequences,
            "use_default_badwordsids": False
        })
    elif model['engine'] == "llamacpp":
        print("slot_id", model['slot_id'])
        slot_id = -1 if model['slot_id'] is None else model['slot_id']
        params.update({
            "n_predict": length is None and model['max_length'] or length,
            "slot_id": slot_id,
            "cache_prompt": True,
            "typical_p": 1,
            "tfs_z": 1,
            "stop": stop_sequences,
            "use_default_badwordsids": False
        })
    elif model['engine'] == "openai":
        params.update({
            "n": 1,
            "stop": stop_sequences,
            "max_tokens": length is None and model['max_length'] or length,
        })

    response = requests.post(model['api_url'], json=params, cookies=JAR)

    if response.status_code == 200:
        # Simulate the response (you will need to replace this with actual API response handling)
        response_data = response.json()

        if model['engine'] == "kobold":
            print(response_data)
            return False, response_data['results'][0]['text']
        elif model['engine'] == "llamacpp":
            model['slot_id'] = response_data['slot_id']
            stopped = response_data['stopped_eos'] or response_data['stopped_word']
            return stopped, response_data['content']
        elif model['engine'] == "openai":
            return False, response_data.choices[0]['text']
    else:
        print(f"Error: Request failed with status code {response.status_code}")
        return True, None

def generate_answer(messages, active_prompt, model):
    persona_name = active_prompt['persona_name']
    prompt = prepare_prompt(messages, active_prompt, model)

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
        stopped, last_result = complete(prompt + compounded_result, model, stop_sequences)
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
                to_yield += " **[writing ...]**"

        yield to_yield

def should_answer(messages, active_prompt, model):
    prompt = prepare_prompt(messages, active_prompt, model, add_persona=False)
    prompt = f"{prompt}{model['user_prepend']}"

    stopped, answer = complete(prompt, model, ["YES", "NO"])
    print(answer)
    if answer.startswith(active_prompt['persona_name']) and not answer.strip().endswith("NULL"):
        return True
    else:
        return False


@bot.message_handler(content_types=['text'])
def echo_all(message):
    global last_read_message  # Use the global variable
    if message.chat.type in ['group', 'supergroup']:  # Check if the chat is a group
        chat_id = str(message.chat.id)
        if message.is_topic_message:
            chat_id = str(message.chat.id) + "_" + str(message.message_thread_id)
        if (chat_id not in HISTORIES):
            HISTORIES[chat_id] = []


        if isinstance(message, types.Message):  # Check if it's a real message (ignores edited messages)
            HISTORIES[chat_id].append(message)

            if message.text == "/clear": # and message.from_user.is_admin:
                reply = bot.reply_to(message, "Clearing history.")
                HISTORIES[chat_id] = []
                return

           
            # now we can process the message, using our AI model
            # we will use the last 10 messages as context
            messages = HISTORIES[chat_id][-40:]
            if not should_answer(messages, ACTIVE_PROMPT, ACTIVE_MODEL):
                return
            reply = None
            for result in generate_answer(messages, ACTIVE_PROMPT, ACTIVE_MODEL):
                got_null = (result.strip('\n').strip() == "NULL")
                if got_null: break

                if reply is None:
                    reply = bot.reply_to(message, result)
                else:
                    # update the reply
                    print("updating message")
                    bot.edit_message_text(chat_id=message.chat.id, message_id=reply.message_id, text=result)

            if reply is not None:
                HISTORIES[chat_id].append(reply)
            
            write_history()
    else:
        print(message)

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

if __name__ == '__main__':
    read_history()
    ACTIVE_PROMPT['persona_name'] = bot.get_me().username
    bot.polling()
    write_history()