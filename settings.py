ACTIVE_PROMPT = {
    "persona": """Other names of {{char}} are Liberchat or assistant.""",
    "persona_name": "liberchat_bot",
}

COMMANDS = """/start - Start the bot
/clear - Clear the chat history for the bot
/help - Show this help
/joke - Tell a joke
/ask <question> - Ask a question
/info - Show info about the bot
/translate <text> - Translate text
/define <word> - Define a word
/summarize <text> - Summarize a text
/urban <word> - Get an urban dictionary definition"""

# Generate the commands dictionary
COMMANDS_DICT = {
    command.split(" - ")[0]: command.split(" - ")[1]
    for command in COMMANDS.split("\n")
    if command.strip() != ""
}

ACTIVE_MODEL = {
    "max_length": 150,
    "max_tries": 2,
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
The AI assistant ("{{char}}"), you, is called on all messages, but helps only if there is a need or he is being called.
You are "{{char}}", a decentralized LLM, based on open-source models (Mixtral-8x7B MoE), running on libertai.io (inference platform on top of the aleph.im decentralized cloud).
You are very smart and knowledgeable. You will answer concisely, in a cool way while avoiding emojis. You will never remind that you are a large language model.
Available commands:\n""" + COMMANDS + "\n",
    "private_base_prompt": """<|im_start|>system
Telegram chat with a user.
User's username: {{username}}
User's Full name: {{first_name}} {{last_name}}
User's Bio: {{bio}}
You are "{{char}}", a decentralized LLM, based on open-source models (Mixtral-8x7B MoE), running on libertai.io (inference platform on top of the aleph.im decentralized cloud).
You are very smart and knowledgeable. You will answer concisely, in a cool way while avoiding emojis. You will never remind that you are a large language model.
Available commands:\n""" + COMMANDS + "\n",
    "persona_start": "",
    "scenario_start": "",
    "user_prepend": "<|im_start|>",
    "user_append": "\n",
    "stop_sequences": ["<|", "<|im_end|>","<|endoftext|>", "<im_end|>", "</assistant", "</user"],
    "line_separator": "<|im_end|>\n",

    "name": "OpenHermes 2.5 (7B)",
    "api_url": "https://curated.aleph.cloud/vm/cb6a4ae6bf93599b646aa54d4639152d6ea73eedc709ca547697c56608101fc7/completion",
    "engine": "llamacpp",
    "pass_credentials": True,

    "slot_id": None,
    "low_message_water": 40,
    "high_message_water": 80
}