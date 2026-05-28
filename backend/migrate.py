"""
数据库迁移脚本 — 为现有数据库添加 AI 增强所需的列和表
安全: 只添加缺失的列，不修改已有数据
幂等: 可重复执行，已存在的列/表会自动跳过
"""
import os
import re
import sqlite3

# 从 DATABASE_URL 提取路径，兼容 Docker 环境和本地开发
_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./wordmaster.db")
_DB_PATH = re.sub(r"^sqlite:///", "", _DB_URL)
DB_PATH = os.path.abspath(_DB_PATH)

# AI 增强字段: (列名, SQL类型, 默认值)
AI_COLUMNS = [
    ("example_l1", "VARCHAR", "''"),
    ("example_l2", "VARCHAR", "''"),
    ("example_l3", "VARCHAR", "''"),
    ("image_prompt", "VARCHAR", "''"),
    ("image_url", "VARCHAR", "''"),
    ("mnemonic", "VARCHAR", "''"),
    ("etymology", "VARCHAR", "''"),
    ("word_family", "VARCHAR", "''"),
    ("synonyms", "VARCHAR", "''"),
    ("enriched", "BOOLEAN", "0"),
]

NEW_TABLES = {
    "api_configs": """
        CREATE TABLE IF NOT EXISTS api_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider VARCHAR NOT NULL,
            api_key_encrypted VARCHAR NOT NULL,
            api_base VARCHAR NOT NULL,
            text_model VARCHAR,
            image_model VARCHAR,
            speech_model VARCHAR,
            is_enabled BOOLEAN DEFAULT 0
        )
    """,
    "word_error_patterns": """
        CREATE TABLE IF NOT EXISTS word_error_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            word_id INTEGER NOT NULL REFERENCES words(id),
            user_input VARCHAR,
            error_type VARCHAR,
            count INTEGER DEFAULT 1
        )
    """,
}


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 获取 words 表已有列名
    cursor.execute("PRAGMA table_info(words)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    # 2. 添加缺失的列
    for col_name, col_type, default in AI_COLUMNS:
        if col_name not in existing_cols:
            sql = f"ALTER TABLE words ADD COLUMN {col_name} {col_type} DEFAULT {default}"
            cursor.execute(sql)
            print(f"  ✓ 添加列: words.{col_name}")
        else:
            print(f"  - 已存在: words.{col_name}")

    # 3. 创建新表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    for table_name, ddl in NEW_TABLES.items():
        if table_name not in existing_tables:
            cursor.execute(ddl)
            print(f"  ✓ 创建表: {table_name}")
        else:
            print(f"  - 已存在: {table_name}")

    conn.commit()
    conn.close()
    print("\n迁移完成，用户数据未受影响。")


if __name__ == "__main__":
    migrate()
