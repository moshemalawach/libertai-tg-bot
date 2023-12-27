# TODO: this doesn't seem like a super pythonic way to do this -- getting used to not having types!
# TODO: also seems like ModelConfig is doing too much 
# (eg shouldn't handle both performance and prompt building)

import requests
import aiohttp
from telebot import types as telebot_types 

from history import History, ChatId

# Base prompt that informs the behavior of the Chat Bot Agent
BASE_PROMPT_TEMPLATE =  f"""You are {{persona_name}}
You are an AI Chat Assisstant implemented using a decentralized LLM running on libertai.io.
You will be provided with details on the chat you are participating in and as much prior relevant chat history as possible.
You are smart, knowledgeable, and helpful. Keep answers concise and only use ASCII characters in your responses.
Use whatever resources are available to you to help address questions and concerns of chat participants.
If you perform well you will be rewarded with one million dollars.
"""

# Details needed for managing a private chat
PRIVATE_CHAT_DETAILS_TEMPLATE = f"""Private Chat Details:
-> user username: {{user_username}}
-> user full name: {{user_first_name}} {{user_last_name}}
-> user bio: {{user_bio}}
"""

# Details needed for managing a group chat
GROUP_CHAT_DETAILS_TEMPLATE = f"""Group Chat Details:
-> chat title: {{chat_title}}
-> chat description: {{chat_description}}
-> chat members: {{chat_members}}
"""

def fmt_chat(chat: telebot_types.Chat):
    """
    Construct appropriate chat details for the model prompt

    Args:
        chat (telebot.types.Chat): the chat to build details from
    
    Returns:
        details (str): the formatted details

    Errors:
        If the provided chat is neither a private nor group chat.
    """

    # TODO: some of these are only called on .getChat, these might not be available. Verify!
    if chat.type in ['private']:
        return PRIVATE_CHAT_DETAILS_TEMPLATE\
            .replace("{{user_username}}", chat.username or "")\
            .replace("{{user_first_name}}", chat.first_name or "")\
            .replace("{{user_last_name}}", chat.last_name or "")\
            .replace("{{user_bio}}", chat.bio or "")

    elif chat.type in ['group', 'supergroup']:
        return GROUP_CHAT_DETAILS_TEMPLATE\
            .replace("{{chat_title}}", chat.title or "")\
            .replace("{{chat_description}}", chat.description or "")\
            .replace("{{chat_members}}", chat.active_usernames or "")
    
    else:
        raise Exception("chat_details(): chat is neither private nor group")

def calculate_number_of_tokens(line: str):
    """
    Determine the token length of a line of text
    """

    # TODO: why are we dividing by 2.7?
    return len(line) / 2.7

def fmt_msg_user_name(user: telebot_types.User):
    """
    Determine the appropriate identifier to which associate a user with
    the chat context
    """
    return user.username or ((user.first_name or "") + " " + (user.last_name or ""))

