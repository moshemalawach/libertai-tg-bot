# Libertai Telegram Chat Bot

This is a simple Telegram Chat Bot that can be used to send messages to a Telegram group or channel.
It utilizes a Basic AI agent in order to respond to messages sent to the bot.
It works by building up a knowledge base of messages sent to the bot and then using that knowledge base to respond to
messages sent to the bot.
It also implements a function interface for the bot to use in order to respond to messages that require further
information.

## Requirements
- Python3 + Pip3

## Installation

```
./install.sh
```

## Setup

You must a valid Telegram Bot Token in order to use this bot. You can get one by talking to
the [BotFather](https://t.me/botfather) on Telegram.

After you have obtained a token, you must export a variable called `TG_TOKEN` with the token as the value at runtime.

## Configuration

See config.yml for the default configuration.

Templates for bot prompts and responses are stored in the `templates` directory.

Available templates are:

- 'private_chat': How you wish to format details of a private chat.
- 'group_chat': How you wish to format details of a group chat.
- 'persona': What behavior you want the bot to exhibit. THe default is designed to make function calls to the bot function, make sure you understand the implications of changing this.
- 'reward': How you want to 'reward' the bot for good behavior.
- 'punishment': How you want to 'punish' the bot for bad behavior.
- 'example': An example of an exchange between the bot and a user.

## Usage

You can launch the bot in debug mode by running the following command:

```
./dev.sh
```

The bot should be available on Telegram after you have launched it.

For example if you bot is named `liberchat_bot` you can search for it on Telegram and start a conversation with it.
Just open:

```
https://t.me/liberchat_bot
```

You will see logs appear in the terminal where you launched the bot.

In order to use the bot in a production environment, you can run the following command:

```
./run.sh
```

This will divert logs to ./data/app.log if you're using the default configuration.

You can wrap this script in a service in order to run the bot in the background. For now the service must be running in the same directory as this repository.