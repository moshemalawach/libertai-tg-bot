import pickle
from telebot import types
from typing import Dict, List

# TODO: find a way to get around having this in memory the whole time
# TODO: implement a way to break up chat histories so we can selectively load / dump them

# Where to read / write the chat history on disk
HISTORY_FILE = "history.pkl"

# TODO: look into whether or not we can just use the chat's int as the chat id, and not have to worry about topics
# Let's air on the side of verbose and opinionated for chat ids
ChatId = str

# NOTE: telegram groups optionally have 'topics'. 
#  These are not given unqiue ids so we interpret chat_ids
#   as strs and append the topic if necessary to provide a unqiue key 
#    in the bot's history
def chat_id_from_message(message: types.Message) -> ChatId:
    """
    Get our internal representation of a message's chat identifier
    from its metadata
    """

    # TODO: messgae thread ids are only for supergroups i think, while topic_messages are for any group
    # but i would think you'd want to include the topic in this!
    # make sure we're doing this correctly
    if message.is_topic_message:
        return str(message.chat.id) + "_" + str(message.message_thread_id)
    else:
        return str(message.chat.id)

# TODO: definitions
# TODO: saved messages
class History():
    """
    An in-memory representation of a chat bot history.
    Tracks total history of all chats connected to the bot.
    """

    # Map of chat_id to chat history
    history = Dict[ChatId, List[types.Message]]

    def __init__(self):
        self.load()

    def dump(self):
        """Writes the chat history to a file.
        """
        with open(HISTORY_FILE, "wb") as f:
            pickle.dump(self.history, f)

    def load(self):
        """Reads the chat history from a file.
        """
        try:
            with open(HISTORY_FILE, "rb") as f:
                self.history = pickle.load(f)
        except FileNotFoundError:
            self.history = {}

    def get_chat_last_message(self, chat_id: ChatId) -> types.Message:
        """Gets the most recent message in the history this message belongs to

        Args:
            message (telebot.types.Message): The message for which we want to get the chat history

        Returns:
            types.Message: the most recent message in the history if available. None if otherwise
        """
        if chat_id in self.history:
            return self.history[chat_id][-1]
        else:
            return None

    def get_chat_nth_last_message(self, chat_id: ChatId, nth: int) -> List[types.Message]:
        """Gets the nth most recent message preceeding the history this message belongs to

        Args:
            message (telebot.types.Message): The message for which we want to get the chat history
            nth (int): integer representing how far back to go

        Returns:
            types.Message: the nth most recent message in the history if available. None if otherwise
        """
      
        # Check if the history is big enough -- avoid wrapping back around
        if nth > len(self.history[chat_id]):
            return None

        # Invert the index to index backwards
        return self.history[chat_id][-nth]

    def clear_chat_history(self, chat_id: ChatId):
        """Clear the chat history preceeding the given message

        Args:
            message (telebot.types.Message): The message for which we want to clear the preceeding chat history
        """
        if chat_id in self.history:
            self.history[chat_id] = []
            self.dump()

    def add_message(self, message: types.Message):
        """Adds a message to its chat's history
        Saves the result to disk

        Args:
            message (types.Message): The message to add to the chat history.
        """
        chat_id = chat_id_from_message(message) 
        if chat_id not in self.history:
            self.history[chat_id] = []
        self.history[chat_id].append(message)
        self.dump()
        return chat_id

    def update_message(self, message: types.Message):
        """Updates a message in its chat's history
        Saves the result to disk

        Args:
            message (types.Message): The message to add to the chat history.
        """
        chat_id = chat_id_from_message(message) 
        if chat_id in self.history:
            for i, msg in enumerate(self.history[chat_id]):
                if msg.message_id == message.message_id:
                    self.history[chat_id][i] = message
                    self.dump()
                    return None
        return None
