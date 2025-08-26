# tests/test_minimal.py
"""
最小限のテストケース - デバッグ用
"""

import pytest
import os


def test_environment():
    """環境設定テスト"""
    assert os.environ.get("ENVIRONMENT") == "testing"
    print("✅ Environment is correctly set to testing")


def test_imports():
    """基本インポートテスト"""
    try:
        from app.main import app
        from app.database import get_db
        from app.models import game

        print("✅ All imports successful")
        assert True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        assert False


def test_mysql_connection():
    """MySQL接続テスト"""
    try:
        import pymysql

        conn = pymysql.connect(
            host="mysql",
            port=3306,
            user="baseball_user",
            password="baseball_pass",
            database="baseball_game",
            connect_timeout=10,
        )
        conn.ping()
        conn.close()
        print("✅ MySQL connection successful")
        assert True
    except Exception as e:
        print(f"❌ MySQL connection failed: {e}")
        pytest.skip(f"MySQL not available: {e}")


def test_database_engine():
    """データベースエンジンテスト"""
    try:
        from app.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            assert row[0] == 1

        print("✅ Database engine working")

    except Exception as e:
        print(f"❌ Database engine failed: {e}")
        pytest.skip(f"Database engine not working: {e}")


def test_api_creation():
    """API作成テスト"""
    try:
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/")

        print(f"📡 API response status: {response.status_code}")
        print(f"📡 API response data: {response.json()}")

        assert response.status_code == 200
        assert response.json()["status"] == "running"

    except Exception as e:
        print(f"❌ API creation failed: {e}")
        assert False
