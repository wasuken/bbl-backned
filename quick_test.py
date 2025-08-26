#!/usr/bin/env python3
"""
クイックテストスクリプト - 問題の特定用
"""

import sys
import os


def test_basic_setup():
    """基本セットアップテスト"""
    print("🔍 Testing basic setup...")

    # 環境変数
    print(f"ENVIRONMENT: {os.environ.get('ENVIRONMENT', 'NOT SET')}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'NOT SET')}")

    # インポートテスト
    try:
        import pymysql

        print("✅ pymysql imported")

        from app.main import app

        print("✅ FastAPI app imported")

        from app.database import engine

        print("✅ Database engine imported")

        from app.models import game

        print("✅ Game models imported")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

    return True


def test_mysql_connection():
    """MySQL接続テスト"""
    print("🔍 Testing MySQL connection...")

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

        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        print(f"✅ MySQL connection successful: {result}")
        return True

    except Exception as e:
        print(f"❌ MySQL connection failed: {e}")
        return False


def test_sqlalchemy_connection():
    """SQLAlchemy接続テスト"""
    print("🔍 Testing SQLAlchemy connection...")

    try:
        from app.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION() as version"))
            row = result.fetchone()
            print(f"✅ SQLAlchemy connection successful. MySQL version: {row[0]}")
            return True

    except Exception as e:
        print(f"❌ SQLAlchemy connection failed: {e}")
        return False


def test_table_creation():
    """テーブル作成テスト"""
    print("🔍 Testing table creation...")

    try:
        from app.database import engine
        from app.models import game
        from sqlalchemy import text

        # テーブル作成
        game.Base.metadata.create_all(bind=engine)

        # テーブル確認
        with engine.connect() as conn:
            result = conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            print(f"✅ Tables created: {tables}")

            if "games" not in tables:
                print("❌ 'games' table not found")
                return False

        return True

    except Exception as e:
        print(f"❌ Table creation failed: {e}")
        return False


def test_api_startup():
    """API起動テスト"""
    print("🔍 Testing API startup...")

    try:
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/")

        print(f"✅ API response: {response.status_code} - {response.json()}")

        if response.status_code != 200:
            print("❌ API not responding correctly")
            return False

        return True

    except Exception as e:
        print(f"❌ API startup failed: {e}")
        return False


def main():
    """メイン実行"""
    print("🚀 Running quick diagnostic tests...\n")

    tests = [
        ("Basic Setup", test_basic_setup),
        ("MySQL Connection", test_mysql_connection),
        ("SQLAlchemy Connection", test_sqlalchemy_connection),
        ("Table Creation", test_table_creation),
        ("API Startup", test_api_startup),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 50)
    print("📋 DIAGNOSTIC RESULTS")
    print("=" * 50)

    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:10} {test_name}")
        if not success:
            all_passed = False

    print("=" * 50)

    if all_passed:
        print("🎉 All diagnostics passed! Tests should work now.")
        print("💡 Try running: python -m pytest tests/test_minimal.py -v")
    else:
        print("❌ Some diagnostics failed. Check the errors above.")
        print("💡 Most likely MySQL connection issue.")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
