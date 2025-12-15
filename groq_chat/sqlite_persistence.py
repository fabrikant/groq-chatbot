# persistence.py
import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

from telegram import Update
from telegram.ext import BasePersistence
from telegram.ext import CallbackData

# ----------------------------------------------------------------------
# 1️⃣  Асинхронный SQLAlchemy
# ----------------------------------------------------------------------
from sqlalchemy import (
    Column,
    Integer,
    Text,
    JSON,
    PrimaryKeyConstraint,
    select,
    insert,
    delete,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ----------------------------------------------------------------------
# 2️⃣  Таблицы
# ----------------------------------------------------------------------
class UserData(Base):
    __tablename__ = "user_data"
    user_id = Column(Integer, primary_key=True, autoincrement=False)
    data = Column(JSON, nullable=False, default=dict)


class ChatData(Base):
    __tablename__ = "chat_data"
    chat_id = Column(Integer, primary_key=True, autoincrement=False)
    data = Column(JSON, nullable=False, default=dict)


class BotData(Base):
    __tablename__ = "bot_data"
    id = Column(Integer, primary_key=True, default=1)
    data = Column(JSON, nullable=False, default=dict)


class CallbackDataModel(Base):
    __tablename__ = "callback_data"
    pattern = Column(Text, primary_key=True)  # уникальный ключ
    data = Column(JSON, nullable=False)  # сериализованные данные


class ConversationData(Base):
    __tablename__ = "conversation_data"
    chat_id = Column(Integer, primary_key=True, autoincrement=False)
    user_id = Column(Integer, primary_key=True, autoincrement=False)
    state = Column(Text, nullable=True)
    data = Column(JSON, nullable=False, default=dict)


# ----------------------------------------------------------------------
# 3️⃣  SQLitePersistence
# ----------------------------------------------------------------------
class SQLitePersistence(BasePersistence):
    """
    Асинхронный persistence, использующий SQLite + SQLAlchemy.
    Файл БД: ./data/telegram_bot_data.db
    """

    def __init__(self, path: str = "./data/telegram_bot_data.db"):
        # Создаём директорию, если её нет
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        # Асинхронный движок SQLite
        self._engine = create_async_engine(
            f"sqlite+aiosqlite:///{path}",
            echo=False,
            future=True,
        )
        self._sessionmaker = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

        # Таблицы создаём один раз (запускаем в синхронном контексте,
        # потому что __init__ не async)
        import asyncio

        asyncio.get_event_loop().run_until_complete(self._create_tables())

    # ------------------------------------------------------------------
    # 3️⃣  Внутренний метод создания таблиц
    # ------------------------------------------------------------------
    async def _create_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ------------------------------------------------------------------
    # 4️⃣  Пользовательские данные
    # ------------------------------------------------------------------
    async def get_user_data(self) -> Dict[int, Dict]:
        async with self._sessionmaker() as session:
            stmt = select(UserData)
            result = await session.execute(stmt)
            return {row.user_id: row.data for row in result.scalars()}

    async def update_user_data(self, user_id: int, data: Dict) -> None:
        async with self._sessionmaker() as session:
            stmt = (
                insert(UserData)
                .values(user_id=user_id, data=data)
                .on_conflict_do_update(index_elements=["user_id"], set_={"data": data})
            )
            await session.execute(stmt)
            await session.commit()

    # ------------------------------------------------------------------
    # 5️⃣  Чат‑данные
    # ------------------------------------------------------------------
    async def get_chat_data(self) -> Dict[int, Dict]:
        async with self._sessionmaker() as session:
            stmt = select(ChatData)
            result = await session.execute(stmt)
            return {row.chat_id: row.data for row in result.scalars()}

    async def update_chat_data(self, chat_id: int, data: Dict) -> None:
        async with self._sessionmaker() as session:
            stmt = (
                insert(ChatData)
                .values(chat_id=chat_id, data=data)
                .on_conflict_do_update(index_elements=["chat_id"], set_={"data": data})
            )
            await session.execute(stmt)
            await session.commit()

    # ------------------------------------------------------------------
    # 6️⃣  Bot‑данные (одна запись)
    # ------------------------------------------------------------------
    async def get_bot_data(self) -> Dict:
        async with self._sessionmaker() as session:
            stmt = select(BotData).where(BotData.id == 1)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return row.data if row else {}

    async def update_bot_data(self, data: Dict) -> None:
        async with self._sessionmaker() as session:
            stmt = (
                insert(BotData)
                .values(id=1, data=data)
                .on_conflict_do_update(index_elements=["id"], set_={"data": data})
            )
            await session.execute(stmt)
            await session.commit()

    # ------------------------------------------------------------------
    # 7️⃣  Callback‑данные
    # ------------------------------------------------------------------
    async def store_callback_data(self, callback_data: CallbackData) -> str:
        """
                Сохраняет объект ``CallbackData`` и возвращает строку‑ключ,
        которую потом можно положить в ``callback_data`` кнопки.
        """
        # Приведём объект к JSON‑строке – это будет наш уникальный key.
        # Сериализуем с сортировкой, чтобы один и тот же набор полей давал одинаковый ключ.
        payload = json.dumps(
            callback_data.to_dict(), sort_keys=True, separators=(",", ":")
        )
        key = f"{callback_data.pattern}:{payload}"

        async with self._sessionmaker() as session:
            stmt = insert(CallbackDataModel).values(
                pattern=key, data=callback_data.to_dict()
            )
            await session.execute(stmt)
            await session.commit()
        return key

    async def get_callback_data(self, pattern: str) -> Optional[Dict]:
        """Возвращает сохранённые данные по ключу, полученному из InlineKeyboardButton."""
        async with self._sessionmaker() as session:
            stmt = select(CallbackDataModel).where(CallbackDataModel.pattern == pattern)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return row.data if row else None

    async def drop_callback_data(self, pattern: str) -> None:
        async with self._sessionmaker() as session:
            stmt = delete(CallbackDataModel).where(CallbackDataModel.pattern == pattern)
            await session.execute(stmt)
            await session.commit()

    # ------------------------------------------------------------------
    # 8️⃣  Диалоги (ConversationHandler)
    # ------------------------------------------------------------------
    async def get_conversation(
        self, chat_id: int, user_id: int
    ) -> Tuple[Optional[str], Dict]:
        async with self._sessionmaker() as session:
            stmt = select(ConversationData).where(
                ConversationData.chat_id == chat_id,
                ConversationData.user_id == user_id,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return row.state, row.data
            return None, {}

    async def update_conversation(
        self,
        chat_id: int,
        user_id: int,
        new_state: Optional[str] = None,
        new_data: Optional[Dict] = None,
    ) -> None:
        async with self._sessionmaker() as session:
            # Подготовим словарь полей, которые хотим upsert‑нуть
            values: Dict[str, Any] = {"chat_id": chat_id, "user_id": user_id}
            if new_state is not None:
                values["state"] = new_state
            if new_data is not None:
                values["data"] = new_data

            stmt = (
                insert(ConversationData)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=["chat_id", "user_id"], set_=values
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def drop_conversation(self, chat_id: int, user_id: int) -> None:
        async with self._sessionmaker() as session:
            stmt = delete(ConversationData).where(
                ConversationData.chat_id == chat_id,
                ConversationData.user_id == user_id,
            )
            await session.execute(stmt)
            await session.commit()

    # ------------------------------------------------------------------
    # 9️⃣  Закрытие соединения
    # ------------------------------------------------------------------
    async def close(self) -> None:
        """Вызывается при остановке приложения."""
        await self._engine.dispose()


# ----------------------------------------------------------------------
# 10️⃣  Пример запуска бота
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    from telegram import Bot
    from telegram.ext import ApplicationBuilder, CommandHandler

    async def start(update: Update, _: Any) -> None:
        await update.message.reply_text("Привет! Данные сохраняются в SQLite.")

    async def main() -> None:
        persistence = SQLitePersistence()  # создаёт ./data/telegram_bot_data.db
        app = (
            ApplicationBuilder()
            .token("YOUR_BOT_TOKEN")  # <-- замените на реальный токен
            .persistence(persistence)
            .build()
        )

        app.add_handler(CommandHandler("start", start))

        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        # Ожидаем пока процесс не будет остановлен вручную
        await asyncio.Event().wait()

    asyncio.run(main())
