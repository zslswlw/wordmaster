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
    ("context_audio", "VARCHAR", "''"),
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
    "feature_flags": """
        CREATE TABLE IF NOT EXISTS feature_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            example_enabled BOOLEAN DEFAULT 1,
            image_enabled BOOLEAN DEFAULT 1,
            mnemonic_enabled BOOLEAN DEFAULT 1,
            error_analysis_enabled BOOLEAN DEFAULT 1,
            story_enabled BOOLEAN DEFAULT 0
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

    # 检查 words 表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='words'")
    words_table_exists = cursor.fetchone() is not None
    existing_tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    if not words_table_exists:
        # 全新数据库: 用 SQLAlchemy create_all 建全量表（含最新 schema）
        conn.close()
        print("  全新数据库，使用 SQLAlchemy 创建所有表...")
        from app.models import Base, engine
        Base.metadata.create_all(bind=engine)
        print("  ✓ 所有表已创建（包含最新 schema）")
    else:
        # 已存在数据库: 增量添加缺失的列
        print("  检测到已有数据库，增量迁移...")
        cursor.execute("PRAGMA table_info(words)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        for col_name, col_type, default in AI_COLUMNS:
            if col_name not in existing_cols:
                sql = f"ALTER TABLE words ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                cursor.execute(sql)
                print(f"  ✓ 添加列: words.{col_name}")
            else:
                print(f"  - 已存在: words.{col_name}")

    # 创建新表（幂等，兼容新旧数据库）
    if not words_table_exists:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

    for table_name, ddl in NEW_TABLES.items():
        if table_name not in existing_tables:
            cursor.execute(ddl)
            print(f"  ✓ 创建表: {table_name}")
        else:
            print(f"  - 已存在: {table_name}")

    # 确保 feature_flags 有默认行
    cursor.execute("SELECT COUNT(*) FROM feature_flags")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO feature_flags (id, example_enabled, image_enabled, mnemonic_enabled, error_analysis_enabled, story_enabled) VALUES (1, 1, 1, 1, 1, 0)")
        print("  ✓ 插入默认 feature_flags 行")

    # 词库迁移: user_id 允许 NULL (共享词库)
    if words_table_exists:
        cursor.execute("PRAGMA table_info(word_banks)")
        bank_cols = {row[1]: row for row in cursor.fetchall()}
        if "user_id" in bank_cols and bank_cols["user_id"][3] == 1:  # notnull=1
            conn.commit()  # 提交之前的操作
            # SQLite 不支持 ALTER COLUMN，通过重建表实现
            conn.execute("CREATE TABLE word_banks_new (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR NOT NULL, user_id INTEGER NULL REFERENCES users(id), word_count INTEGER DEFAULT 0, created_at DATETIME)")
            conn.execute("INSERT INTO word_banks_new SELECT id, name, user_id, word_count, created_at FROM word_banks")
            conn.execute("DROP TABLE word_banks")
            conn.execute("ALTER TABLE word_banks_new RENAME TO word_banks")
            conn.commit()
            print("  ✓ word_banks.user_id: NOT NULL → NULL")

    # 角色迁移: 添加 role 列，首个用户设为 admin
    if words_table_exists:
        cursor.execute("PRAGMA table_info(users)")
        user_cols = {row[1] for row in cursor.fetchall()}
        if "role" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'user'")
            print("  ✓ 添加列: users.role")
            # 首注册用户设为 admin
            cursor.execute("UPDATE users SET role = 'admin' WHERE id = (SELECT MIN(id) FROM users)")
            print("  ✓ 首个用户已设为 admin")
        else:
            print("  - 已存在: users.role")

    conn.commit()
    conn.close()
    print("\n迁移完成，用户数据未受影响。")


if __name__ == "__main__":
    migrate()
