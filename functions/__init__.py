# TODO: functions
# def prepare_completion(messages):

#     completion = client.chat.completions.create(
#         model="openhermes-2.5",
#         messages=messages,
#         max_tokens=150,
#     )


#     # Loading the response as a JSON object
#     print(completion.choices[0])

#     if completion.choices[0].finish_reason == "max_tokens":
#         return completion.choices[0].message.content
#     elif completion.choices[0].finish_reason == "stop":
#         # check if there is a function call
#         if "<function-call>" in completion.choices[0].message.content:
#             # extract the function call
#             fn_call = completion.choices[0].message.content.split("<function-call>")[1].split("</function-call>")[0]
#             print("function call:", fn_call)
#             messages.append(completion.choices[0].message)
#             # parse the function call
#             fn_call = json.loads(fn_call)
#             # get the function
#             fn = functions[fn_call['name']]
#             # call the function with the arguments
#             try:
#                 fn_result = fn(**fn_call['args'])
#                 print("function result:", fn_result)
#             except Exception as e:
#                 print("function error:", e)
#                 fn_result = {"error": str(e)}
#             # check if the result is a generator, if yes cast to a list
#             if isinstance(fn_result, types.GeneratorType):
#                 fn_result = list(fn_result)
#             # we now add a message and call the prepare_completion function again
#             messages.append({"role": "function-result", "content": json.dumps(fn_result)})
#             return prepare_completion(messages)
        
#     return completion

# # messages=[
# #     {"role": "system", "content": SYSTEM},
# #     {"role": "user", "content": "What is the price of the $ALEPH token?"},
# # ]

# # result = prepare_completion(messages)
# # print(result)



# FN_REPLY = """{"name": "function_name", "args": {"arg1": "value1", "arg2": "value2", ...}}}"""

# # TODO register more functions -- make sure they have great docstrings!
# llm_functions = {
#     "coingecko.get_price": coingecko_get_price
# }

# llm_functions_description = "\n".join([introspect_function(name, f) for name, f in functions.items()])

# SYSTEM = f"""You are a helpful assistant with access to the following functions:

# {functions_description}

# To use these functions respond with a function-call, example:
# <function-call>{FN_REPLY}</function-call>

# Edge cases you must handle:
# - If you use a function only use the function call and don't answer the user yet, you will get the function call result as a response then you can answer to the user.
# - If there are no functions that match the user request, try to answer the question yourself (role assistant) but only answer things you know for sure.
# - You can retry function calls if you didn't get a result, but don't retry more than 3 times.

# Example dialogue:
# user: What is the capital of Bengladesh?
# assistant: The capital of Bengladesh is Dhaka.
# user: What is the population of bengladesh?
# assistant: <function-call>{{"name": "wikipedia.summary", "args": {{"title": "bengladesh"}}}}</function-call>
# function-result: {{"summary": "Bangladesh ( (listen); Bengali: বাংলাদেশ, pronounced [ˈbaŋlaˌdeʃ] (listen)), officially the People's Republic of Bangladesh, is a country in South Asia. It is the eighth-most populous country in the world, with a population exceeding 162 million people. In terms of landmass, Bangladesh ranks 92nd, spanning 148,460 square kilometres (57,320 sq mi), making it one of the most densely-populated countries in the world. Bangladesh shares land borders with India to the west, north, and east, Myanmar to the southeast, and the Bay of Bengal to the south. It is narrowly separated from Nepal and Bhutan by the Siliguri Corridor, and from China by Sikkim, in the north, respectively. Dhaka, the capital and largest city, is the nation's economic, political, and cultural hub. Chittagong, the largest seaport, is the second-largest city."}}
# assistant: The population of bengladesh is 162 million people.
# """


# import openai
# import json
# import types

# import requests
# import wikipedia 
# import inspect
# import json
# import duckduckgo_search

# def introspect_function(function_name, func):

#     # Get function arguments
#     signature = inspect.signature(func)
#     arguments = [{'name': param.name, 'default': param.default is not inspect._empty and param.default or None} for param in signature.parameters.values()]

#     # Get function docstring
#     docstring = inspect.getdoc(func)

#     # Create a dictionary with the gathered information
#     function_info = {
#         'name': function_name,
#         'arguments': arguments,
#         'docstring': docstring
#     }

#     # Convert the dictionary to JSON
#     print(function_info)
#     json_result = json.dumps(function_info, indent=2)
    
#     return json_result
