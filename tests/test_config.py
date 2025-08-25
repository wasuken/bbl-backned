import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError
import time

from .database import Base, get_db
from .config import TestSettings
from .models import game as game_models
from .models import logging as logging_models

# テスト用設定
test_settings = TestSettings()

# テスト用エンジン作成 - 既存のデータベースを使用
test_engine = create_engine(
    "mysql+pymysql://baseball_user:baseball_pass@mysql:3306/baseball_game",  # メインDBを使用
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def wait_for_mysql(max_retries=30, delay=2):
    """MySQLの起動を待機"""
    print("Waiting for MySQL...")
    for i in range(max_retries):
        try:
            # 既存のデータベースへの接続テスト
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("MySQL connection successful!")
            return True
        except Exception as e:
            if i == max_retries - 1:
                print(f"MySQL connection failed after {max_retries} attempts: {e}")
                return False
            print(f"Attempt {i + 1}/{max_retries}: MySQL not ready...")
            time.sleep(delay)
    return False


def create_test_database():
    """テスト用データベース準備（既存DBを使用）"""
    print("Preparing test environment...")

    # MySQLの準備完了を待機
    if not wait_for_mysql():
        print("Warning: MySQL connection timeout, but continuing...")
        # テストを続行（既存の接続で動く可能性がある）

    # テーブルが存在しない場合は作成
    try:
        game_models.Base.metadata.create_all(bind=test_engine)
        print("Test tables ready!")
    except Exception as e:
        print(f"Warning: Table creation issue: {e}")


def drop_test_database():
    """テスト用データベースクリーンアップ"""
    print("Test cleanup completed")
    pass  # 既存DBを使用するため、削除は行わない


def create_test_tables():
    """テスト用テーブルを作成"""
    print("Setting up test tables...")

    try:
        # 全テーブル作成（存在しない場合のみ）
        game_models.Base.metadata.create_all(bind=test_engine)

        # 初期データ確認・作成
        with TestSessionLocal() as db:
            try:
                from .services.logging_service import ParameterManager

                param_manager = ParameterManager()

                # パラメータバージョンが存在するかチェック
                from .models.logging import ParameterVersion

                existing = (
                    db.query(ParameterVersion)
                    .filter(ParameterVersion.version == "1.0.0")
                    .first()
                )

                if not existing:
                    param_manager.create_default_version(db)
                    print("Default parameter version created")
                else:
                    print("Default parameter version already exists")

            except Exception as e:
                print(f"Warning: Parameter setup issue: {e}")

        print("Test tables setup completed!")

    except Exception as e:
        print(f"Warning: Table setup issue: {e}")
        # エラーでも続行


def drop_test_tables():
    """テスト用テーブルクリーンアップ"""
    # 本番DBを使用するため、テーブル削除は行わない
    pass


def get_test_db():
    """テスト用DB接続取得（FastAPI Dependency Override用）"""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_test_data():
    """テストデータをリセット"""
    print("Resetting test data...")

    try:
        with TestSessionLocal() as db:
            # テスト用のデータのみクリア（サンプルデータは保持）
            db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

            # テスト用データを識別して削除（より安全な方法）
            test_tables_data = {
                "pitches": "WHERE game_id LIKE 'test-%'",
                "game_details": "WHERE game_id LIKE 'test-%'",
                "games": "WHERE id LIKE 'test-%'",
                "player_statistics": "WHERE version LIKE 'test-%'",
                "parameter_adjustments": "WHERE new_version LIKE 'test-%'",
                "simulation_runs": "WHERE run_name LIKE 'test_%'",
            }

            for table, condition in test_tables_data.items():
                try:
                    db.execute(text(f"DELETE FROM {table} {condition}"))
                except Exception as table_error:
                    print(f"Warning: Could not clean table {table}: {table_error}")

            db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            db.commit()

        print("Test data reset completed!")

    except Exception as e:
        print(f"Warning: Test data reset issue: {e}")
        # エラーでも続行