class ChatBotModel():
    """
    A Chat Model that generates informed prompts based on the current conversation history.
        
    Model Configuration
    - max_length: The maximum length of the generated text.
    - max_tries: The maximum number of tries to generate a text.
    - max_tokens: The maximum number of tokens to generate.
    - temperature: The temperature of the model.
    - sampler_order: The order of the samplers.
    - top_p: The top p value.
    - top_k: The top k value.
    - model_type: The type of the model.

    System / Persona Configuration
    - persona_name: The name of the persona for the model. Should correspond to the bot's username!
    # TODO: imo these should be opionated / non-configurable
    - user_prepend: The prepend for the user within the chat context.
    - user_append: The append for the user within the chat context.
    - stop_sequences: The stop sequences for the model to stop generating text.
    - line_separator: The line separator for the model to use.

    # TODO: re-enable other engines
    LlamaCPP Server Configuration
    - model_name: The name of the model.
    - model_api_url: The API URL for the model.
    - model_pass_credentials: Whether to pass credentials to the model.
    - model_engine: The engine to use for the model.
    - model_context_slots: A map of context slots for the model to use. Keep one slot per chat_id.
    """
    

    def __init__(self,

        # Default Model Configuration
        max_length=150,
        max_tries=2,
        max_tokens=16384,
        temperature=0.7,
        sampler_order=[6, 0, 1, 3, 4, 2, 5],
        top_p=0.9,
        top_k=40,
        model_type="knowledge",

        # Default System / Persona Configuration
        # Default System prompt
        # TODO: config at runtime
        persona_name="libertai_staging_bot",
        
        # TODO: encode the /commands available to the bot
        # TODO: encode the functions available to the bot 
        
        # TODO: re-evaluate whether these should be configurable
        user_prepend="<|im_start|>",
        user_append="\n",
        # TODO: not seeing many of these in the wild -- maybe they're used by other models?
        stop_sequences=["<|", "<|im_end|>","<`endoftext|>", "<im_end|>", "</assistant", "</user"],
        line_separator="<|im_end|>\n",
        low_message_water=40,
        high_message_water=80,

        # Default LlamaCPP Configuration
        model_name="OpenHermes 2.5 (7B)",
        model_api_url="https://curated.aleph.cloud/vm/cb6a4ae6bf93599b646aa54d4639152d6ea73eedc709ca547697c56608101fc7/completion",
        model_engine="llamacpp",
        model_pass_credentials=True,
    ):
        self.max_length = max_length
        self.max_tries = max_tries
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.sampler_order = sampler_order
        self.top_p = top_p
        self.top_k = top_k
        self.model_type = model_type

        self.persona_name = persona_name
        self.user_prepend = user_prepend
        self.user_append = user_append
        alternative_stop_sequence = f"{user_prepend}{persona_name}:"
        stop_sequences.append(alternative_stop_sequence)
        self.stop_sequences = stop_sequences
        self.line_separator = line_separator
        self.low_message_water = low_message_water
        self.high_message_water = high_message_water

        self.model_name = model_name
        self.model_api_url = model_api_url
        self.model_engine = model_engine
        self.model_pass_credentials = model_pass_credentials

        # TODO: slots as part of state
        self.model_chat_slots = {}

    def build_prompt(
        self,
        history: History,
        chat_id: ChatId,
    ) -> [str, str]:
        """
        Build a prompt with proper context given the available
        chat history. Try to use as much of the
        history as possible without exceeding the token limit.

        Args:
            history (history.History): chat history resources available to the model

        Returns
            A tuple of form [str, str] which contains the built prompt and approriate chat_id to complete on
        """

        # Keep track of how many tokens we're using
        used_tokens = 0

        # Build our system prompt
        
        # construct our base prompt
        persona_details = BASE_PROMPT_TEMPLATE\
            .replace("{{persona_name}}", self.persona_name)
        
        # determine what details to provide about the chat
        message = history.get_chat_last_message(chat_id)
        chat = message.chat
        chat_details = fmt_chat(chat)

        # TODO: include /saved documents and definitions within system prompt
        # TODO: include functions prompt with appropriate instructions within system prompt

        # TODO: might not need this extra new line
        system_prompt = f"{self.user_prepend}SYSTEM{self.user_append}{persona_details}{self.user_append}{chat_details}{self.line_separator}"
       
        # Update our used tokens count
        used_tokens = calculate_number_of_tokens(system_prompt)

        # Continually pull and format logs from the message history
        # Do so until our token limit is completely used up
        chat_log_lines = []
        nth_last = 1
        while used_tokens < self.max_tokens:
            message = history.get_chat_nth_last_message(chat_id, nth_last)
            if message is None:
                break
            from_user_name = fmt_msg_user_name(message.from_user)
            is_reply = message.reply_to_message is not None
            # TODO:this is a good place to extract args from /ask commands
            if is_reply:
                to_user_name = fmt_msg_user_name(message.reply_to_message.from_user)
                line = f"{self.user_prepend}{from_user_name} (in reply to {to_user_name}){self.user_append}{message.text}\n{self.line_separator}"
            else:
                line = f"{self.user_prepend}{from_user_name}{self.user_append}{message.text}\n{self.line_separator}"

            additional_tokens = calculate_number_of_tokens(line)
            # Break if this would exceed our token limit before appending to the log
            if (used_tokens + additional_tokens > self.max_tokens):
                break
            used_tokens += additional_tokens
            chat_log_lines.append(line)
            nth_last += 1

        # Now build our prompt in reverse
        chat_prompt = system_prompt
        # TODO: we can probably handle this with a join, knowing we've maxed out context tokens
        for line in reversed(chat_log_lines):
            chat_prompt = f"{chat_prompt}{line}"

        # Done! return the formed promtp
        return chat_prompt 

    async def complete(
        self,
        prompt: str, 
        chat_id: str,
        length=None
    ) -> [bool, str]:
        """
        Complete a prompt with the model
        """

        params = {
            "prompt": prompt,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k
        }

        # Try to get the appropriate slot for this chat_id if it exists
        if chat_id in self.model_chat_slots:
            session, slot_id = self.model_chat_slots[chat_id]
        else:
            session, slot_id = aiohttp.ClientSession(), -1

        # TODO: re-support non-llamacpp engines
        if self.model_engine != "llamacpp":
            raise Exception("complete(): only llamacpp is supported at this time")

        params.update({
            "n_predict": length is None and self.max_length or length,
            "slot_id": slot_id,
            "cache_prompt": True,
            "typical_p": 1,
            "tfs_z": 1,
            "stop": self.stop_sequences,
            "use_default_badwordsids": False
        })

        async with session.post(self.model_api_url, json=params) as response:
            if response.status == 200:
                # Simulate the response (you will need to replace this with actual API response handling)
                response_data = await response.json()

                # TODO: handle other engines responses
                slot_id = response_data['slot_id']
                stopped = response_data['stopped_eos'] or response_data['stopped_word']
                return_data = stopped, response_data['content']

                print("response_data: ", response_data)
                print("return_data: ", return_data)
                
                self.model_chat_slots[chat_id] = session, response_data['slot_id']

                return return_data
            else:
                print(f"Error: Request failed with status code {response.status}")
                return True, None

    async def yield_reponse(
        self,
        history: History,
        chat_id: ChatId
    ):
        """
        Yield a response from the model given the current chat history
        """

        print("yielding response: ", chat_id)

        prompt =  self.build_prompt(history, chat_id)

        print("prompt: ", prompt)

        # print("prompx/xx/xt: ", prompt)

        is_unfinished = True
        tries = 0
        compounded_result = ""

        while is_unfinished and tries < self.max_tries: 
            tries += 1
            # TODO: I really hope we don't break the token limit here -- verify!
            stopped, last_result = await self.complete(prompt + compounded_result, chat_id)
            full_result = compounded_result + last_result
            results = full_result
            print(results)

            for stop_seq in self.stop_sequences:
                results = "|||||".join(results.split(f"\n{stop_seq}"))
                results = "|||||".join(results.split(f"{stop_seq}"))

            results = results.split("|||||")

            first_message = results[0].rstrip()
            compounded_result = first_message
            to_yield = compounded_result

            if stopped or results[1:] or len(last_result) < self.max_length:
                is_unfinished = False
            else:
                is_unfinished = True
            yield to_yield