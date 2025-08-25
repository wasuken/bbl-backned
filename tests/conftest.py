import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# テスト環境設定
os.environ["ENVIRONMENT"] = "testing"

from app.main import app
from app.database import get_db
from app.config import get_settings
from app.test_database import (
    get_test_db,
    create_test_database,
    drop_test_database,
    create_test_tables,
    drop_test_tables,
    reset_test_data,
    TestSessionLocal,
)

# テスト用設定
test_settings = get_settings()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """テスト開始時にテスト用DBを作成"""
    print("\n=== Setting up test database ===")
    create_test_database()
    create_test_tables()
    yield
    print("\n=== Tearing down test database ===")
    drop_test_database()


@pytest.fixture(scope="function")
def db_session():
    """各テスト関数用のDBセッション"""
    reset_test_data()
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPIテストクライアント"""

    # DI override
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # テスト後にDI overrideをクリア
    app.dependency_overrides = {}


@pytest.fixture
def sample_game_data():
    """サンプルゲームデータ"""
    return {"player_pitching": True, "player_score": 3, "cpu_score": 2, "inning": 5}


@pytest.fixture
def sample_pitch_data():
    """サンプル投球データ"""
    return {"player_pitch": {"type": "fastball", "zone": 5}}


@pytest.fixture
def sample_guess_data():
    """サンプル予想データ"""
    return {"player_guess": {"type": "fastball", "zone": 5}}
