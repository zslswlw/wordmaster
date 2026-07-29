import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


IMPORT_DB = Path(f"/private/tmp/wordmaster-test-import-{os.getpid()}.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["ENV"] = "test"
os.environ["APP_TIMEZONE"] = "Asia/Shanghai"
os.environ["DATABASE_URL"] = f"sqlite:///{IMPORT_DB}"
os.environ["TEST_RANDOM_SEED"] = "0"

from app.auth import create_access_token
from app.clock import MutableBusinessClock, set_clock
from app.main import app
from app.models import Base, User, configure_sqlite_connection, get_db


@pytest.fixture
def api(tmp_path):
    db_path = tmp_path / "wordmaster-test-case.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    from sqlalchemy import event

    event.listen(engine, "connect", configure_sqlite_connection)
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    clock = MutableBusinessClock(
        "Asia/Shanghai",
        datetime.fromisoformat("2026-07-29T09:00:00+08:00"),
    )
    set_clock(clock)

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    db = testing_session()
    user = User(
        username="tester",
        password_hash="not-used-by-token-tests",
        role="admin",
        created_at=clock.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    token = create_access_token({"sub": user.username, "role": user.role})
    headers = {"Authorization": f"Bearer {token}"}

    yield {
        "client": client,
        "headers": headers,
        "session": testing_session,
        "clock": clock,
        "user_id": user.id,
    }

    app.dependency_overrides.clear()
    client.close()
    engine.dispose()


def pytest_sessionfinish(session, exitstatus):
    if IMPORT_DB.exists():
        IMPORT_DB.unlink()
