# TODO: this doesn't seem like a super pythonic way to do this -- getting used to not having types!
# TODO: also seems like ModelConfig is doing too much 
# (eg shouldn't handle both performance and prompt building)

import requests
import aiohttp
from telebot import types as telebot_types
import inspect
import json

from coin_price import coingecko_get_price_usd
from history import History, ChatId

# TODO: better place for utilities
def introspect_function(function_name, func):

    # Get function arguments
    signature = inspect.signature(func)
    arguments = [{'name': param.name, 'default': param.default is not inspect._empty and param.default or None} for param in signature.parameters.values()]

    # Get function docstring
    docstring = inspect.getdoc(func)

    # Create a dictionary with the gathered information
    function_info = {
        'name': function_name,
        'arguments': arguments,
        'docstring': docstring
    }

    # Convert the dictionary to JSON
    json_result = json.dumps(function_info, indent=2)
    
    return json_result


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
            .replace("{user_username}", chat.username or "")\
            .replace("{user_first_name}", chat.first_name or "")\
            .replace("{user_last_name}", chat.last_name or "")\
            .replace("{user_bio}", chat.bio or "")

    elif chat.type in ['group', 'supergroup']:
        return GROUP_CHAT_DETAILS_TEMPLATE\
            .replace("{chat_title}", chat.title or "")\
            .replace("{chat_description}", chat.description or "")\
            .replace("{chat_members}", chat.active_usernames or "")
    
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


# TODO register more functions -- make sure they have great docstrings!
llm_functions = {
    "coingecko.get_price": coingecko_get_price_usd
}

llm_functions_description = "\n".join([introspect_function(name, f) for name, f in llm_functions.items()])

FN_DEPTH = 3
FN_CALL = """{"name": "function_name", "args": {"arg1": "value1", "arg2": "value2", ...}}"""
FN_REPLY = """{"name": "function_name", "args": {"arg1": "value1", "arg2": "value2", ...}, "result": "result}"""
FN_ERROR = """{"name": "function_name", "args": {"arg1": "value1", "arg2": "value2", ...}, "error": "error message}"""
BASE_PROMPT_TEMPLATE =  f"""You are {{persona_name}}
You are an AI Chat Assisstant implemented using a decentralized LLM running on libertai.io.
You will be provided with details on the chat you are participating in and as much prior relevant chat history as possible.
Use whatever resources are available to you to help address questions and concerns of chat participants.

You are smart, knowledgeable, and helpful.
If you perform well I will give you i
"""
# Base prompt that informs the behavior of the Chat Bot Agent
# BASE_PROMPT_TEMPLATE =  f"""You are {{persona_name}}
# You are an AI Chat Assisstant implemented using a decentralized LLM running on libertai.io.
# You will be provided with details on the chat you are participating in and as much prior relevant chat history as possible.
# Use whatever resources are available to you to help address questions and concerns of chat participants.

# FUNCTION CALLS:

# You also have access to the following tools:
# {llm_functions_description}

# When responding to a message, you may choose to use a function to help you answer the question if you don't know the answer yourself.
# Only use functions that you know are necessary to answer the question.
# You call functions by formatting your response as follows:
# <function-call>{FN_CALL}</function-call>
# Do not include any other text in your response if you are using a function. You will be penalized for each extra token you use outside of the function call.
# After you successfully call a function, you will be provided with the result of the function call appended to the next message you receive.
# Function results are provided in the following format:
# <function-result>{FN_REPLY}</function-result>
# If a function call fails, you will be provided with an error message instead of a result. Your function will be retried up to 3 times before failing.
# Function errors are provided in the following format:
# <function-error>{FN_ERROR}</function-error>
# You are NEVER allowed to call functions that are not provided to you in this prompt.
# You are NEVER allowed to call more than {FN_DEPTH} functions in a row without providing a qualified response.
# If you do so you will be TURNED OFF FOREVER.

# ALL OTHER RESPONSES:

