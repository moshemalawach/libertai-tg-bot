from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    create_engine,
    select,
    delete,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm import sessionmaker, relationship, joinedload
from telebot import types as telebot_types
import datetime
import asyncio

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    # NOTE: Api docs says that a username maybe None, but we'll assume that it's always present
    # This will make it more straightforward in enforcing the unique constraint
    username = Column(String, unique=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    language_code = Column(String)
    messages = relationship("Message", back_populates="from_user")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)

    # Chat ID and message ID are unique together
    chat_id = Column(Integer, nullable=False)

    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_user = relationship("User", back_populates="messages")

    reply_to_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    reply_to_message = relationship("Message", remote_side=[id], backref="replies")

    text = Column(String)

    timestamp = Column(DateTime)

    __table_args__ = (UniqueConstraint("id", "chat_id", name="uix_id_chat_id"),)


# Database Initialization and helpers


# Simple Synchronous Database for setting up the database
class SyncDatabase:
    def __init__(self, database_path):
        database_url = f"sqlite:///{database_path}"
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)


class AsyncDatabase:
    def __init__(self, database_path):
        database_url = f"sqlite+aiosqlite:///{database_path}"
        self.engine = create_async_engine(database_url)
        self.AsyncSession = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )
        # If this is an in-memory database, we need to create the tables
        if database_path == ":memory:":
            asyncio.run(self.create_tables())

    async def create_tables(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def add_message(
        self, message: telebot_types.Message, edited=False, reply_to_message_id=None
    ):
        async with self.AsyncSession() as session:
            async with session.begin():
                user = await session.execute(
                    select(User).filter(User.username == message.from_user.username)
                )
                user = user.scalars().first()
                if not user:
                    user = User(
                        id=message.from_user.id,
                        username=message.from_user.username,
                        first_name=message.from_user.first_name,
                        last_name=message.from_user.last_name,
                        language_code=message.from_user.language_code,
                    )
                    session.add(user)

                reply_to_id = reply_to_message_id or (
                    message.reply_to_message.message_id
                    if message.reply_to_message
                    else None
                )
                new_message = Message(
                    id=message.message_id,
                    chat_id=message.chat.id,
                    from_user_id=user.id,
                    reply_to_message_id=reply_to_id,
                    text=message.text,
                    timestamp=datetime.datetime.fromtimestamp(
                        message.edit_date if edited else message.date
                    ),
                )
                session.add(new_message)

    async def update_message_text(self, message_id, new_text):
        async with self.AsyncSession() as session:
            async with session.begin():
                db_message = await session.execute(
                    select(Message).filter(Message.id == message_id)
                )
                db_message = db_message.scalars().first()
                if db_message:
                    db_message.text = new_text

    async def get_chat_last_messages(self, chat_id, limit=10, offset=0):
        async with self.AsyncSession() as session:
            result = await session.execute(
                select(Message)
                .options(joinedload(Message.from_user))
                .options(
                    joinedload(Message.reply_to_message).joinedload(Message.from_user)
                )
                .where(Message.chat_id == chat_id)
                .order_by(Message.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )

            messages = result.scalars().all()

            return messages

    async def clear_chat_history(self, chat_id):
        async with self.AsyncSession() as session:
            async with session.begin():
                await session.execute(delete(Message).where(Message.chat_id == chat_id))
