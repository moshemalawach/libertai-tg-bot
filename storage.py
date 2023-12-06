import json
from telebot import types

LOGS_FILE = "logs.json"

def write_history(histories):
    """Writes the chat history to a file as a json object.
    """
    to_write = {}
    for chat_id, history in histories.items():
        to_write[str(chat_id)] = [msg.json for msg in history]
    with open(LOGS_FILE, "w") as f:
        json.dump(to_write, f)

def read_history():
    """Reads the chat history from a file as a json object.
    """
    try:
        histories = {}
        with open(LOGS_FILE, "r") as f:
            histories = json.load(f)
            for chat_id in histories.keys():
                print(chat_id, len(histories[chat_id]))
                histories[chat_id] = [
                    types.Message.de_json(item) for item in histories[chat_id]
                ]
        return histories
    except FileNotFoundError:
        return {}