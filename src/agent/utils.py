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

def introspect_function(function_name, func):
    '''
    Introspect a function and return a JSON representation of it
    '''
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

    # NOTE (amiller68): I removed an indent here -- I think that's fine but leaving a note until i test
    # Convert the dictionary to JSON
    json_result = json.dumps(function_info)

    return json_result