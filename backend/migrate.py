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
            story_enabled BOOLEAN DEFAULT 0,
            ai_worker_paused BOOLEAN DEFAULT 0,
            ai_worker_pause_reason TEXT,
            ai_worker_paused_at DATETIME,
            quota_reserve_percent INTEGER DEFAULT 30,
            feedback_reserve_percent INTEGER DEFAULT 20,
            priority_bank_id INTEGER REFERENCES word_banks(id)
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
    "memory_bundles": """
        CREATE TABLE IF NOT EXISTS memory_bundles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lexeme_key VARCHAR(64) NOT NULL,
            word_text VARCHAR NOT NULL,
            normalized_pos VARCHAR,
            primary_meaning VARCHAR NOT NULL,
            strategy VARCHAR,
            memory_anchor VARCHAR(45),
            scene_summary VARCHAR,
            image_prompt TEXT,
            narration_text VARCHAR(64) NOT NULL,
            prompt_version VARCHAR NOT NULL DEFAULT 'memory-v1',
            content_version INTEGER NOT NULL DEFAULT 1,
            text_model VARCHAR,
            quality_scores TEXT,
            status VARCHAR NOT NULL DEFAULT 'draft',
            source_bundle_id INTEGER REFERENCES memory_bundles(id),
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    """,
    "memory_assets": """
        CREATE TABLE IF NOT EXISTS memory_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bundle_id INTEGER NOT NULL REFERENCES memory_bundles(id),
            asset_type VARCHAR NOT NULL,
            file_path VARCHAR NOT NULL,
            sha256 VARCHAR(64) NOT NULL,
            mime_type VARCHAR NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            model VARCHAR,
            generation_params TEXT,
            status VARCHAR NOT NULL DEFAULT 'ready',
            created_at DATETIME NOT NULL
        )
    """,
    "word_memory_links": """
        CREATE TABLE IF NOT EXISTS word_memory_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL UNIQUE REFERENCES words(id),
            active_bundle_id INTEGER REFERENCES memory_bundles(id),
            status VARCHAR NOT NULL DEFAULT 'pending',
            revision INTEGER NOT NULL DEFAULT 1,
            updated_at DATETIME NOT NULL
        )
    """,
    "memory_feedback": """
        CREATE TABLE IF NOT EXISTS memory_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            word_id INTEGER NOT NULL REFERENCES words(id),
            bundle_id INTEGER REFERENCES memory_bundles(id),
            component VARCHAR NOT NULL,
            reason VARCHAR NOT NULL,
            detail TEXT,
            status VARCHAR NOT NULL DEFAULT 'pending',
            replacement_bundle_id INTEGER REFERENCES memory_bundles(id),
            auto_attempts INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            resolved_at DATETIME
        )
    """,
    "memory_exposures": """
        CREATE TABLE IF NOT EXISTS memory_exposures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            word_id INTEGER NOT NULL REFERENCES words(id),
            bundle_id INTEGER REFERENCES memory_bundles(id),
            group_id INTEGER REFERENCES study_groups(id),
            plan_id INTEGER REFERENCES review_plans(id),
            study_type VARCHAR,
            exposed_at DATETIME NOT NULL,
            next_result BOOLEAN
        )
    """,
    "ai_jobs": """
        CREATE TABLE IF NOT EXISTS ai_jobs (
            id VARCHAR(36) PRIMARY KEY,
            kind VARCHAR NOT NULL,
            target_type VARCHAR NOT NULL,
            target_id INTEGER NOT NULL,
            bank_id INTEGER REFERENCES word_banks(id),
            priority INTEGER NOT NULL DEFAULT 100,
            status VARCHAR NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            available_at DATETIME NOT NULL,
            payload TEXT,
            idempotency_key VARCHAR NOT NULL UNIQUE,
            last_error_code VARCHAR,
            last_error_message TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    """,
    "ai_quota_snapshots": """
        CREATE TABLE IF NOT EXISTS ai_quota_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider VARCHAR NOT NULL,
            remaining_percent FLOAT,
            status VARCHAR NOT NULL,
            reset_at DATETIME,
            raw_payload TEXT,
            checked_at DATETIME NOT NULL
        )
    """,
    "system_state": """
        CREATE TABLE IF NOT EXISTS system_state (
            id INTEGER PRIMARY KEY,
            maintenance_mode BOOLEAN NOT NULL DEFAULT 0,
            maintenance_reason VARCHAR,
            maintenance_started_by INTEGER REFERENCES users(id),
            maintenance_started_at DATETIME
        )
    """,
    "admin_audit_logs": """
        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER REFERENCES users(id),
            actor_username VARCHAR NOT NULL,
            action VARCHAR NOT NULL,
            target_type VARCHAR NOT NULL,
            target_id VARCHAR,
            before_json TEXT,
            after_json TEXT,
            request_id VARCHAR(36) NOT NULL,
            ip_address VARCHAR,
            user_agent TEXT,
            created_at DATETIME NOT NULL
        )
    """,
}


