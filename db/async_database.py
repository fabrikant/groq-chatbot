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

# FORWARD_FLAG = "forward"
# RECORD_LOGS = "record_logs"

db_session: Optional[AsyncSession] = None


class Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=False)
    admin = Column(Boolean, nullable=False)
    file_interpreter = Column(Boolean, nullable=False)

    def __str__(self):
        return f"tg_id: {self.tg_id}; is admin: {self.admin}"

    def postprocessing(self):
        pass


# class AdminFlags(Base):
#     __tablename__ = "admin_flags"
#     id = Column(String, primary_key=True, autoincrement=False)
#     value = Column(Boolean, nullable=False)

#     def __str__(self):
#         return f"id: {self.id}; value: {self.value}"

#     def postprocessing(self):
#         pass


# class Messages(Base):
#     __tablename__ = "messages"
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     user_id = Column(Integer, nullable=False)
#     user_info = Column(String)
#     message = Column(String)
#     date = Column(DateTime, nullable=False)
#     incoming = Column(Boolean, nullable=False)

#     def __str__(self):
#         return f"id: {self.user_id}; user_info: {self.user_info}; message: {self.message}; date: {self.date}"

#     def postprocessing(self):
#         pass


# class ApplicationsKeys(Base):
#     __tablename__ = "app_keys"
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     app_name = Column(String)
#     user = Column(String)
#     key = Column(String)
#     date = Column(DateTime, nullable=False)
#     app_sanitase_name = Column(String)

#     def __str__(self):
#         return f"id: {self.user_id}; user_info: {self.user_info}; message: {self.message}; date: {self.date}"

#     def postprocessing(self):
#         self.date = datetime.datetime.now()
#         self.app_sanitase_name = self.app_name.lower().replace(" ", "_")


async def initialize_db() -> AsyncSession:
    global db_session

    connection_string = "sqlite+aiosqlite:///./data/tg-bot.db"
    engine = create_async_engine(connection_string, echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    session = AsyncSessionLocal()

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

    db_session = session


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


# async def new_app_key(session: AsyncSession, model, update: bool, **kwargs):
#     instance = None
#     try:
#         result = await session.execute(
#             select(model)
#             .filter_by(user=kwargs["user"])
#             .filter_by(app_name=kwargs["app_name"])
#         )
#         instance = result.scalars().first()

#         if instance:
#             if update:
#                 for key, value in kwargs.items():
#                     setattr(instance, key, value)
#                 instance.postprocessing()
#                 session.add(instance)
#                 await session.commit()
#                 await session.refresh(instance)
#         else:
#             instance = model(**kwargs)
#             instance.postprocessing()
#             session.add(instance)
#             await session.commit()
#             await session.refresh(instance)
#     except SQLAlchemyError as e:
#         logger.error(f"Database error in new_app_key for model {model.__name__}: {e}")
#         await session.rollback()
#         instance = None
#     except Exception as e:
#         logger.error(
#             f"An unexpected error occurred in new_app_key for model {model.__name__}: {e}"
#         )
#         await session.rollback()
#         instance = None

#     return instance


# async def add_message_record(
#     session: AsyncSession, user_id: int, user_info: str, message: str, incoming: bool
# ):
#     try:
#         record = Messages(
#             user_id=user_id,
#             user_info=user_info,
#             message=message,
#             date=datetime.datetime.now(),
#             incoming=incoming,
#         )
#         session.add_all([record])
#         await session.commit()
#         await session.refresh(record)  # Refresh to get the generated ID
#     except SQLAlchemyError as e:
#         logger.error(f"Database error adding message record: {e}")
#         await session.rollback()
#     except Exception as e:
#         logger.error(f"An unexpected error occurred adding message record: {e}")
#         await session.rollback()


# async def get_records_by_user(session: AsyncSession, user_id: int, incoming: bool):
#     try:
#         result = await session.execute(
#             select(Messages)
#             .filter(Messages.incoming == incoming)
#             .filter(Messages.user_id == user_id)
#         )
#         return result.scalars().all()
#     except SQLAlchemyError as e:
#         logger.error(f"Database error getting records by user: {e}")
#         await session.rollback()
#         return []
#     except Exception as e:
#         logger.error(f"An unexpected error occurred getting records by user: {e}")
#         await session.rollback()
#         return []


# async def get_records_by_app(session: AsyncSession, app_sanitase_name: str):
#     try:
#         result = await session.execute(
#             select(ApplicationsKeys).filter(
#                 ApplicationsKeys.app_sanitase_name == app_sanitase_name
#             )
#         )
#         return result.scalars().all()
#     except SQLAlchemyError as e:
#         logger.error(f"Database error getting records by app: {e}")
#         await session.rollback()
#         return []
#     except Exception as e:
#         logger.error(f"An unexpected error occurred getting records by app: {e}")
#         await session.rollback()
#         return []


# async def get_admin_flag(session: AsyncSession, flag_name: str):
#     try:
#         result = await session.execute(select(AdminFlags).filter_by(id=flag_name))
#         return result.scalars().first()
#     except SQLAlchemyError as e:
#         logger.error(f"Database error getting admin flag '{flag_name}': {e}")
#         await session.rollback()
#         return None
#     except Exception as e:
#         logger.error(
#             f"An unexpected error occurred getting admin flag '{flag_name}': {e}"
#         )
#         await session.rollback()
#         return None


# async def messeges_count(session: AsyncSession) -> int:
#     try:
#         return await session.scalar(select(func.count(Messages.id)))
#     except SQLAlchemyError as e:
#         logger.error(f"Database error getting message count: {e}")
#         await session.rollback()
#         return 0
#     except Exception as e:
#         logger.error(f"An unexpected error occurred getting message count: {e}")
#         await session.rollback()
#         return 0


# async def users_count(session: AsyncSession) -> int:
#     try:
#         return await session.scalar(select(func.count(distinct(Messages.user_id))))
#     except SQLAlchemyError as e:
#         logger.error(f"Database error getting distinct user count: {e}")
#         await session.rollback()
#         return 0
#     except Exception as e:
#         logger.error(f"An unexpected error occurred getting distinct user count: {e}")
#         await session.rollback()
#         return 0


# async def delete_messages(session: AsyncSession):
#     try:
#         await session.execute(delete(Messages))
#         await session.commit()
#     except SQLAlchemyError as e:
#         logger.error(f"Database error deleting all messages: {e}")
#         await session.rollback()
#     except Exception as e:
#         logger.error(f"An unexpected error occurred deleting all messages: {e}")
#         await session.rollback()
