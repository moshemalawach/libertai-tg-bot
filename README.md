# Telegram Chat Bot

This is a simple Telegram Chat Bot that can be used to send messages to a Telegram group or channel.
It utilizes a Basic AI agent in order to respond to messages sent to the bot.
It works by building up a knowledge base of messages sent to the bot and then using that knowledge base to respond to
messages sent to the bot.
It also implements a function interface for the bot to use in order to respond to messages that require further
information.
It utilizes [Libertai's decentralized LLM API](https://libertai.io/apis/text-generation/) for generating context-aware responses to user queries.

## Requirements
- Python3 + Pip + virtualenv

## Setup

### Configuration

#### Note on Environment Variables

The bot is configured using environment variables.

It is best to do this in a `.env` file at the root of this repository. Our scripts will look for this file and use it to set the environment variables.

You can override these defaults by setting the environment variables in your environment. prior to running the bot.

#### Telegram Bot Token

You must a valid Telegram Bot Token in order to use this bot. You can get one by talking to
the [BotFather](https://t.me/botfather) on Telegram.

Name this variable `TG_TOKEN` within your environment.

#### Logging

The logging is controlled by the `LOG_PATH` environment variable. This is the path to the log file that the bot will write to.

If this is not set, the bot will default to writing logs out to stdout only.

A good default is to set this to `./data/app.log` in the `.env` file.

#### Sqlite Database

The bot uses a sqlite database to store the knowledge base of messages that it has received.

The URL to the database is controlled by the `DATABASE_URL` environment variable.

If this is not set, the bot will default to using `sqlite:///:memory:` which will create an in-memory database that will be lost when the bot is stopped.

A good default is to set this to `sqlite:///./data/app.db` in the `.env` file.

#### Debug Mode

If you want to run the bot in debug mode, you can set the `DEBUG` environment variable to `True`.

This will log events related to LLM completion and other debug information.

#### Agent

The bot uses an AI agent to generate responses to user queries.

See `./agent.yaml` for the default configuration. The bot will load this file and use it to configure the agent when it starts.

If you want to change the agent configuration, you can do so by editing this file or setting the `AGENT_CONFIG_PATH` environment variable to the path of the file you want to use. This file must contain a valid yaml configuration for the agent.

See `./agent.yaml` for the default configuration and documentation on the available options.

## Installation

This command sets up a virtual environment and installs the required dependencies within it for the bot to run.

```
./scripts/install.sh
```

If you would like to run the bot please ensure you use the virtual environment created by the install script.

```
source venv/bin/activate
python3 src/app.py
```

## Usage

### Development

We provide a script to run the bot in development mode. This will run the bot in debug mode, against an in-memory database and write logs to stdout.

```
./scripts/dev.sh
```

Make sure you have a valid Telegram Bot Token set in your environment.

After you have launched the bot, you can search for it on Telegram using its username and start a conversation with it.

### Production-ish

#### Note on Database Migrations

The bot uses an sqlite database to store the knowledge base of messages that it has received.

You can use the `alembic` tool to manage the database schema. We provide scripts for doing so within the virtual environment.

You can run the following command to generate new migrations if you have made changes to the database schema:

```
./scripts/prepare_migrations.sh
```

This will generate a new migration file in the `./alembic/versions` directory.

NOTE: This script is also controlled by the `DATABASE_URL` environment variable. If you do not set this, the script will default to using `sqlite:///./data/app.db` as the database URL.

You can run the following command to apply the migrations to the database:

```
./scripts/migrate.sh
```

This will apply any new migrations to the database.

Like the previous script, this script is also controlled by the `DATABASE_URL` environment variable. If you do not set this, the script will default to using `sqlite:///./data/app.db` as the database URL.

#### Running the Bot

We provide a script to run the bot in production mode. This will deactivate debug mode, and allow you to configure the logging and database URL. If neither of these are set, the bot will default to writing logs to `./data/app.log` and using `sqlite:///./data/app.db` as the database URL.

```
./scripts/run.sh
```