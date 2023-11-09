from storage import read_history, write_history
HISTORIES = {}

def recover():
    """Recovers the chat history from a file.
    """
    global HISTORIES
    HISTORIES = read_history()

def save():
    """Saves the chat history to a file.
    """
    write_history(HISTORIES)