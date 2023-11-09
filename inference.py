import requests

JAR = requests.cookies.RequestsCookieJar()
SLOTS = {}

def calculate_number_of_tokens(line):
    return len(line) / 2.7

def get_user_name(user):
    return user.username or (user.first_name + " " + user.last_name)

def prepare_prompt(messages, active_prompt, model, add_persona=True, chat=None):
    chat_log = ""
    current_tokens = 0
    persona_name = active_prompt['persona_name']

    if chat is None:
        chat = messages[-1].chat

    if chat.type == "private":
        base_prompt = model['private_base_prompt'].replace("{{char}}", persona_name)\
            .replace("{{username}}", chat.username or "")\
            .replace("{{first_name}}", chat.first_name or "")\
            .replace("{{last_name}}", chat.last_name or "")\
            .replace("{{bio}}", chat.bio or "")
    else:
        base_prompt = model['group_base_prompt'].replace("{{char}}", persona_name)\
            .replace("{{room_title}}", chat.title or "")\
            .replace("{{room_description}}", chat.description or "")
    prompt_calc = f"{base_prompt}\n{model['log_start']}\n{model['user_prepend']}{persona_name}{model['user_append']}"
    initial_prompt_tokens = calculate_number_of_tokens(prompt_calc)
    max_tokens = model['max_tokens'] - initial_prompt_tokens

    chat_log_lines = []
    seen_info = set()

    for msg in messages:
        name = get_user_name(msg.from_user)
        # check if the message is from our telegram bot
        # if name == bot.get_me().username:
        #     name = persona_name
        # if name == active_prompt.users[0].username:
        #     name = user_name
        # elif name == active_prompt.users[1].username:
        #     name = persona_name
        if (msg.reply_to_message is not None):
            chat_log_lines.append(f"{model['user_prepend']}{name} (in reply to {get_user_name(msg.reply_to_message.from_user)}){model['user_append']}{msg.text}")
        else:
            chat_log_lines.append(f"{model['user_prepend']}{name}{model['user_append']}{msg.text}")

    for line in reversed(chat_log_lines):
        line_tokens = calculate_number_of_tokens(line)

        # matched_entries = find_matches(line)
        # info_tokens = 0
        # info_text = ''
        # for entry in matched_entries:
        #     if entry not in seen_info:
        #         formatted_entry = f"### INFO: {entry}"
        #         info_tokens += calculate_number_of_tokens(formatted_entry)
        #         info_text += f"{formatted_entry}\n"
        #         seen_info.add(entry)

        if (current_tokens + line_tokens) <= max_tokens:
            chat_log = f"{model['line_separator']}{line}\n{chat_log}"
            current_tokens += line_tokens

            # if info_text:
            #     print("adding info text", info_text)
            #     chat_log = f"{info_text}{chat_log}"
            #     current_tokens += info_tokens
        else:
            break
    
    if add_persona:
        return f"{base_prompt}\n{model['log_start']}\n{chat_log}{model['line_separator']}{model['user_prepend']}{persona_name} (in reply to {get_user_name(messages[-1].from_user)}){model['user_append']}"
    else:
        return f"{base_prompt}\n{model['log_start']}\n{chat_log}{model['line_separator']}"

def complete(prompt, model, stop_sequences, length=None, chat_id="0"):
    print(prompt)
    params = {
        "prompt": prompt,
        "temperature": model['temperature'],
        "top_p": model['top_p'],
        "top_k": model['top_k'],
    }

    if model['engine'] == "kobold":
        params.update({
            "n": 1,
            "max_context_length": model['max_tokens'],
            "max_length": length is None and model['max_length'] or length,
            "rep_pen": 1.08,
            "top_a": 0,
            "typical": 1,
            "tfs": 1,
            "rep_pen_range": 1024,
            "rep_pen_slope": 0.7,
            "sampler_order": model['sampler_order'],
            "quiet": True,
            "stop_sequence": stop_sequences,
            "use_default_badwordsids": False
        })
    elif model['engine'] == "llamacpp":
        if chat_id in SLOTS:
            slot_id = SLOTS[chat_id]
        else:
            slot_id = -1
            
        print("slot_id", slot_id)
        # slot_id = model['slot_id'] is None and -1 or model['slot_id']
        params.update({
            "n_predict": length is None and model['max_length'] or length,
            "slot_id": slot_id,
            "cache_prompt": True,
            "typical_p": 1,
            "tfs_z": 1,
            "stop": stop_sequences,
            "use_default_badwordsids": False
        })
    elif model['engine'] == "openai":
        params.update({
            "n": 1,
            "stop": stop_sequences,
            "max_tokens": length is None and model['max_length'] or length,
        })

    response = requests.post(model['api_url'], json=params, cookies=JAR)

    if response.status_code == 200:
        # Simulate the response (you will need to replace this with actual API response handling)
        response_data = response.json()

        if model['engine'] == "kobold":
            print(response_data)
            return False, response_data['results'][0]['text']
        elif model['engine'] == "llamacpp":
            # model['slot_id'] = response_data['slot_id']
            SLOTS[chat_id] = response_data['slot_id']
            stopped = response_data['stopped_eos'] or response_data['stopped_word']
            return stopped, response_data['content']
        elif model['engine'] == "openai":
            return False, response_data.choices[0]['text']
    else:
        print(f"Error: Request failed with status code {response.status_code}")
        return True, None

