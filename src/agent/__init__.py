import json
import re
import sys
import aiohttp

from telebot import types as telebot_types

from functions import functions as llm_functions
from .utils import calculate_number_of_tokens, fmt_msg_user_name, introspect_function

sys.path.append("..")
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
        with open(agent_config["persona"]["templates"]["private_chat"], "r") as f:
            self.private_chat_template = f.read()
        with open(agent_config["persona"]["templates"]["group_chat"], "r") as f:
            self.group_chat_template = f.read()
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

    async def clear_chat_context(self, chat_id: str):
        """
        Clear the chat context for a given chat
        """
        if chat_id in self.model_chat_slots:
            session, _ = self.model_chat_slots[chat_id]
            await session.close()
            del self.model_chat_slots[chat_id]

    async def build_prompt(
        self,
        database: AsyncDatabase,
        message: telebot_types.Message,
    ) -> str:
        """
        Build a prompt with proper context given the available
        chat history. Try to use as much of the
        history as possible without exceeding the token limit.

        Returns
            A str containing the prompt to be used for the model
        """

        # Keep track of how many tokens we're using
        used_tokens = 0
        # The chat object
        chat = message.chat
        # The Id of the chat
        chat_id = chat.id
        
        # Create a chat prompt to tack on to the end of the context we build
        chat_prompt = self.prompt_chat_message(self.persona_name, "")
        # construct our chat details
        chat_details = self.fmt_chat_details(chat)
        # construct our persona prompt
        persona = (
            self.persona_template.replace("{persona_name}", self.persona_name)
            .replace("{functions}", LLM_FUNCTIONS_DESCRIPTION)
            .replace("{max_function_calls}", str(MAX_FUNCTION_CALLS))
        )
        # determine our reward
        reward = self.reward
        # determine our punishment
        punishment = self.punishment

        # TODO: include /saved documents and definitions within system prompt

        # Construct our system prompt for the model
        system_prompt = (
            self.chat_message(
                # Set this chat message as a system prompt
                "SYSTEM",
                # Include the following, separated by a line separator
                persona
                + self.line_separator
                + f"If you perform well, you will be rewarded. {reward}"
                + self.line_separator
                + f"Otherwise, you will be punished. {punishment}"
                + self.line_separator
                +
                # Important! Example than Chat details
                self.example
                + self.line_separator
                +
                # Include the chat details
                chat_details
                + self.line_separator,
            )
            + self.line_separator
        )

        # Update our used tokens count
        system_prompt_tokens = calculate_number_of_tokens(system_prompt)
        chat_prompt_tokens = calculate_number_of_tokens(chat_prompt)
        used_tokens += system_prompt_tokens + chat_prompt_tokens

        # TODO: refactor s.t.
        #  - make an estimate of how many messages we can pull
        #  - pull that many rows and try saturating our token limit
        #  - repeat as needed
        # Continually pull and format logs from the message history
        # Do so until our token limit is completely used up
        # For now we'll just pull the last 10 messages in batches
        chat_log_lines = []
        # TODO: make this configurable
        batch_size = 10
        offset = 0
        done = False
        # Keep pulling messages until we're done or we've used up all our tokens
        while not done and used_tokens < self.max_tokens:
            # Get `batch_size` messages from the chat history
            messages = await database.get_chat_last_messages(chat_id, batch_size, offset)

            # Construct condition on whether to break due to no more messages
            # If set we won't re-enter the loop
            done = messages is None or len(messages) < batch_size

            # Iterate over the messages we've pulled
            for message in messages:
                from_user_name = fmt_msg_user_name(message.user)
                is_reply = message.reply_to_message is not None

                if is_reply:
                    to_user_name = fmt_msg_user_name(message.reply_to_message.user)
                    line = self.chat_message(
                        f"{from_user_name} (in reply to {to_user_name})", message.text
                    )
                else:
                    line = self.chat_message(from_user_name, message.text)
                line = f"{line}{self.line_separator}"

                # Calculate the number of tokens this line would use
                additional_tokens = calculate_number_of_tokens(line)

                # Break if this would exceed our token limit before appending to the log
                if used_tokens + additional_tokens > self.max_tokens:
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
        chat_prompt_context = system_prompt
        for line in reversed(chat_log_lines):
            chat_prompt_context = f"{chat_prompt_context}{line}"

        # Add the call stack prompt
        chat_prompt = f"{chat_prompt_context}{chat_prompt}"

        # Done! return the formed prompt
        return chat_prompt

    async def complete(
        self, prompt: str, chat_id: str, length=None
    ) -> tuple[bool, str]:
        """
        Complete a prompt with the model

        Returns a tuple of (stopped, result)
        """

        params = {
            "prompt": prompt,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

        # Try to get the appropriate slot for this chat_id if it exists
        if chat_id in self.model_chat_slots:
            session, slot_id = self.model_chat_slots[chat_id]
        else:
            session, slot_id = aiohttp.ClientSession(), -1

        # Update the parameters based on the model engine
        if self.model_engine == "kobold":
            params.update(
                {
                    "n": 1,
                    "max_context_length": self.max_length,
                    "max_length": length is None and self.max_length or length,
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
        elif self.model_engine == "llamacpp":
            params.update(
                {
                    "n_predict": length is None and self.max_length or length,
                    "slot_id": slot_id,
                    "id_slot": slot_id,
                    "cache_prompt": True,
                    "typical_p": 1,
                    "tfs_z": 1,
                    "stop": self.stop_sequences,
                    "use_default_badwordsids": False,
                }
            )
        elif self.model_engine == "openai":
            params.update(
                {
                    "n": 1,
                    "stop": self.stop_sequences,
                    "max_tokens": length is None and self.max_length or length,
                }
            )
        else:
            raise Exception("complete(): unsupported model engine")

        # TODO: handle other engines responses
        # Query the model
        async with session.post(self.model_api_url, json=params) as response:
            if response.status == 200:
                response_data = await response.json()
                return_data = False, ""
                # NOTE: other engines are untested and seem incorrect
                if self.model_engine == "kobold":
                    return_data = False, response_data["results"][0]["text"]

                elif self.model_engine == "llamacpp":
                    if "slot_id" in response_data:
                        slot_id = response_data["slot_id"]
                    elif "id_slot" in response_data:
                        slot_id = response_data["id_slot"]
                    stopped = (
                        response_data["stopped_eos"] or response_data["stopped_word"]
                    )
                    return_data = stopped, response_data["content"]
                    self.model_chat_slots[chat_id] = session, slot_id

                elif self.model_engine == "openai":
                    return_data = False, response_data.choices[0]["text"]

                return return_data
            else:
                raise Exception("Non-200 response from the model: " + response.status)

    async def close_sessions(self):
        """
        Close all open sessions
        """
        for session, _ in self.model_chat_slots.values():
            await session.close()

    async def yield_response(
        self, message: telebot_types.Message, database: AsyncDatabase, logger: Logger
    ):
        """
        Yield a response from the model given the current chat history

        Yields a tuple of ('update' | 'success' | 'error', message)
        """

        # Keep querying the model until we get a qualified response or run out of call depth
        # Build our prompt with the current history and call stack
        chat_id = message.chat.id
        message_id = message.message_id
        prompt = await self.build_prompt(database, message)

        logger.debug(
            f"Constructed prompt: {prompt}",
            chat_id=chat_id,
            message_id=message_id,
        )

        tries = 0
        fn_calls = 0
        compounded_result = ""
        stopped_reason = None

        logger.debug(
            f"Completing on prompt",
            chat_id=chat_id,
            message_id=message_id
        )

        while tries < self.max_tries:
            logger.debug(
                f"Completion attempt: {tries}",
                chat_id=chat_id,
                message_id=message_id
            )
            
            logger.debug(
                f"Compounded result: {compounded_result}",
                chat_id=chat_id,
                message_id=message_id
            )

            # TODO: I really hope we don't break the token limit here -- add proper checks and verify!
            stopped, last_result = await self.complete(
                prompt + compounded_result, chat_id
            )

            logger.debug(
                f"Last result: {last_result}",
                chat_id=chat_id,
                message_id=message_id
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
                clean_result = clean_result.strip("\/n")

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

    def chat_message(self, user: str, message: str) -> str:
        """
        Construct a chat message for the model prompt from the mesage history
        """
        return (
            f"{self.user_prepend}{user}{self.line_separator}{message}{self.user_append}"
        )

    def prompt_chat_message(self, user: str, message: str) -> str:
        """
        Prompt the model to complete a chat message
        """
        return f"{self.user_prepend}{user}{self.line_separator}{message}"

    def fmt_chat_details(self, chat: telebot_types.Chat):
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
        if chat.type in ["private"]:
            return (
                self.private_chat_template.replace(
                    "{user_username}", chat.username or ""
                )
                .replace("{user_first_name}", chat.first_name or "")
                .replace("{user_last_name}", chat.last_name or "")
                .replace("{user_bio}", chat.bio or "")
            )

        elif chat.type in ["group", "supergroup"]:
            return (
                self.group_chat_template.replace("{chat_title}", chat.title or "")
                .replace("{chat_description}", chat.description or "")
                .replace("{chat_members}", chat.active_usernames or "")
            )

        else:
            raise Exception("chat_details(): chat is neither private nor group")
