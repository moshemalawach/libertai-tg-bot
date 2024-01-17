USER_PREPEND = "<|im_begin|>"
USER_APPEND = "<|im_end|>"
LINE_SEPARATOR = "\n"


def chat_message(user: str, message: str) -> str:
    return f"{USER_PREPEND}{user}{LINE_SEPARATOR}{message}{LINE_SEPARATOR}{USER_APPEND}"


def prompt_chat_message(user: str, message: str) -> str:
    return f"{USER_PREPEND}{user}{LINE_SEPARATOR}{message}"
