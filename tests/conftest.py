import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import time

# テスト環境設定
os.environ["ENVIRONMENT"] = "testing"

from app.main import app
from app.database import get_db
from app.models import game as game_models

# テスト用データベース接続設定（コンテナ内から）
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+pymysql://baseball_user:baseball_pass@mysql:3306/baseball_game_test",
)

print(f"📊 Test database URL: {TEST_DATABASE_URL}")

if not TEST_DATABASE_URL:
    raise ValueError("TEST_DATABASE_URL is not set")

# テスト用エンジン作成
test_engine = create_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def test_mysql_connection():
    """MySQL接続テスト"""
    print("🔍 Testing MySQL connection...")
    try:
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            print(f"✅ MySQL connection successful: {row}")
            return True
    except Exception as e:
        print(f"❌ MySQL connection failed: {e}")
        return False


def create_test_environment():
    """テスト環境作成"""
    print("🔧 Setting up test environment...")

    # MySQL接続確認
    if not test_mysql_connection():
        print("❌ Cannot connect to MySQL, skipping tests")
        pytest.skip("MySQL is not available")
        return False

    try:
        # テーブル作成
        print("📋 Creating tables...")
        game_models.Base.metadata.create_all(bind=test_engine)

        # 初期データ作成
        print("📊 Setting up initial data...")
        with TestSessionLocal() as db:
            try:
                from app.services.logging_service import ParameterManager
                from app.models.logging import ParameterVersion

                param_manager = ParameterManager()

                # デフォルトバージョンの存在確認
                existing = (
                    db.query(ParameterVersion)
                    .filter(ParameterVersion.version == "1.0.0")
                    .first()
                )

                if not existing:
                    print("📝 Creating default parameter version...")
                    param_manager.create_default_version(db)
                else:
                    print("✅ Default parameter version already exists")

            except Exception as e:
                print(f"⚠️  Parameter setup warning: {e}")

        print("✅ Test environment ready!")
        return True

    except Exception as e:
        print(f"❌ Test environment setup failed: {e}")
        pytest.skip(f"Cannot setup test environment: {e}")
        return False


@pytest.fixture(scope="session", autouse=True)
def setup_test_session():
    """テストセッション全体の初期化"""
    print("\n=== Test Session Setup ===")

    # 環境確認
    print(f"Environment: {os.environ.get('ENVIRONMENT', 'unknown')}")
    print(f"Python path: {os.environ.get('PYTHONPATH', 'unknown')}")

    # テスト環境作成
    create_test_environment()

    yield

    print("\n=== Test Session Teardown ===")


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_data():
    """各テスト前後でデータクリーンアップ"""
    # テスト前クリーンアップ
    _cleanup_data()
    yield
    # テスト後クリーンアップ
    _cleanup_data()


def _cleanup_data():
    """テストデータをクリーンアップ"""
    try:
        with TestSessionLocal() as db:
            # 外部キー制約を一時的に無効化
            db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

            # テストで作成されたデータを削除
            db.execute(text("DELETE FROM pitches"))
            db.execute(text("DELETE FROM game_details"))
            db.execute(text("DELETE FROM games"))
            db.execute(text("DELETE FROM player_statistics"))
            db.execute(text("DELETE FROM parameter_adjustments"))

            # parameter_versionsは1.0.0以外を削除
            db.execute(text("DELETE FROM parameter_versions WHERE version != '1.0.0'"))

            # 1.0.0をアクティブに設定
            db.execute(
                text(
                    "UPDATE parameter_versions SET is_active = TRUE WHERE version = '1.0.0'"
                )
            )

            # 外部キー制約を再有効化
            db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

            db.commit()

    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")


@pytest.fixture(scope="function")
def db_session():
    """各テスト用のDBセッション"""
    print("🗃️  Creating test database session...")

    # MySQL接続確認
    if not test_mysql_connection():
        pytest.skip("MySQL connection failed")

    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPIテストクライアント"""
    print("🌐 Creating test client...")

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        # 接続テスト
        try:
            response = test_client.get("/")
            print(f"📡 API connection test: {response.status_code}")
        except Exception as e:
            print(f"⚠️  API connection warning: {e}")

        yield test_client

    # クリーンアップ
    app.dependency_overrides = {}


# シンプルなサンプルデータ
@pytest.fixture
def sample_game_data():
    return {"player_pitching": True}


@pytest.fixture
def sample_pitch_data():
    return {"player_pitch": {"type": "fastball", "zone": 5}}


@pytest.fixture
def sample_guess_data():
    return {"player_guess": {"type": "fastball", "zone": 5}}
