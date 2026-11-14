"""Alembic 遷移環境。

連線字串的來源依序是：
1. 程序環境變數 DATABASE_URL
2. 專案目錄（ledger-api）裡 .env 檔的 DATABASE_URL

不從 alembic.ini 讀連線字串，也不把連線字串寫進程式。
"""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import create_engine, pool

from database_url import normalize_database_url
from extensions import db
import models  # noqa: F401  載入模型，讓資料表註冊到 db.metadata，autogenerate 才看得到

PROJECT_DIR = Path(__file__).resolve().parent.parent

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = db.metadata


def get_database_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        env_file = PROJECT_DIR / ".env"
        if env_file.is_file():
            url = (dotenv_values(env_file).get("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "找不到 DATABASE_URL。請在環境變數設定，或寫在 "
            f"{PROJECT_DIR / '.env'}（格式見 .env.example）。"
        )
    return normalize_database_url(url)


def run_migrations_offline() -> None:
    """離線模式：只產生 SQL，不連資料庫。"""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """連線模式：連上資料庫執行遷移。"""
    connectable = create_engine(get_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
