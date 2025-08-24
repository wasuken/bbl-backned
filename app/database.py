from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
import os

# 環境変数からDB接続情報を取得
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://baseball_user:baseball_pass@mysql:3306/baseball_game",
)

# SQLAlchemy エンジン作成
engine = create_engine(
    DATABASE_URL,
    echo=True,  # 開発時はSQL出力
    pool_pre_ping=True,  # 接続確認
    pool_recycle=300,  # 5分で接続リサイクル
)

# セッションファクトリ
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Session:
    """データベースセッション取得（FastAPI Dependency）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """データベース初期化"""
    from .models import game

    game.Base.metadata.create_all(bind=engine)
