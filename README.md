# Libertai Telegram Chat Bot

This is a simple Telegram Chat Bot that can be used to send messages to a Telegram group or channel.
It utilizes a Basic AI agent in order to respond to messages sent to the bot.
It works by building up a knowledge base of messages sent to the bot and then using that knowledge base to respond to
messages sent to the bot.
It also implements a function interface for the bot to use in order to respond to messages that require further
information.

## Installation

```
pip install -r requirements.txt
```

## Setup

You must a valid Telegram Bot Token in order to use this bot. You can get one by talking to
the [BotFather](https://t.me/botfather) on Telegram.

After you have obtained a token, you must export a variable called `TG_TOKEN` with the token as the value at runtime.

## Usage

You can launch the bot by running the following command:

```
python main.py
```

The bot should be available on Telegram after you have launched it.

For example if you're bot is named `liberchat_bot` you can search for it on Telegram and start a conversation with it.
Just open:

```
https://t.me/liberchat_bot
```

## TODO

[ ] - term definition

[ ] - message indexing

[ ] - split out chatml configuration, model tuning, and prompt building into seperate modules