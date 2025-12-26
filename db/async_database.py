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
    ocr_model = Column(String, nullable=True)
    tts_model = Column(String, nullable=True)
    stt_model = Column(String, nullable=True)
    tts_voice = Column(String, nullable=True)

    def __str__(self):
        return f"tg_id: {self.tg_id}; is admin: {self.admin}"

    def postprocessing(self):
        if not self.lang:
            self.lang = os.getenv("LANG", "en")


class ModelsVoices(Base):
    __tablename__ = "models_voices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String, nullable=False)
    voice_name = Column(String, nullable=False)


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


async def set_model_voices(user_id: int, model_name: str, voices: list) -> None:
    session = db_session

    # 1. Синхронизация таблицы ModelsVoices (добавление/удаление)
    stmt = select(ModelsVoices).where(ModelsVoices.model_name == model_name)
    result = await session.execute(stmt)
    existing_records = result.scalars().all()

    existing_voices_map = {r.voice_name: r for r in existing_records}
    existing_voices_names = set(existing_voices_map.keys())
    new_voices_names = set(voices)

    # Удаляем старые
    voices_to_delete = existing_voices_names - new_voices_names
    if voices_to_delete:
        delete_stmt = delete(ModelsVoices).where(
            ModelsVoices.model_name == model_name,
            ModelsVoices.voice_name.in_(voices_to_delete),
        )
        await session.execute(delete_stmt)

    # Добавляем новые
    for v_name in new_voices_names - existing_voices_names:
        new_record = ModelsVoices(
            model_name=model_name,
            voice_name=v_name,
            # active=False  # Раскомментируйте, если поле есть в БД
        )
        session.add(new_record)

    # 2. Проверка пользователя (Users)
    if voices:  # Проверяем только если список не пуст
        user_stmt = select(Users).where(Users.id == user_id)
        user_result = await session.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if user:
            if user.tts_voice not in voices:
                user.tts_voice = voices[0]

    try:
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
