import os

from os import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))
import functions
from validator import validate_function_call_schema
from utils import validate_and_extract_tool_calls


class Executor:
    def __init__(self):
        self.tools = functions.get_tools()

    def process_completion_and_validate(self, completion):
        validation, tool_calls, error_message = validate_and_extract_tool_calls(
            completion
        )

        if validation:
            return tool_calls, error_message
        else:
            tool_calls = None
            return tool_calls, error_message

    def execute_function_call(self, tool_call):
        function_name = tool_call.get("name")
        function_to_call = getattr(functions, function_name, None)
        function_args = tool_call.get("arguments", {})

        # NOTE: this should be handled in the validator, but just in case
        if not function_to_call:
            raise ValueError(f"Function {function_name} not found")

        function_response = function_to_call(*function_args.values())
        results_dict = f'{{"name": "{function_name}", "content": {function_response}}}'
        return results_dict

    def handle_completion(self, completion):
        print("Handling completion: ", completion)
        try:
            # NOTE: this used to build up the prompt with recursive calls. For now we'll move that logic to the main agent class
            # def recursive_loop(prompt, completion, depth):
            # nonlocal max_depth
            tool_calls, error_message = self.process_completion_and_validate(completion)
            print("Tool calls: ", tool_calls)
            print("Error message: ", error_message)
            tool_message = ""
            if tool_calls:
                for tool_call in tool_calls:
                    validation, message = validate_function_call_schema(
                        tool_call, self.tools
                    )
                    if validation:
                        try:
                            function_response = self.execute_function_call(tool_call)
                            tool_message += f"<tool_response>\n{function_response}\n</tool_response>\n"
                        except Exception as e:
                            tool_name = tool_call.get("name")
                            tool_message += f"<tool_response>\nThere was an error when executing the function: {tool_name}\nHere's the error traceback: {e}\nPlease call this function again with correct arguments within XML tags <tool_call></tool_call>\n</tool_response>\n"
                    else:
                        tool_name = tool_call.get("name")
                        tool_message += f"<tool_response>\nThere was an error validating function call against function signature: {tool_name}\nHere's the error traceback: {message}\nPlease call this function again with correct arguments within XML tags <tool_call></tool_call>\n</tool_response>\n"
                return tool_message
            elif error_message:
                tool_message += f"<tool_response>\nThere was an error parsing function calls\n Here's the error stack trace: {error_message}\nPlease call the function again with correct syntax<tool_response>"
                return tool_message
            return None
        except Exception as e:
            raise e
