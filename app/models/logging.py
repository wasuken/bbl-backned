from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Enum,
    ForeignKey,
    TIMESTAMP,
    DECIMAL,
    Text,
    BigInteger,
    JSON,
    Date,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

# 既存のgame.pyからBaseをインポート
from .game import Base


class GameTypeEnum(enum.Enum):
    player_vs_cpu = "player_vs_cpu"
    simulation = "simulation"
    cpu_vs_cpu = "cpu_vs_cpu"


class WinnerEnum(enum.Enum):
    player = "player"
    cpu = "cpu"
    tie = "tie"


class AdjustmentTypeEnum(enum.Enum):
    manual = "manual"
    learning = "learning"
    simulation_based = "simulation_based"


class PlayerTypeEnum(enum.Enum):
    human = "human"
    cpu = "cpu"


class ParameterVersion(Base):
    __tablename__ = "parameter_versions"

    version = Column(String(20), primary_key=True)
    parameters = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    created_by = Column(String(50), default="system")
    description = Column(Text)
    is_active = Column(Boolean, default=False)

    # リレーション
    game_details = relationship("GameDetail", back_populates="parameter_version")
    adjustments_as_base = relationship(
        "ParameterAdjustment",
        foreign_keys="ParameterAdjustment.base_version",
        back_populates="base_version_rel",
    )
    adjustments_as_new = relationship(
        "ParameterAdjustment",
        foreign_keys="ParameterAdjustment.new_version",
        back_populates="new_version_rel",
    )


class GameDetail(Base):
    __tablename__ = "game_details"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    game_id = Column(String(36), ForeignKey("games.id"), nullable=False)
    version = Column(
        String(20), ForeignKey("parameter_versions.version"), nullable=False
    )
    game_type = Column(Enum(GameTypeEnum), default=GameTypeEnum.player_vs_cpu)

    # 最終結果
    final_player_score = Column(Integer, nullable=False)
    final_cpu_score = Column(Integer, nullable=False)
    total_innings = Column(Integer, default=9)
    winner = Column(Enum(WinnerEnum), nullable=False)

    # ゲーム統計
    total_pitches = Column(Integer, default=0)
    hits_player = Column(Integer, default=0)
    hits_cpu = Column(Integer, default=0)
    errors_player = Column(Integer, default=0)
    errors_cpu = Column(Integer, default=0)

    # パフォーマンス指標
    game_duration_seconds = Column(Integer)

    # メタデータ
    completed_at = Column(TIMESTAMP, server_default=func.now())
    simulation_run_id = Column(Integer, ForeignKey("simulation_runs.id"), nullable=True)

    # リレーション
    parameter_version = relationship("ParameterVersion", back_populates="game_details")
    # 既存のGameモデルは同じBaseなので問題なし
    simulation_run = relationship("SimulationRun", back_populates="game_details")


class PlayerStatistics(Base):
    __tablename__ = "player_statistics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    version = Column(
        String(20), ForeignKey("parameter_versions.version"), nullable=False
    )
    player_type = Column(Enum(PlayerTypeEnum), nullable=False)

    # 集計期間
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)

    # 打撃成績
    games_played = Column(Integer, default=0)
    at_bats = Column(Integer, default=0)
    hits = Column(Integer, default=0)
    batting_avg = Column(DECIMAL(4, 3), default=0.000)

    # 投球成績
    innings_pitched = Column(DECIMAL(4, 1), default=0.0)
    earned_runs = Column(Integer, default=0)
    era = Column(DECIMAL(4, 2), default=0.00)
    strikeouts = Column(Integer, default=0)
    walks = Column(Integer, default=0)

    # 勝敗
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    win_rate = Column(DECIMAL(4, 3), default=0.000)

    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # リレーション
    parameter_version = relationship("ParameterVersion")


class ParameterAdjustment(Base):
    __tablename__ = "parameter_adjustments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    base_version = Column(
        String(20), ForeignKey("parameter_versions.version"), nullable=False
    )
    new_version = Column(
        String(20), ForeignKey("parameter_versions.version"), nullable=False
    )
    adjustment_type = Column(Enum(AdjustmentTypeEnum), nullable=False)

    # 調整内容
    parameter_changes = Column(JSON, nullable=False)
    reason = Column(Text)

    # 調整結果の予測/実績
    expected_impact = Column(JSON)
    actual_impact = Column(JSON)

    created_at = Column(TIMESTAMP, server_default=func.now())
    created_by = Column(String(50), default="system")

    # リレーション
    base_version_rel = relationship(
        "ParameterVersion",
        foreign_keys=[base_version],
        back_populates="adjustments_as_base",
    )
    new_version_rel = relationship(
        "ParameterVersion",
        foreign_keys=[new_version],
        back_populates="adjustments_as_new",
    )