def _table_columns(cursor, table_name):
    return {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")}


def _add_column(cursor, table_name, column_name, ddl):
    if column_name in _table_columns(cursor, table_name):
        return
    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")
    print(f"  ✓ 添加列: {table_name}.{column_name}")


def _merge_duplicate_review_plans(cursor):
    duplicates = cursor.execute(
        """
        SELECT group_id, review_round
        FROM review_plans
        GROUP BY group_id, review_round
        HAVING COUNT(*) > 1
        """
    ).fetchall()

    for group_id, review_round in duplicates:
        plans = cursor.execute(
            """
            SELECT id, review_date, original_date, status, postponed_days, completed_at
            FROM review_plans
            WHERE group_id = ? AND review_round = ?
            ORDER BY id
            """,
            (group_id, review_round),
        ).fetchall()
        canonical_id = plans[0][0]
        duplicate_ids = [row[0] for row in plans[1:]]
        completed_dates = sorted(row[5] for row in plans if row[5])
        status = "completed" if any(row[3] == "completed" for row in plans) else "pending"
        review_date = plans[0][1]
        original_date = plans[0][2] or review_date
        postponed_days = max((row[4] or 0) for row in plans)
        completed_at = completed_dates[0] if completed_dates else None

        cursor.execute(
            """
            UPDATE review_plans
            SET review_date = ?, original_date = ?, status = ?,
                postponed_days = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                review_date,
                original_date,
                status,
                postponed_days,
                completed_at,
                canonical_id,
            ),
        )
        placeholders = ",".join("?" for _ in duplicate_ids)
        cursor.execute(
            f"UPDATE study_records SET plan_id = ? WHERE plan_id IN ({placeholders})",
            (canonical_id, *duplicate_ids),
        )
        cursor.execute(
            f"DELETE FROM review_plans WHERE id IN ({placeholders})",
            duplicate_ids,
        )
        print(f"  ✓ 合并重复复习计划: group={group_id}, round={review_round}")


def _migrate_study_core(cursor, existing_tables):
    if "study_records" not in existing_tables or "review_plans" not in existing_tables:
        return

    _add_column(cursor, "study_records", "study_type", "VARCHAR DEFAULT 'new'")
    _add_column(cursor, "study_records", "user_input", "VARCHAR")
    _add_column(
        cursor,
        "study_records",
        "plan_id",
        "INTEGER REFERENCES review_plans(id)",
    )
    _add_column(cursor, "review_plans", "original_date", "DATE")
    _add_column(cursor, "review_plans", "postponed_days", "INTEGER DEFAULT 0")
    _add_column(cursor, "review_plans", "completed_at", "DATETIME")

    cursor.execute("UPDATE study_records SET study_type = 'new' WHERE study_type IS NULL")
    cursor.execute(
        "UPDATE review_plans SET original_date = review_date WHERE original_date IS NULL"
    )
    cursor.execute(
        "UPDATE review_plans SET postponed_days = 0 WHERE postponed_days IS NULL"
    )
    cursor.execute("UPDATE review_plans SET status = 'pending' WHERE status IS NULL")

    _merge_duplicate_review_plans(cursor)

    cursor.execute(
        """
        DELETE FROM study_records
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM study_records
            GROUP BY group_id, word_id, round, study_type, COALESCE(plan_id, -1)
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_study_records_no_plan
        ON study_records(group_id, word_id, round, study_type)
        WHERE plan_id IS NULL
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_study_records_with_plan
        ON study_records(plan_id, word_id, round)
        WHERE plan_id IS NOT NULL
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_review_plans_group_round
        ON review_plans(group_id, review_round)
        """
    )
    print("  ✓ 学习记录与复习计划已去重并建立唯一约束")


def migrate(db_path=None):
    target_path = os.path.abspath(db_path or DB_PATH)
    conn = sqlite3.connect(target_path)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    # Legacy migrations rebuild referenced tables. Keep FK checks disabled only
    # for this migration connection; application connections enable them.
    conn.execute("PRAGMA foreign_keys=OFF")
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
        conn = sqlite3.connect(target_path)
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=OFF")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

    for table_name, ddl in NEW_TABLES.items():
        if table_name not in existing_tables:
            cursor.execute(ddl)
            print(f"  ✓ 创建表: {table_name}")
        else:
            print(f"  - 已存在: {table_name}")

    for table_name in ("word_banks", "api_configs", "feature_flags", "word_memory_links"):
        if table_name in existing_tables or table_name in NEW_TABLES:
            _add_column(cursor, table_name, "revision", "INTEGER NOT NULL DEFAULT 1")
            cursor.execute(
                f"UPDATE {table_name} SET revision = 1 WHERE revision IS NULL OR revision < 1"
            )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_admin_audit_created ON admin_audit_logs(created_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_admin_audit_actor_created "
        "ON admin_audit_logs(actor_user_id, created_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_admin_audit_request_id ON admin_audit_logs(request_id)"
    )

    _add_column(
        cursor,
        "feature_flags",
        "ai_worker_paused",
        "BOOLEAN DEFAULT 0",
    )
    _add_column(
        cursor,
        "feature_flags",
        "ai_worker_pause_reason",
        "TEXT",
    )
    _add_column(
        cursor,
        "feature_flags",
        "ai_worker_paused_at",
        "DATETIME",
    )
    _add_column(
        cursor,
        "feature_flags",
        "quota_reserve_percent",
        "INTEGER DEFAULT 30",
    )
    _add_column(
        cursor,
        "feature_flags",
        "feedback_reserve_percent",
        "INTEGER DEFAULT 20",
    )
    _add_column(
        cursor,
        "feature_flags",
        "priority_bank_id",
        "INTEGER REFERENCES word_banks(id)",
    )

    # 确保 feature_flags 有默认行
    cursor.execute("SELECT COUNT(*) FROM feature_flags")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO feature_flags (id, example_enabled, image_enabled, mnemonic_enabled, error_analysis_enabled, story_enabled) VALUES (1, 1, 1, 1, 1, 0)")
        print("  ✓ 插入默认 feature_flags 行")

    cursor.execute(
        """
        UPDATE feature_flags
        SET ai_worker_pause_reason = '旧版本自动暂停，恢复前请查看最近失败原因'
        WHERE ai_worker_paused = 1
          AND (ai_worker_pause_reason IS NULL OR trim(ai_worker_pause_reason) = '')
        """
    )

    # 词库迁移: user_id 允许 NULL (共享词库)
    if words_table_exists:
        cursor.execute("PRAGMA table_info(word_banks)")
        bank_cols = {row[1]: row for row in cursor.fetchall()}
        if "user_id" in bank_cols and bank_cols["user_id"][3] == 1:  # notnull=1
            conn.commit()  # 提交之前的操作
            # SQLite 不支持 ALTER COLUMN，通过重建表实现
            conn.execute("CREATE TABLE word_banks_new (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR NOT NULL, user_id INTEGER NULL REFERENCES users(id), word_count INTEGER DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1, created_at DATETIME)")
            conn.execute("INSERT INTO word_banks_new SELECT id, name, user_id, word_count, revision, created_at FROM word_banks")
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

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}
    _migrate_study_core(cursor, existing_tables)

    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_bundle_version "
        "ON memory_bundles(lexeme_key, content_version)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_asset_version "
        "ON memory_assets(bundle_id, asset_type, version)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_jobs_dispatch "
        "ON ai_jobs(status, priority, available_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_jobs_bank_status "
        "ON ai_jobs(bank_id, status, priority, available_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_words_bank_seq "
        "ON words(bank_id, seq_num)"
    )

    # Existing plaintext keys are encrypted in place; already encrypted values are untouched.
    if "api_configs" in existing_tables:
        try:
            from app.services.ai.secrets import encrypt_secret

            for config_id, secret in cursor.execute(
                "SELECT id, api_key_encrypted FROM api_configs"
            ).fetchall():
                if secret and not secret.startswith("enc:v1:"):
                    cursor.execute(
                        "UPDATE api_configs SET api_key_encrypted = ? WHERE id = ?",
                        (encrypt_secret(secret), config_id),
                    )
            print("  ✓ API Key 已使用 APP_SECRET_KEY 加密")
        except ImportError:
            print("  ! 未找到加密依赖，API Key 暂未迁移")

        cursor.execute(
            """
            UPDATE api_configs
            SET api_base = 'https://api.minimaxi.com'
            WHERE lower(provider) = 'minimax'
              AND lower(rtrim(api_base, '/')) IN (
                  'https://api.minimax.chat',
                  'http://api.minimax.chat'
              )
            """
        )
        cursor.execute(
            """
            UPDATE api_configs
            SET text_model = 'MiniMax-M3'
            WHERE lower(provider) = 'minimax'
              AND (
                  text_model IS NULL
                  OR trim(text_model) = ''
                  OR lower(trim(text_model)) LIKE 'minimax-m2%'
              )
            """
        )
        cursor.execute(
            """
            UPDATE api_configs
            SET image_model = 'image-01'
            WHERE lower(provider) = 'minimax'
              AND (image_model IS NULL OR trim(image_model) = '')
            """
        )
        cursor.execute(
            """
            UPDATE api_configs
            SET speech_model = 'speech-2.8-turbo'
            WHERE lower(provider) = 'minimax'
              AND (
                  speech_model IS NULL
                  OR trim(speech_model) = ''
                  OR lower(trim(speech_model)) = 'speech-02'
              )
            """
        )
        print("  ✓ MiniMax 旧配置已升级到中国区 MiniMax-M3")

    conn.commit()
    conn.close()
    print("\n迁移完成，用户数据未受影响。")


if __name__ == "__main__":
    migrate()
