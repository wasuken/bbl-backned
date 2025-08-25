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

# テスト用エンジン作成
test_engine = create_engine(
    test_settings.database_url,
    echo=False,  # テスト時はSQL出力を抑制
    pool_pre_ping=True,
    pool_recycle=300,
    # テスト用の最適化
    poolclass=StaticPool,
    connect_args={
        "check_same_thread": False  # SQLite用だが、MySQLでも無害
    },
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def wait_for_mysql(max_retries=30, delay=2):
    """MySQLの起動を待機"""
    for i in range(max_retries):
        try:
            # baseball_userで接続テスト
            test_conn = create_engine(
                "mysql+pymysql://baseball_user:baseball_pass@mysql:3306/mysql",
                echo=False,
            )
            with test_conn.connect() as conn:
                conn.execute(text("SELECT 1"))
            test_conn.dispose()
            return True
        except Exception as e:
            if i == max_retries - 1:
                print(f"MySQL connection failed after {max_retries} attempts: {e}")
                return False
            time.sleep(delay)
    return False


def create_test_database():
    """テスト用データベースを作成（権限を考慮した方法）"""
    print("Creating test database...")

    # MySQLの準備完了を待機
    if not wait_for_mysql():
        raise Exception("MySQL is not ready for test database creation")

    try:
        # 方法1: baseball_userで直接テスト用DBを作成（権限があれば）
        main_engine = create_engine(
            "mysql+pymysql://baseball_user:baseball_pass@mysql:3306/", echo=False
        )

        with main_engine.connect() as conn:
            # テスト用DB作成
            conn.execute(
                text(
                    "CREATE DATABASE IF NOT EXISTS baseball_game_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            conn.commit()

        main_engine.dispose()
        print("Test database created successfully with baseball_user")

    except OperationalError as e:
        print(f"Failed to create test database with baseball_user: {e}")

        # 方法2: rootで作成を試みる（複数のパスワードパターンを試行）
        root_passwords = ["rootpassword", "password", "root", ""]

        for password in root_passwords:
            try:
                if password:
                    root_engine = create_engine(
                        f"mysql+pymysql://root:{password}@mysql:3306/", echo=False
                    )
                else:
                    root_engine = create_engine(
                        "mysql+pymysql://root@mysql:3306/", echo=False
                    )

                with root_engine.connect() as conn:
                    # テスト用DB作成
                    conn.execute(
                        text(
                            "CREATE DATABASE IF NOT EXISTS baseball_game_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                        )
                    )

                    # baseball_userに権限付与
                    conn.execute(
                        text(
                            "GRANT ALL PRIVILEGES ON baseball_game_test.* TO 'baseball_user'@'%'"
                        )
                    )
                    conn.execute(text("FLUSH PRIVILEGES"))
                    conn.commit()

                root_engine.dispose()
                print(
                    f"Test database created successfully with root (password: {'[empty]' if not password else '[hidden]'})"
                )
                break

            except OperationalError as e:
                print(f"Failed with root password '{password}': {e}")
                if password == root_passwords[-1]:  # 最後の試行
                    # 最後の手段：既存のテスト用テーブルをクリアするだけ
                    print("Falling back to table-level cleanup...")
                    reset_test_data()
                    return


def drop_test_database():
    """テスト用データベースを削除"""
    # 削除は省略（クリーンアップはreset_test_dataで実行）
    pass


def create_test_tables():
    """テスト用テーブルを作成"""
    print("Creating test tables...")

    try:
        # 全テーブル作成
        game_models.Base.metadata.create_all(bind=test_engine)

        # 初期データ投入
        with TestSessionLocal() as db:
            # デフォルトパラメータバージョン作成
            from .services.logging_service import ParameterManager

            param_manager = ParameterManager()
            param_manager.create_default_version(db)

        print("Test tables created successfully")

    except Exception as e:
        print(f"Error creating test tables: {e}")
        raise


def drop_test_tables():
    """テスト用テーブルを削除"""
    try:
        game_models.Base.metadata.drop_all(bind=test_engine)
    except Exception as e:
        print(f"Error dropping test tables: {e}")


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
            # 全テーブルのデータをクリア（外部キー制約考慮した順序で）
            db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

            # 子テーブルから順に削除
            tables = [
                "pitches",
                "game_details",
                "player_statistics",
                "parameter_adjustments",
                "games",
                "simulation_runs",
                "strategy_stats",
                "parameter_versions",
            ]

            for table in tables:
                try:
                    db.execute(text(f"TRUNCATE TABLE {table}"))
                except Exception as table_error:
                    print(f"Warning: Could not truncate table {table}: {table_error}")
                    # テーブルが存在しない場合は無視
                    pass

            db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            db.commit()

        # 初期データ再投入
        with TestSessionLocal() as db:
            from .services.logging_service import ParameterManager

            param_manager = ParameterManager()
            param_manager.create_default_version(db)

        print("Test data reset successfully")

    except Exception as e:
        print(f"Error resetting test data: {e}")
        # エラーでも続行（テスト実行のため）
