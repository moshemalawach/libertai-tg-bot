from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm import sessionmaker, relationship, joinedload
from telebot import types as telebot_types
import datetime

Base = declarative_base()

# NOTE: for now all it seems like we need is User and Message data
# I could add 'Chat', but we never need or pull that from history
# Model Declarations
# NOTE: now that we don't just marshal json, I am concerned about invariants that occur
# due to ordering in how users get added to the database. This is a future concern for now


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    # NOTE: Api docs says that a username maybe None, but we'll assume that it's always present
    # This will make it more straightforward in enforcing the unique constraint
    username = Column(String, unique=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    language_code = Column(String)
    messages = relationship("Message", back_populates="user")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)

    # Chat ID and message ID are unique together
    chat_id = Column(Integer, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="messages")

    reply_to_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    reply_to_message = relationship("Message", remote_side=[id], backref="replies")

    text = Column(String)

    timestamp = Column(DateTime)

    __table_args__ = (UniqueConstraint("id", "chat_id", name="uix_id_chat_id"),)


# Database Initialization and helpers


class Database:
    def __init__(self, database_url):
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def add_message(self, message: telebot_types.Message):
        session = self.Session()

        # Create or update the user as necessary
        user = (
            session.query(User)
            .filter(User.username == message.from_user.username)
            .first()
        )
        if not user:
            user = User(
                id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                language_code=message.from_user.language_code,
            )
            session.add(user)
            session.commit()

        # Add the message to the database
        new_message = Message(
            id=message.message_id,
            chat_id=message.chat.id,
            user_id=user.id,
            reply_to_message_id=message.reply_to_message.message_id
            if message.reply_to_message
            else None,
            text=message.text,
            timestamp=datetime.datetime.fromtimestamp(message.date),
        )

        session.add(new_message)
        session.commit()
        session.close()

    def update_message_text(self, message: telebot_types.Message):
        session = self.Session()
        message = (
            session.query(Message).filter(Message.id == message.message_id).first()
        )
        if message:
            message.text = message.text
            session.commit()
        session.close()

    def get_chat_last_messages(self, chat_id, limit=10, offset=0):
        session = self.Session()
        try:
            messages = (
                session.query(Message)
                .options(joinedload(Message.user))
                .options(joinedload(Message.reply_to_message))
                .filter(Message.chat_id == chat_id)
                .order_by(Message.timestamp.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return messages
        finally:
            session.close()

    def clear_chat_history(self, chat_id):
        session = self.Session()
        session.query(Message).filter(Message.chat_id == chat_id).delete()
        session.commit()
        session.close()
