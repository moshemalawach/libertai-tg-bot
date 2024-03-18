import json
from os import system
import re
import sys
import aiohttp

from telebot import types as telebot_types

from functions import functions as llm_functions
from .utils import (
    calculate_number_of_tokens,
    fmt_msg_user_name,
    introspect_function,
    fmt_chat_details,
)

sys.path.append("..")
import database
from database import AsyncDatabase
from logger import Logger

# CONSTANTS

LLM_FUNCTIONS_DESCRIPTION = "\n".join(
    [introspect_function(name, f) for name, f in llm_functions.items()]
)
MAX_FUNCTION_CALLS = 3
BOT_NOTE = """{"note": "note message"}"""


# TODO: unclear separation of concerns -- I would really like to find a better way
#  to isolate Chat Histroy from prompt building
class Agent:
    """
    A Chat Bot that generates informed prompts based on the current conversation history.
    """

    def __init__(self, agent_config: dict):
        # Instance Configuration
        self.model_name = agent_config["model"]["name"]
        self.model_api_url = agent_config["model"]["api_url"]
        self.model_engine = agent_config["model"]["engine"]
        self.model_pass_credentials = agent_config["model"]["pass_credentials"]

        # Model Parameters
        self.max_length = agent_config["model"]["max_length"]
        self.max_tries = agent_config["model"]["max_tries"]
        self.max_tokens = agent_config["model"]["max_tokens"]
        self.temperature = agent_config["model"]["temperature"]
        self.sampler_order = agent_config["model"]["sampler_order"]
        self.top_p = agent_config["model"]["top_p"]
        self.top_k = agent_config["model"]["top_k"]
        self.model_type = agent_config["model"]["model_type"]

        # Chat ML Configuration
        self.user_prepend = agent_config["chat_ml"]["user_prepend"]
        self.user_append = agent_config["chat_ml"]["user_append"]
        self.stop_sequences = agent_config["chat_ml"]["stop_sequences"]
        self.line_separator = agent_config["chat_ml"]["line_separator"]

        # Persona Configuration and Templates
        # TODO: better configuration handling for this
        # self.persona_name = agent_config['persona']['name']
        self.persona_name = "chat-bot"
        with open(agent_config["persona"]["templates"]["persona"], "r") as f:
            self.persona_template = f.read()
        with open(agent_config["persona"]["templates"]["example"], "r") as f:
            self.example = f.read()
        with open(agent_config["persona"]["templates"]["reward"], "r") as f:
            self.reward = f.read()
        with open(agent_config["persona"]["templates"]["punishment"], "r") as f:
            self.punishment = f.read()

        # Initialize an empty Map to track open context slots on the server
        self.model_chat_slots = {}

    def set_persona_name(self, name: str):
        """
        Set the persona name for the chat bot
        """
        self.persona_name = name

    async def clear_chat(self, chat_id: str):
        """
        Clear the chat from the model's available context
        """
        if chat_id in self.model_chat_slots:
            session, _ = self.model_chat_slots[chat_id]
            await session.close()
            del self.model_chat_slots[chat_id]

    async def clear_all_chats(self):
        """
        Close all open sessions
        """
        for session, _ in self.model_chat_slots.values():
            await session.close()
        self.model_chat_slots = {}

    ### Prompt Builders and Helpers ###

    def log_chat_message(
        self, message: telebot_types.Message | database.Message
    ) -> str:
        """
        Format a chat Message as a ChatML message

        - message: the message to format -- either a telebot.types.Message or a database.Message
        """

        from_user_name = fmt_msg_user_name(message.from_user)
        is_reply = message.reply_to_message is not None

        sender = from_user_name
        if is_reply:
            to_user_name = fmt_msg_user_name(message.reply_to_message.from_user)
            sender = f"{from_user_name} (in reply to {to_user_name})"
        return f"{self.user_prepend}{sender}{self.line_separator}{message.text}{self.user_append}{self.line_separator}"

    def build_agent_prompt(
        self,
        message: telebot_types.Message | database.Message | None = None,
        text: str = "",
        token_limit: int = 2048,
    ) -> tuple[str, int]:
        """
        Prompt a simple response from the model:
        - message: the message to prompt a response from (optional)
        - text: text to start the model off on (optional)
        - token_limit: the maximum number of tokens the prompt can use

        Returns a tuple of (prompt, used_tokens)
        """

        base = ""
        if message is not None:
            base = self.log_chat_message(message)

        prompt = (
            f"{base}{self.user_prepend}{self.persona_name}{self.line_separator}{text}"
        )

        used_tokens = calculate_number_of_tokens(prompt)

        if used_tokens > token_limit:
            raise Exception("prompt_response(): prompt exceeds token limit")

        return prompt, used_tokens

    async def build_chat_log(
        self,
        database: AsyncDatabase,
        chat: telebot_types.Chat,
        token_limit: int = 2048,
        batch_size: int = 10,
        offset: int = 0,
    ) -> tuple[str, int]:
        """
        Build the most up to date chat context for a given chat's history.
        Mac out at `token_limit` tokens.

        - chat: the chat to build the log for
        - token_limit: the maximum number of tokens the log can use
        - batch_size: the number of messages to pull at a time

        Returns a tuple of (chat_context, used_tokens)
        """

        # Keep track of how many tokens we're using
        used_tokens = 0
        # The Id of the chat
        chat_id = chat.id

        chat_log_lines = []
        offset = 0
        done = False
        # Keep pulling messages until we're done or we've used up all our tokens
        while not done and used_tokens < token_limit:
            # Get `batch_size` messages from the chat history
            messages = await database.get_chat_last_messages(
                chat_id, batch_size, offset
            )

            # Construct condition on whether to break due to no more messages
            # If set we won't re-enter the loop
            done = messages is None or len(messages) < batch_size

            # Iterate over the messages we've pulled
            for message in messages:
                line = self.log_chat_message(message)
                # Calculate the number of tokens this line would use
                additional_tokens = calculate_number_of_tokens(line)

                # Break if this would exceed our token limit before appending to the log
                if used_tokens + additional_tokens > token_limit:
                    done = True
                    # Break out of the for loop.
                    # Since we're 'done' we won't continue the while loop
                    break

                # Update our used tokens count
                used_tokens += additional_tokens

                # Actually append the line to the log
                chat_log_lines.append(line)

            # Update our offset
            offset += batch_size

        # Now build our prompt in reverse
        chat_context = ""
        for line in reversed(chat_log_lines):
            chat_context = f"{chat_context}{line}"

        return chat_context, used_tokens

    def build_system_prompt(
        self,
        chat: telebot_types.Chat,
        token_limit: int = 2048,
    ) -> tuple[str, int]:
        """
        Build a system prompt for the model.
        Utilizes the persona template and chat details in order to prime the model to use a specific persona and chat context.

        - chat: the chat to build the system prompt for
        - token_limit: the maximum number of tokens the prompt can use

        Returns a tuple of (system_prompt, used_tokens)
        """

        # Our SYSTEM prompt consists of:

        # A persona
        persona = (
            self.persona_template.replace("{persona_name}", self.persona_name)
            .replace("{functions}", LLM_FUNCTIONS_DESCRIPTION)
            .replace("{max_function_calls}", str(MAX_FUNCTION_CALLS))
        )
        # Chat details
        chat_details = fmt_chat_details(chat, line_separator=self.line_separator)
        # A reward
        reward = self.reward
        # A punishment
        punishment = self.punishment

        # Put it all together tied together with valid ChatML
        system_prompt = f"{self.user_prepend}SYSTEM{self.line_separator}{persona}{'If you perform well, you will be rewarded. ' + reward + self.line_separator if reward else ''}{'Otherwise, you will be punished. ' + punishment + self.line_separator if punishment else ''}{self.example}{self.line_separator}{chat_details}{self.line_separator}{self.user_append}{self.line_separator}"
        # Update our used tokens count
        used_tokens = calculate_number_of_tokens(system_prompt)

        # Check if we're over our token limit
        if used_tokens > token_limit:
            raise Exception("build_system_prompt(): system prompt exceeds token limit")

        return system_prompt, used_tokens

    async def build_prompt(
        self, message: telebot_types.Message, database: AsyncDatabase
    ) -> str:
        system_prompt, used_tokens = self.build_system_prompt(
            message.chat, token_limit=self.max_tokens
        )

        agent_prompt, _ = self.build_agent_prompt(
            token_limit=self.max_tokens - used_tokens
        )

        chat_log, _ = await self.build_chat_log(
            database, message.chat, token_limit=self.max_tokens - used_tokens
        )

        prompt = f"{system_prompt}{chat_log}{agent_prompt}"

        return prompt

    ### Server Interaction ###

    async def complete(self, prompt: str, chat_id: int) -> tuple[bool, str]:
        """
        Complete a prompt using a given session and slot id.

        Returns a tuple of (stopped, result)
        """

        if chat_id in self.model_chat_slots:
            session, slot_id = self.model_chat_slots[chat_id]
        else:
            session = aiohttp.ClientSession()
            slot_id = -1

        params = {
            "prompt": prompt,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

        # Update the parameters based on the model engine

        # Kobold
        if self.model_engine == "kobold":
            params.update(
                {
                    "n": 1,
                    "max_context_length": 4096,
                    "max_length": self.max_length,
                    "rep_pen": 1.08,
                    "top_a": 0,
                    "typical": 1,
                    "tfs": 1,
                    "rep_pen_range": 1024,
                    "rep_pen_slope": 0.7,
                    "sampler_order": self.sampler_order,
                    "quiet": True,
                    "stop_sequence": self.stop_sequences,
                    "use_default_badwordsids": False,
                }
            )
        # OpenAI
        elif self.model_engine == "openai":
            params.update(
                {
                    "n": 1,
                    "stop": self.stop_sequences,
                    "max_tokens": self.max_length,
                }
            )
        elif self.model_engine == "llamacpp":
            params.update(
                {
                    "n_predict": self.max_length,
                    "id_slot": slot_id,
                    "typical_p": 1,
                    "tfs_z": 1,
                    "stop": self.stop_sequences,
                    "cache_prompt": True,
                    "use_default_badwordsids": False,
                }
            )
        else:
            raise Exception("complete(): unsupported model engine")

        async with session.post(self.model_api_url, json=params) as response:
            if response.status == 200:
                response_data = await response.json()
                return_data = False, ""

                # NOTE: modles other than llamacpp are untested and seem incorrect
                if self.model_engine == "kobold":
                    return_data = False, response_data["results"][0]["text"]
                elif self.model_engine == "openai":
                    return_data = False, response_data.choices[0]["text"]
                # LlamaCPP
                elif self.model_engine == "llamacpp":
                    slot_id = response_data["id_slot"]
                    self.model_chat_slots[chat_id] = session, slot_id
                    stopped = (
                        response_data["stopped_eos"] or response_data["stopped_word"]
                    )
                    return_data = stopped, response_data["content"]

                return return_data
            else:
                raise Exception("Non-200 response from the model: " + response.status)

    ### Response Yielding ###

    # TODO: split out the response yielding from rendering the response
    async def yield_response(
        self, message: telebot_types.Message, database: AsyncDatabase, logger: Logger
    ):
        """
        Yield a response from the agent given it's current state and the message it's responding to.

        Yields a tuple of ('update' | 'success' | 'error', message)
        """

        chat_id = message.chat.id
        message_id = message.message_id

        prompt = await self.build_prompt(message, database)

        logger.debug(
            f"Constructed prompt: {prompt}",
            chat_id=chat_id,
            message_id=message_id,
        )

        tries = 0
        fn_calls = 0
        compounded_result = ""
        stopped_reason = None

        while tries < self.max_tries:
            logger.debug(
                f"Compounded result: {compounded_result}",
                chat_id=chat_id,
                message_id=message_id,
            )

            stopped, last_result = await self.complete(
                prompt + compounded_result, chat_id
            )

            logger.debug(
                f"Last result: {last_result}", chat_id=chat_id, message_id=message_id
            )

            # Try to extract a function call from the `last_result`
            if "<function-call>" in last_result and fn_calls < MAX_FUNCTION_CALLS:
                function_call_json_str = (
                    last_result.split("<function-call>")[1]
                    .split("</function-call>")[0]
                    .strip()
                    .replace("\n", "")
                )
                function_call = (
                    f"<function-call>{function_call_json_str}</function-call>"
                )

                # Parse the function call
                function_call_json = json.loads(function_call_json_str)
                fn = llm_functions[function_call_json["name"]]

                logger.info(
                    f"Calling function `{function_call_json['name']}` with arguments `{function_call_json['args']}`",
                    chat_id=chat_id,
                    message_id=message_id,
                )

                yield (
                    "update",
                    f"Calling function `{function_call_json['name']}` with arguments `{function_call_json['args']}`",
                )
                # call the function with the arguments
                function_result = None
                try:
                    result = fn(**function_call_json["args"])
                    function_result_json = {**function_call_json, "result": result}
                    function_result = f"<function-result>{json.dumps(function_result_json)}</function-result>"
                    # remove new lines from the result
                    function_result = function_result.replace("\n", "")
                    logger.info(
                        f"Function `{function_call_json['name']}` returned `{function_result_json['result']}`",
                        chat_id=chat_id,
                        message_id=message_id,
                    )
                except Exception as e:
                    function_error_json = {**function_call_json, "error": str(e)}
                    function_error = f"<function-error>{json.dumps(function_error_json)}</function-error>"
                    function_result = function_error.replace("\n", "")
                    logger.warn(
                        f"Function `{function_call_json['name']}` raised an error: {str(e)}",
                        chat_id=chat_id,
                        message_id=message_id,
                    )
                finally:
                    compounded_result = f"{compounded_result}{self.line_separator}{function_call}{self.line_separator}{function_result}"
                    fn_calls += 1
                    # Continue to the next iteration without incurring a 'try'
                    continue
            elif fn_calls >= MAX_FUNCTION_CALLS:
                logger.warn(
                    "Function call depth exceeded",
                    chat_id=chat_id,
                    message_id=message_id,
                )
                yield (
                    "error",
                    "I'm sorry, I've exceeded my function call depth. Please try again.",
                )
                return
            elif "<function-result>" in last_result:
                function_result_json_str = (
                    last_result.split("<function-result>")[1]
                    .split("</function-result>")[0]
                    .strip()
                    .replace("\n", "")
                )
                function_result = (
                    f"<function-result>{function_result_json_str}</function-result>"
                )
                last_result = f'{function_result}{self.line_separator}<function-note>{{"note": "You just fabricated a result. Please consider using a function call, instead of generating an uninformed result"}}</function-note>'
                logger.warn(
                    f"fabricated function result: {function_result_json_str}",
                    chat_id=chat_id,
                    message_id=message_id,
                )
                stopped = False
                fn_calls += 1
                continue

            # Note: assuming that the model searches for answers first, then generates a response
            # Ok we're done scraping function calls off the stack
            tries += 1
            results = compounded_result + last_result

            for stop_seq in self.stop_sequences:
                results = "|||||".join(results.split(f"\n{stop_seq}"))
                results = "|||||".join(results.split(f"{stop_seq}"))

            results = results.split("|||||")

            results = results[0].rstrip()
            compounded_result = results
            logger.debug(
                f"Final result: {compounded_result}",
                chat_id=chat_id,
                message_id=message_id,
            )

            if stopped:
                stopped_reason = "stopped"
                break
            if len(last_result) > self.max_length:
                stopped_reason = "max_length"
                break

        if not stopped_reason:
            logger.warn(
                "Failed to stop within max tries",
                chat_id=chat_id,
                message_id=message_id,
            )
            yield (
                "error",
                "I'm sorry, I don't know how to respond to that. Please try again.",
            )
        else:
            if stopped_reason == "max_length":
                logger.warn(
                    "Stopped due to max length",
                    chat_id=chat_id,
                    message_id=message_id,
                )
                yield (
                    "error",
                    "I'm sorry, I'm having trouble coming up with a concise response. Please try again.",
                )
            if compounded_result != "":
                # Clean the final result of any function calls, notes, etc
                tags = [
                    "function-call",
                    "function-result",
                    "function-error",
                    "function-note",
                ]
                pattern = r"<(" + "|".join(tags) + r")>.*?<\/\1>"
                clean_result = re.sub(pattern, "", compounded_result)

                # Strip \n from the front and back of the result
                clean_result = clean_result.strip("\n")

                yield "success", clean_result
            else:
                logger.warn(
                    "Failed to generate a response",
                    chat_id=chat_id,
                    message_id=message_id,
                )
                yield (
                    "error",
                    "I'm sorry, I'm having trouble coming up with a response. Please try again.",
                )
