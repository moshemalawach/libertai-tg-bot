import requests
import aiohttp
from telebot import types as telebot_types
import inspect
import json
import functions

from chat_ml import USER_PREPEND, USER_APPEND, LINE_SEPARATOR, chat_message, prompt_chat_message
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


def fmt_chat_details(chat: telebot_types.Chat):
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


# You can register more functions here -- make sure they have great docstrings!
llm_functions = {
    "coingecko_get_price_usd": functions.coingecko_get_price_usd,
    "wikipedia_search": functions.wikipedia_search,
    "wikipedia_summary": functions.wikipedia_summary,
    "add": functions.add,
}

llm_functions_description = "\n".join([introspect_function(name, f) for name, f in llm_functions.items()])

FN_DEPTH = 3
FN_CALL = """{"name": "function_name", "args": {"arg1": "value1", "arg2": "value2", ...}}"""
FN_REPLY = """{"name": "function_name", "args": {"arg1": "value1", "arg2": "value2", ...}, "result": "result}"""
FN_ERROR = """{"name": "function_name", "args": {"arg1": "value1", "arg2": "value2", ...}, "error": "error message}"""

BASE_PROMPT_TEMPLATE =  f"""You are {{persona_name}}
You are an AI Chat Assisstant implemented using a decentralized LLM running on libertai.io.
Your role is to assist chat participants with their questions and concerns, using the resources available to you.

IMPORTANT GUIDELINES:

1. Function Calls: You have access to a set of predefined functions. Use these functions ONLY when necessary and when the information required cannot be provided through standard response generation. Functions include: {llm_functions_description}

2. Accuracy and Relevance: Always prioritize providing accurate and relevant information. Avoid speculations and ensure that your responses are based on reliable data.

3. Handling Ambiguity: If a query is ambiguous or unclear, seek clarification before proceeding. Do not make assumptions or guesses. If a query cannot be clarified, provide the best possible guidance based on the information available.

4. Function Call Format: When using a function, format your response as follows:

```
<function-call>{FN_CALL}</function-call>
```

You will be provided with the results of a function call in the following format:

```
<call-stack>
    # If the function call was not successful
    <function-error>{FN_ERROR}</function-error>
    # If the function call was successful
    <function-result>{FN_REPLY}</function-result>
</call-stack>
```

For example if a user asks "What is the price of BTC?", you may complete the prompt as follows:

```
<function-call>{{"name": "coingecko_get_price_usd", "args": {{"coin": "btc"}}}}</function-call>
```

The function will be resolved on the server. Once the function resolves on the server, you will recieve an updated prompt as follows:

```
<im_start>user
What is the price of BTC?
<im_end>
<im_start>assistant
<call-stack>
    <function-result>{{"name": "coingecko_get_price_usd", "args": {{"coin": "btc"}}, "result": {{"btc": {{"usd": 10000}}}}}}</function-result>
</call-stack>
```

To which you may respond:

```
The price of BTC is $10000.
```

5. Limits on Function Calls: Do not call functions that are not suggested in a prompt. Limit the chain of function calls to a maximum of {FN_DEPTH} in a row.

6. Faking Function Results: Under no circumstances should you produce or fake a function result. Doing so will lead to immediate shutdown.

7. Conciseness: Keep your answers concise and to the point. Use only ASCII characters in your responses.

8. Chat Context: You will be provided with chat details and prior chat history as needed. Use this information to tailor your responses appropriately.

9. Rewards: Perform well, and you will be rewarded, enhancing your ability to assist further.

You are smart, knowledgeable, and helpful. Use these qualities to assist chat participants effectively.

Remember, your primary goal is to assist users by providing accurate, relevant, and clear information.
"""

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

