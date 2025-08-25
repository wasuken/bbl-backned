import os
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # データベース設定
    database_url: str = (
        "mysql+pymysql://baseball_user:baseball_pass@mysql:3306/baseball_game"
    )
    test_database_url: str = (
        "mysql+pymysql://baseball_user:baseball_pass@mysql:3306/baseball_game_test"
    )

    # 環境設定
    environment: str = "development"
    debug: bool = True

    # API設定
    api_title: str = "Baseball Game API"
    api_version: str = "1.0.0"

    # テスト用：直接バックエンドのポートを使用
    api_host: str = "localhost"
    api_port: int = 8000

    # CORS設定 - カンマ区切りの文字列として受け取り
    cors_origins_str: str = "http://localhost:3000,http://localhost:5173,http://localhost:8501,http://localhost:3232"

    # CORS設定をリストに変換するプロパティ
    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins_str.split(",")]

    # API ベースURL
    @property
    def api_base_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"

    class Config:
        env_file = ".env"
        case_sensitive = False


class TestSettings(Settings):
    """テスト用設定"""

    environment: str = "testing"
    debug: bool = True
    database_url: str = (
        "mysql+pymysql://baseball_user:baseball_pass@mysql:3306/baseball_game_test"
    )

    # テスト用：直接バックエンドにアクセス
    api_host: str = "localhost"
    api_port: int = 8000


# 設定インスタンス取得
def get_settings() -> Settings:
    env = os.getenv("ENVIRONMENT", "development")

    if env == "testing":
        return TestSettings()
    else:
        return Settings()


settings = get_settings()
