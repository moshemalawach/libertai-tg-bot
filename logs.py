from storage import read_history, write_history
HISTORIES = {}

def recover():
    """Recovers the chat history from a file.
    """
    for key, value in  read_history().items():
        HISTORIES[key] = value

def save():
    """Saves the chat history to a file.
    """
    write_history(HISTORIES)