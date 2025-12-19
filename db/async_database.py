import os
import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    func,
    select,
    delete,
    distinct,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import SQLAlchemyError

from typing import Optional
import logging

from groq_chat.filters import _AUTHORIZED_USERS

logger = logging.getLogger(__name__)
Base = declarative_base()

db_session: Optional[AsyncSession] = None


class Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=False)
    admin = Column(Boolean, nullable=False)
    file_interpreter = Column(Boolean, nullable=False)
    lang = Column(String, nullable=True)

    def __str__(self):
        return f"tg_id: {self.tg_id}; is admin: {self.admin}"

    def postprocessing(self):
        if not self.lang:
            self.lang = os.getenv("LANG", "en")


async def initialize_db() -> AsyncSession:
    global db_session

    dirname = "./data/"

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    connection_string = f"sqlite+aiosqlite:///{dirname}tg-bot.db"
    engine = create_async_engine(connection_string, echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    session = AsyncSessionLocal()
    db_session = session

    admin = True
    for str_tg_id in _AUTHORIZED_USERS:
        tg_id = None
        try:
            tg_id = int(str_tg_id)
        except ValueError:
            logger.error("Ошибка: строка не может быть преобразована в целое число")

        if tg_id:
            try:
                await get_or_create(
                    Users, False, id=tg_id, admin=admin, file_interpreter=False
                )
                admin = False
            except SQLAlchemyError as e:
                logger.error(f"Error initializing user: {e}")
                # raise
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred during user initialization: {e}"
                )
                # raise


async def get_or_create(model, update: bool, **kwargs):
    session = db_session
    instance = None
    try:
        result = await session.execute(select(model).filter_by(id=kwargs["id"]))
        instance = result.scalars().first()

        if instance:
            if update:
                for key, value in kwargs.items():
                    setattr(instance, key, value)
                instance.postprocessing()
                session.add(instance)
                await session.commit()
                await session.refresh(instance)
        else:
            instance = model(**kwargs)
            instance.postprocessing()
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_or_create for model {model.__name__}: {e}")
        await session.rollback()
        instance = None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred in get_or_create for model {model.__name__}: {e}"
        )
        await session.rollback()
        instance = None

    return instance


async def get_record_by_id(model, id):
    session = db_session
    instance = None
    try:
        result = await session.execute(select(model).filter_by(id=id))
        instance = result.scalars().first()
    except Exception as e:
        logger.error(
            f"Database error in get record for model {model.__name__} and id {id}: {e}"
        )

    return instance


async def set_user_setting(user_id, setting_id, setting_value):
    session = db_session
    instance = await get_record_by_id(Users, id=user_id)
    if instance:
        setattr(instance, setting_id, setting_value)
        await session.commit()
        await session.refresh(instance)
    return instance


async def get_user_setting(user_id, setting_id, default_value=None):
    result = default_value
    instance = await get_record_by_id(Users, id=user_id)
    if instance:
        result = getattr(instance, setting_id)
    return result