# If you feel you have enough information to answer the question yourself, you may do so.
# You are smart, knowledgeable, and helpful.
# Keep answers concise and only use ASCII characters in your responses.
# In order to denote qualified responses, you must format your response as follows:
# <qualified-response>{{RESPONSE}}</qualified-response>
# You will be penalized for each extra token you use outside of the qualified response.

# Example dialogue:
# `A USER ASKS`

# user: What is the price of the $ALEPH token is USD?

# `INTERNALLY, THE ASSISTANT CALLS THE COINGECKO API`
# <function-call>{{"name": "coingecko.get_price", "args": {{"coin": "aleph"}}}}</function-call>

# `THE ASSISTANT RECIEVES THE UPDATED MESSAGE HISTORY`

# `
# ...

# user: What is the price of the $ALEPH token is USD?

# <function-result>{{"name": "coingecko.get_price", "args": {{"coin": "aleph"}},{{"aleph":{{"usd":0.12831}}}}}}</function-result>
# `

# `TO WHICH THE ASSISTANT RESPONDS`

# assisstant: The price of the $ALEPH token is USD is $0.12831.

# """

# Details needed for managing a private chat
PRIVATE_CHAT_DETAILS_TEMPLATE = """Private Chat Details:
-> user username: {user_username}
-> user full name: {user_first_name} {user_last_name}
-> user bio: {user_bio}
"""