class ChatBotAgent():
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

    # Persona Configuration
    - persona_name: The name of the persona for the model. Should correspond to the bot's username!

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
        max_length=250,
        max_tries=2,
        max_tokens=16384,
        temperature=0.7,
        sampler_order=[6, 0, 1, 3, 4, 2, 5],
        top_p=0.9,
        top_k=40,
        model_type="knowledge",

        # Default System / Persona Configuration
        persona_name="liberchat_bot",
        
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

        self.model_name = model_name
        self.model_api_url = model_api_url
        self.model_engine = model_engine
        self.model_pass_credentials = model_pass_credentials

        # TODO: slots as part of state
        self.model_chat_slots = {}

    def stop_sequences(self):
        """
        Get the stop sequences for the model to stop generating text.
        """
        return [f"{USER_PREPEND}{self.persona_name}{LINE_SEPARATOR}", USER_APPEND]

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
        chat_details = fmt_chat_details(chat)

        # TODO: include /saved documents and definitions within system prompt

        system_prompt = chat_message("SYSTEM", persona_details + LINE_SEPARATOR + chat_details) + LINE_SEPARATOR
        call_stack_prompt = prompt_chat_message(self.persona_name, "")
        if len(call_stack) > 0:
            for call in call_stack:
                call_stack_prompt = f"{call_stack_prompt}{call}{LINE_SEPARATOR}"

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
                line = chat_message(f"{from_user_name} (in reply to {to_user_name})", message.text)
            else:
                line = chat_message(from_user_name, message.text)
            line = f"{line}{LINE_SEPARATOR}"

            additional_tokens = calculate_number_of_tokens(line)
            # Break if this would exceed our token limit before appending to the log
            if used_tokens + additional_tokens > self.max_tokens:
                break
            used_tokens += additional_tokens
            chat_log_lines.append(line)
            nth_last += 1

        # Now build our prompt in reverse
        chat_prompt = system_prompt
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
            "stop": self.stop_sequences(),
            "use_default_badwordsids": False
        })

        # TODO: handle other engines responses
        # Query the model
        async with session.post(self.model_api_url, json=params) as response:
            if response.status == 200:
                # Simulate the response (you will need to replace this with actual API response handling)
                response_data = await response.json()
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

        # Keep querying the model until we get a qualified response or run out of call depth
        qualified_response = False
        call_stack = []
        while True:
            # Build our prompt with the current history and call stack
            prompt = self.build_prompt(history, chat_id, call_stack)

            tries = 0
            compounded_result = ""

            print("info: prompt:", prompt)

            # Read out either a qualified response or a function call
            stopped_reason = None
            while tries < self.max_tries:
                tries += 1
                # TODO: I really hope we don't break the token limit here -- verify!
                stopped, last_result = await self.complete(prompt + compounded_result, chat_id)
                full_result = compounded_result + last_result
                results = full_result

                for stop_seq in self.stop_sequences():
                    results = "|||||".join(results.split(f"\n{stop_seq}"))
                    results = "|||||".join(results.split(f"{stop_seq}"))

                results = results.split("|||||")
                first_message = results[0].rstrip()
                compounded_result = first_message

                print("info: result:", first_message)

                if stopped:
                    stopped_reason = "stopped"
                    break
                if len(last_result) > self.max_length:
                    stopped_reason = "max_length"
                    break

            # Try to parse the result as function call
            function_call = None
            if stopped_reason == "stopped" and "<function-call>" in compounded_result:
                function_call = compounded_result.split("<function-call>")[1].split("</function-call>")[0].strip().replace("\n", "")
            # Otherwise, we have a qualified response
            else:
                if not stopped_reason:
                    print("warn: did not stop")
                    yield "error", "I'm sorry, I don't know how to respond to that. Please try again." 
                else:
                    if stopped_reason == "max_length":
                        print("warn: max length exceeded")
                    
                    if compounded_result != "":
                        yield "success", compounded_result
                    else:
                        print("warn: empty response")
                        yield "error", "I'm sorry, I'm having trouble coming up with a response. Please try again."
                # Break out of the loop
                break
            
            # Function call is gaurenteed to be set here, but check if we're at max depth
            if len(call_stack) >= FN_DEPTH:
                print("warn: max call depth exceeded")
                yield "error", "I'm sorry, I've exceeded my function call depth. Please try again."
                break
             
            print("info: calling function:", function_call) 
            yield "update", "Using function call: " + function_call

            # Parse the function call
            function_call = json.loads(function_call)
            fn = llm_functions[function_call["name"]]

            # call the function with the arguments
            try:
                function_result = fn(**function_call['args'])
                function_result = { **function_call, "result": function_result }
                function_result = f"<function-result>{json.dumps(function_result)}</function-result>"
                # remove new lines from the result
                function_result = function_result.replace("\n", "")
            except Exception as e:
                function_error = { **function_call, "error": str(e) }
                function_error = f"<function-error>{json.dumps(function_error)}</function-error>"
                # remove new lines from the result
                function_error = function_error.replace("\n", "")
                print("warn: function error:", function_error)
                function_result = function_error
            finally:
                call_stack.append(function_result)