import sqlite3

from migrate import migrate


def test_core_migration_merges_duplicates_and_adds_constraints(tmp_path):
    db_path = tmp_path / "legacy-test.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR,
            password_hash VARCHAR,
            created_at DATETIME
        );
        CREATE TABLE word_banks (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id),
            word_count INTEGER,
            created_at DATETIME
        );
        CREATE TABLE words (
            id INTEGER PRIMARY KEY,
            bank_id INTEGER REFERENCES word_banks(id),
            seq_num INTEGER,
            word VARCHAR,
            phonetic VARCHAR,
            meaning VARCHAR
        );
        CREATE TABLE study_groups (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            bank_id INTEGER REFERENCES word_banks(id),
            name VARCHAR,
            start_seq INTEGER,
            end_seq INTEGER,
            status VARCHAR,
            created_at DATETIME,
            completed_at DATETIME
        );
        CREATE TABLE review_plans (
            id INTEGER PRIMARY KEY,
            group_id INTEGER,
            review_date DATE,
            review_round INTEGER,
            status VARCHAR
        );
        CREATE TABLE study_records (
            id INTEGER PRIMARY KEY,
            group_id INTEGER,
            word_id INTEGER,
            round INTEGER,
            correct BOOLEAN,
            study_type VARCHAR,
            plan_id INTEGER,
            studied_at DATETIME
        );
        CREATE TABLE api_configs (
            id INTEGER PRIMARY KEY,
            provider VARCHAR NOT NULL,
            api_key_encrypted VARCHAR NOT NULL,
            api_base VARCHAR NOT NULL,
            text_model VARCHAR,
            image_model VARCHAR,
            speech_model VARCHAR,
            is_enabled BOOLEAN
        );
        INSERT INTO users VALUES (1, 'tester', 'hash', '2026-01-01');
        INSERT INTO word_banks VALUES (1, 'bank', 1, 1, '2026-01-01');
        INSERT INTO words (id, bank_id, seq_num, word, phonetic, meaning)
            VALUES (1, 1, 1, 'apple', '', '苹果');
        INSERT INTO study_groups VALUES
            (1, 1, 1, 'group', 1, 1, 'completed', '2026-01-01', '2026-01-01');
        INSERT INTO review_plans VALUES (10, 1, '2026-01-02', 1, 'pending');
        INSERT INTO review_plans VALUES (11, 1, '2026-01-02', 1, 'completed');
        INSERT INTO study_records VALUES
            (20, 1, 1, 1, 0, 'review', 11, '2026-01-02');
        INSERT INTO study_records VALUES
            (21, 1, 1, 1, 1, 'review', 11, '2026-01-02');
        INSERT INTO api_configs VALUES (
            1,
            'minimax',
            'legacy-secret',
            'https://api.minimax.chat',
            'minimax-m2.7',
            '',
            'speech-02',
            1
        );
        """
    )
    conn.commit()
    conn.close()

    migrate(str(db_path))

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        plans = cursor.execute(
            "SELECT id, status, original_date, postponed_days FROM review_plans"
        ).fetchall()
        assert plans == [(10, "completed", "2026-01-02", 0)]
        records = cursor.execute(
            "SELECT id, plan_id, correct FROM study_records"
        ).fetchall()
        assert records == [(21, 10, 1)]

        indexes = {
            row[1]
            for row in cursor.execute("PRAGMA index_list(study_records)").fetchall()
        }
        assert "uq_study_records_no_plan" in indexes
        assert "uq_study_records_with_plan" in indexes
        assert "user_input" in {
            row[1] for row in cursor.execute("PRAGMA table_info(study_records)")
        }
        assert "ix_ai_jobs_bank_status" in {
            row[1] for row in cursor.execute("PRAGMA index_list(ai_jobs)").fetchall()
        }
        assert "ix_words_bank_seq" in {
            row[1] for row in cursor.execute("PRAGMA index_list(words)").fetchall()
        }
        tables = {
            row[0]
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "memory_bundles",
            "memory_assets",
            "word_memory_links",
            "memory_feedback",
            "memory_exposures",
            "ai_jobs",
            "ai_quota_snapshots",
        }.issubset(tables)
        minimax = cursor.execute(
            """
            SELECT api_key_encrypted, api_base, text_model, image_model, speech_model
            FROM api_configs
            WHERE provider = 'minimax'
            """
        ).fetchone()
        assert minimax[0].startswith("enc:v1:")
        assert "legacy-secret" not in minimax[0]
        assert minimax[1:] == (
            "https://api.minimaxi.com",
            "MiniMax-M3",
            "image-01",
            "speech-2.8-turbo",
        )
        assert cursor.execute("PRAGMA journal_mode").fetchone()[0] == "wal"

        with __import__("pytest").raises(sqlite3.IntegrityError):
            cursor.execute(
                """
                INSERT INTO study_records
                    (group_id, word_id, round, correct, study_type, plan_id)
                VALUES (1, 1, 1, 1, 'review', 10)
                """
            )
    finally:
        conn.close()