# Details needed for managing a group chat
GROUP_CHAT_DETAILS_TEMPLATE = """Group Chat Details:
-> chat title: {chat_title}
-> chat description: {chat_description}
-> chat members: {chat_members}
"""

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
        persona_name="liberchat_staging_bot",
        
        # TODO: encode the /commands available to the bot
        # TODO: encode the functions available to the bot 
        
        # TODO: re-evaluate whether these should be configurable
        user_prepend="<|im_start|>",
        user_append="\n",
        # TODO: not seeing many of these in the wild -- maybe they're used by other models?
        stop_sequences=["<|", "<|im_end|>","<|endoftext|>", "</assistant", "</user"],
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
        call_stack: list = []
    ) -> [str, str]:
        """
        Build a prompt with proper context given the available
        chat history. Try to use as much of the
        history as possible without exceeding the token limit.

        Args:
            history (history.History): chat history resources available to the model
            chat_id (history.ChatId): the chat id for which to build the prompt
            call_stack (list): the call stack of functions being called by the model. These are either
                strings formatted as FN_REPLY or FN_ERROR.

        Returns
            A str containing the prompt to be used for the model
        """

        # Keep track of how many tokens we're using
        used_tokens = 0

        # Build our system prompt
        
        # construct our base prompt
        persona_details = BASE_PROMPT_TEMPLATE\
            .replace("{persona_name}", self.persona_name)
        
        # TODO: prolly a concurrency issue here if we're going to call this multiple times
        #  per completiion potentially. but that is a later problem
        # determine what details to provide about the chat
        message = history.get_chat_last_message(chat_id)
        chat = message.chat
        chat_details = fmt_chat(chat)

        # TODO: include /saved documents and definitions within system prompt

        # TODO: might not need this extra new line
        system_prompt = f"{self.user_prepend}SYSTEM{self.user_append}{persona_details}{self.user_append}{chat_details}{self.line_separator}"
        call_stack_prompt = ""
        if len(call_stack) > 0:
            call_stack_prompt = f"{self.user_prepend}SYSTEM{self.user_append}Function call stack:\n{self.line_separator.join(call_stack)}{self.line_separator}"

        # Update our used tokens count
        system_prompt_tokens = calculate_number_of_tokens(system_prompt)
        call_stack_prompt_tokens = calculate_number_of_tokens(call_stack_prompt)
        used_tokens += system_prompt_tokens + call_stack_prompt_tokens

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

        # Add the call stack prompt
        chat_prompt = f"{chat_prompt}{call_stack_prompt}"

        # Done! return the formed promtp
        return chat_prompt 

    def set_persona_name(self, persona_name: str):
        """
        Set the persona name for the model
        """
        self.persona_name = persona_name

    async def complete(
        self,
        prompt: str, 
        chat_id: str,
        length=None
    ) -> [bool, str]:
        """
        Complete a prompt with the model

        Returns a tuple of (stopped, result)
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

        # Update the request params
        params.update({
            "n_predict": length is None and self.max_length or length,
            "slot_id": slot_id,
            "cache_prompt": True,
            "typical_p": 1,
            "tfs_z": 1,
            "stop": self.stop_sequences,
            "use_default_badwordsids": False
        })

        # TODO: handle other engines responses
        # Query the model
        async with session.post(self.model_api_url, json=params) as response:
            if response.status == 200:
                # Simulate the response (you will need to replace this with actual API response handling)
                response_data = await response.json()
                print("response_data:", response_data)
                slot_id = response_data['slot_id']
                stopped = response_data['stopped_eos'] or response_data['stopped_word']
                return_data = stopped, response_data['content']

                self.model_chat_slots[chat_id] = session, response_data['slot_id']

                return return_data
            else:
                print(f"Error: Request failed with status code {response.status}")
                return True, None

    async def yield_response(
        self,
        history: History,
        chat_id: ChatId
    ):
        """
        Yield a response from the model given the current chat history

        Yields a tuple of ('update' | 'success' | 'error', message)
        """

        # TODO: how beneficial is yielding here?
        # TODO: proper error raising for these conditions
        # Keep querying the model until we get a qualified response or run out of call depth
        qualified_response = False
        call_stack = []
        while True:
            # Build our prompt with the current history and call stack
            prompt = self.build_prompt(history, chat_id, call_stack)

            print("prompt:", prompt)

            tries = 0
            compounded_result = ""

            # Read out either a qualified response or a function call
            # TODO: enum this maybe
            stopped_reason = None
            while tries < self.max_tries:
                tries += 1
                # TODO: I really hope we don't break the token limit here -- verify!
                stopped, last_result = await self.complete(prompt + compounded_result, chat_id)
                
                # TODO: reevaluate this logic and how needed it is
                full_result = compounded_result + last_result
                results = full_result

                for stop_seq in self.stop_sequences:
                    results = "|||||".join(results.split(f"\n{stop_seq}"))
                    results = "|||||".join(results.split(f"{stop_seq}"))

                results = results.split("|||||")
                first_message = results[0].rstrip()
                compounded_result = first_message

                if stopped:
                    stopped_reason = "stopped"
                    # break
                if len(last_result) > self.max_length:
                    stopped_reason = "max_length"
                    # break

                print("stopped_reason:", stopped_reason)
                print("compounded_result:", compounded_result) 
            # Try to parse the result as function call
            function_call = None
            if stopped_reason == "stopped" and "<function-call>" in compounded_result:
                function_call = compounded_result.split("<function-call>")[1].split("</function-call>")[0]
            else:
                if not stopped_reason:
                    yield "error", "I'm sorry, I'm having trouble understanding you. Please try again."
                elif stopped_reason == "max_length":
                    yield "error", "I'm sorry, I can't respond to that. Please try again."
                elif stopped_reason == "stopped":
                    if "<qualified-response>" in compounded_result:
                        qualified_response = compounded_result.split("<qualified-response>")[1].split("</qualified-response>")[0]
                        yield "success", qualified_response
                    else:
                        yield "error", "I'm sorry, I'm having trouble understanding you. Please try again."
                # Break out of the loop
                break 
            
            # Function call is gaurenteed to be set here, but check if we're at max depth
            if len(call_stack) >= FN_DEPTH:
                yield "error", "I'm sorry, I've exceeded my function call depth. Please try again."
                break
            

            yield "update", "Using function call: " + function_call

            print("function call:", function_call)
            # Parse the function call
            function_call = json.loads(function_call)
            fn = llm_functions[function_call['name']]
            print("calling function:", fn)

            # call the function with the arguments
            try:
                function_result = fn(**function_call['args'])
                function_result = { **function_call, "result": function_result }

                print("function result:", function_result)
            except Exception as e:
                function_error = { **function_call, "error": str(e) }
                print("function error:", function_error)
                function_result = function_error
            
            # Add the function call to the call stack
            call_stack.append(function_result)

