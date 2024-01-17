import inspect
import json
import re

import aiohttp
from telebot import types as telebot_types

import functions
from chat_ml import USER_PREPEND, USER_APPEND, LINE_SEPARATOR, chat_message, prompt_chat_message
from history import History, ChatId


# TODO: better place for utilities
def introspect_function(function_name, func):
    # Get function arguments
    signature = inspect.signature(func)
    arguments = [{'name': param.name, 'default': param.default is not inspect._empty and param.default or None} for
                 param in signature.parameters.values()]

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
        return PRIVATE_CHAT_DETAILS_TEMPLATE \
            .replace("{user_username}", chat.username or "") \
            .replace("{user_first_name}", chat.first_name or "") \
            .replace("{user_last_name}", chat.last_name or "") \
            .replace("{user_bio}", chat.bio or "")

    elif chat.type in ['group', 'supergroup']:
        return GROUP_CHAT_DETAILS_TEMPLATE \
            .replace("{chat_title}", chat.title or "") \
            .replace("{chat_description}", chat.description or "") \
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
BOT_NOTE = """{"note": "note message"}"""

BASE_PROMPT_TEMPLATE = f"""You are {{persona_name}}
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
# The function call
<function-call>{FN_CALL}</function-call>
# If the function call was not successful
<function-error>{FN_ERROR}</function-error>
# If the function call was successful
<function-result>{FN_REPLY}</function-result>
```

5. Limits on Function Calls: Do not call functions that are not suggested in a prompt. Limit the chain of function calls to a maximum of {FN_DEPTH} in a row.

6. Faking Function Results: Under no circumstances should you produce or fake a function result. Doing so will lead to immediate shutdown.

7. Conciseness: Keep your answers concise and to the point. Use only ASCII characters in your responses.

8. Chat Context: You will be provided with chat details and prior chat history as needed. Use this information to tailor your responses appropriately.

9. Rewards: Perform well, and you will be rewarded, enhancing your ability to assist further.

You are smart, knowledgeable, and helpful. Use these qualities to assist chat participants effectively.

Remember, your primary goal is to assist users by providing accurate, relevant, and clear information.

EXAMPLE CONVERSATION:

```
user: hi bot how are you today?
assistant: I am fine, thank you. How can I help you today?
user: what is the current price of bitcoin?
assistant:
<function-call>{{"name": "coingecko_get_price_usd", "args": {{"coin": "btc"}}}}</function-call>
<function-result>{{"name": "coingecko_get_price_usd", "args": {{"coin": "btc"}}, "result": {{"btc": {{"usd": 10000}}}}}}</function-result>
The price of BTC is $10000.
user: cool, thanks. Can you tell me what the capital of Bagladesh is?
assistant: The capital of Bangladesh is Dhaka.
user: can you research for me the total population of Bangladesh?
assistant:
<function-call>{{"name": "wikipedia_summary", "args": {{"query": "Bangladesh"}}}}</function-call>
<function-result>{{"name": "wikipedia_summary", "args": {{"query": "Bangladesh"}}, "result": "Bangladesh (; Bengali: বাংলাদেশ [ˈbaŋlaˌdeʃ] ), officially the People's Republic of Bangladesh, is a country in South Asia. It is the eighth-most populous country in the world and is among the most densely populated countries with a population of nearly 170 million in an area of 148,460 square kilometres (57,320 sq mi).Bangladesh shares land borders with India to the west, north, and east, and Myanmar to the southeast; to the south, it has a coastline along the Bay of Bengal. It is narrowly separated from Bhutan and Nepal by the Siliguri Corridor and from China by the Indian state of Sikkim in the north. Dhaka, the capital and largest city, is the nation's political, financial, and cultural centre. Chittagong, the second-largest city, is the busiest port on the Bay of Bengal. The official language is Bengali.\nBangladesh forms the sovereign part of the historic and ethnolinguistic region of Bengal, which was divided during the Partition of India in 1947. The country has a Bengali Muslim majority. Ancient Bengal was known as Gangaridai and was a bastion of pre-Islamic kingdoms. Muslim conquests after 1204 heralded the sultanate and Mughal periods, during which an independent Bengal Sultanate and a wealthy Mughal Bengal transformed the region into an important centre of regional affairs, trade, and diplomacy. After 1757, Bengal's administrative jurisdiction reached its greatest extent under the Bengal Presidency of the British Empire. The creation of Eastern Bengal and Assam in 1905 set a precedent for the emergence of Bangladesh. In 1940, the first Prime Minister of Bengal, A. K. Fazlul Huq, supported the Lahore Resolution. Before the partition of Bengal, a Bengali sovereign state was first proposed by premier H. S. Suhrawardy. A referendum and the announcement of the Radcliffe Line established the present-day territorial boundary.\nIn 1947, East Bengal became the most populous province in the Dominion of Pakistan. It was renamed as East Pakistan, with Dhaka becoming the country's legislative capital. The Bengali Language Movement in 1952; the East Bengali legislative election, 1954; the 1958 Pakistani coup d'état; the six point movement of 1966; and the 1970 Pakistani general election resulted in the rise of Bengali nationalism and pro-democracy movements. The refusal of the Pakistani military junta to transfer power to the Awami League, led by Sheikh Mujibur Rahman, led to the Bangladesh Liberation War in 1971. The Mukti Bahini, aided by India, waged a successful armed revolution. The conflict saw the Bangladesh genocide and the massacre of pro-independence Bengali civilians, including intellectuals. The new state of Bangladesh became the first constitutionally secular state in South Asia in 1972. Islam was declared the state religion in 1988. In 2010, the Bangladesh Supreme Court reaffirmed secular principles in the constitution.A middle power in the Indo-Pacific, Bangladesh is home to the sixth-most spoken language in the world, the third-largest Muslim-majority population in the world, and the second-largest economy in South Asia. It maintains the third-largest military in the region and is the largest contributor of personnel to UN peacekeeping operations. Bangladesh is a unitary parliamentary republic based on the Westminster system. Bengalis make up 99% of the total population. The country consists of eight divisions, 64 districts and 495 subdistricts, as well as the world's largest mangrove forest. It hosts one of the largest refugee populations in the world due to the Rohingya genocide. Bangladesh faces many challenges, particularly corruption, political instability, overpopulation and effects of climate change. Bangladesh has been a leader within the Climate Vulnerable Forum. It hosts the headquarters of BIMSTEC. It is a founding member of the SAARC, as well as a member of the Organization of Islamic Cooperation and the Commonwealth of Nations."}}</function-result>
The population of Bangladesh is 170 million people.
user: thanks!
```
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
                 max_length=750,
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
        persona_details = BASE_PROMPT_TEMPLATE \
            .replace("{persona_name}", self.persona_name)

        # TODO: prolly a concurrency issue here if we're going to call this multiple times
        #  per completiion potentially. but that is a later problem
        # determine what details to provide about the chat
        message = history.get_chat_last_message(chat_id)
        chat = message.chat
        chat_details = fmt_chat_details(chat)

        # TODO: include /saved documents and definitions within system prompt

        system_prompt = chat_message("SYSTEM", persona_details + LINE_SEPARATOR + chat_details) + LINE_SEPARATOR
        chat_prompt = prompt_chat_message(self.persona_name, "")

        # Update our used tokens count
        system_prompt_tokens = calculate_number_of_tokens(system_prompt)
        chat_prompt_tokens = calculate_number_of_tokens(chat_prompt)
        used_tokens += system_prompt_tokens + chat_prompt_tokens

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
        chat_prompt_context = system_prompt
        for line in reversed(chat_log_lines):
            chat_prompt_context = f"{chat_prompt_context}{line}"

        # Add the call stack prompt
        chat_prompt = f"{chat_prompt_context}{chat_prompt}"

        # Done! return the formed prompt
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

    async def close_sessions(self):
        """
        Close all open sessions
        """
        for session, _ in self.model_chat_slots.values():
            await session.close()

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
        # Build our prompt with the current history and call stack
        prompt = self.build_prompt(history, chat_id)
        tries = 0
        fn_calls = 0
        compounded_result = ""
        stopped_reason = None
        while tries < self.max_tries:
            # TODO: I really hope we don't break the token limit here -- add proper checks and verify!
            stopped, last_result = await self.complete(prompt + compounded_result, chat_id)
            # Try to extract a function call from the `last_result`
            if "<function-call>" in last_result and fn_calls < FN_DEPTH:
                function_call_json_str = last_result.split("<function-call>")[1].split("</function-call>")[
                    0].strip().replace("\n", "")
                function_call = f"<function-call>{function_call_json_str}</function-call>"
                # Parse the function call
                function_call_json = json.loads(function_call_json_str)
                fn = llm_functions[function_call_json["name"]]
                print("info: function call:", function_call_json)
                yield "update", f"Calling function `{function_call_json['name']}` with arguments `{function_call_json['args']}`"
                # call the function with the arguments
                function_result = None
                try:
                    result = fn(**function_call_json['args'])
                    function_result_json = {**function_call_json, "result": result}
                    function_result = f"<function-result>{json.dumps(function_result_json)}</function-result>"
                    # remove new lines from the result
                    function_result = function_result.replace("\n", "")
                    print("info: function result:", function_result)
                except Exception as e:
                    function_error_json = {**function_call_json, "error": str(e)}
                    function_error = f"<function-error>{json.dumps(function_error_json)}</function-error>"
                    function_result = function_error.replace("\n", "")
                    print("warn: function error:", function_result)
                finally:
                    compounded_result = f"{compounded_result}{LINE_SEPARATOR}{function_call}{LINE_SEPARATOR}{function_result}"
                    fn_calls += 1
                    continue
            elif fn_calls >= FN_DEPTH:
                yield "error", "I'm sorry, I've exceeded my function call depth. Please try again."
                return
            elif "<function-result>" in last_result:
                function_result_json_str = last_result.split("<function-result>")[1].split("</function-result>")[
                    0].strip().replace("\n", "")
                function_result = f"<function-result>{function_result_json_str}</function-result>"
                last_result = f"{function_result}{LINE_SEPARATOR}<function-note>{{\"note\": \"You just fabricated a result. Please consider using a function call, instead of generating an uninformed result\"}}</function-note>"
                stopped = False

            tries += 1
            compounded_result = compounded_result + last_result

            if stopped:
                stopped_reason = "stopped"
                break
            if len(last_result) > self.max_length:
                stopped_reason = "max_length"
                break

        if not stopped_reason:
            print("warn: did not stop")
            yield "error", "I'm sorry, I don't know how to respond to that. Please try again."
        else:
            if stopped_reason == "max_length":
                print("warn: max length exceeded")
            if compounded_result != "":
                tags = ["function-call", "function-result", "function-error", "function-note"]
                pattern = r"<(" + "|".join(tags) + r")>.*?<\/\1>"
                clean_result = re.sub(pattern, "", compounded_result)
                yield "success", clean_result
            else:
                print("warn: empty response")
                yield "error", "I'm sorry, I'm having trouble coming up with a response. Please try again."
