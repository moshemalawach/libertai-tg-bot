import re
import json
import ast
import xml.etree.ElementTree as ET

def extract_json_from_markdown(text):
    """
    Extracts the JSON string from the given text using a regular expression pattern.
    
    Args:
        text (str): The input text containing the JSON string.
        
    Returns:
        dict: The JSON data loaded from the extracted string, or None if the JSON string is not found.
    """
    json_pattern = r'```json\r?\n(.*?)\r?\n```'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        json_string = match.group(1)
        try:
            data = json.loads(json_string)
            return data
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON string: {e}")
    else:
        print("JSON string not found in the text.")
    return None

def validate_and_extract_tool_calls(agent_response):
    validation_result = False
    tool_calls = []
    error_message = None

    try:
        print("Agent response: ", agent_response)
        # wrap content in root element
        xml_root_element = f"<root>{agent_response}</root>"
        print("XML root element: ", xml_root_element)
        root = ET.fromstring(xml_root_element)
        print("XML root: ", root)

        # extract JSON data
        for element in root.findall(".//tool_call"):
            print("Tool call element: ", element)
            json_data = None
            try:
                json_text = element.text.strip()

                print("JSON text: ", json_text)
                try:
                    # Prioritize json.loads for better error handling
                    json_data = json.loads(json_text)
                    print("JSON data: ", json_data)
                except json.JSONDecodeError as json_err:
                    try:
                        # Fallback to ast.literal_eval if json.loads fails
                        json_data = ast.literal_eval(json_text)
                        print("JSON data (fallback): ", json_data)
                    except (SyntaxError, ValueError) as eval_err:
                        error_message = f"JSON parsing failed with both json.loads and ast.literal_eval:\n"\
                                        f"- JSON Decode Error: {json_err}\n"\
                                        f"- Fallback Syntax/Value Error: {eval_err}\n"\
                                        f"- Problematic JSON text: {json_text}"
                        continue
            except Exception as e:
                error_message = f"Cannot strip text: {e}"

            if json_data is not None:
                tool_calls.append(json_data)
                validation_result = True

    except ET.ParseError as err:
        error_message = f"XML Parse Error: {err}"

    # Return default values if no valid data is extracted
    return validation_result, tool_calls, error_message