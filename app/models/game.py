from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Enum,
    ForeignKey,
    TIMESTAMP,
    DECIMAL,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class PitchTypeEnum(enum.Enum):
    fastball = "fastball"
    changeup = "changeup"
    slider = "slider"
    forkball = "forkball"


class GuessTypeEnum(enum.Enum):
    fastball = "fastball"
    changeup = "changeup"
    slider = "slider"
    forkball = "forkball"
    any = "any"


class ResultTypeEnum(enum.Enum):
    hit = "hit"
    strike = "strike"
    ball = "ball"
    foul = "foul"
    swing_miss = "swing_miss"


class GamePhaseEnum(enum.Enum):
    selecting = "selecting"
    result = "result"


class Game(Base):
    __tablename__ = "games"

    id = Column(String(36), primary_key=True)
    player_score = Column(Integer, default=0)
    cpu_score = Column(Integer, default=0)
    balls = Column(Integer, default=0)
    strikes = Column(Integer, default=0)
    outs = Column(Integer, default=0)
    inning = Column(Integer, default=1)
    is_player_pitching = Column(Boolean, default=True)
    game_phase = Column(Enum(GamePhaseEnum), default=GamePhaseEnum.selecting)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # リレーション
    pitches = relationship("Pitch", back_populates="game", cascade="all, delete-orphan")


class Pitch(Base):
    __tablename__ = "pitches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String(36), ForeignKey("games.id"), nullable=False)
    pitch_number = Column(Integer, nullable=False)

    # 投球データ
    pitch_type = Column(Enum(PitchTypeEnum), nullable=False)
    pitch_zone = Column(Integer, nullable=False)

    # 打者予想データ
    guess_type = Column(Enum(GuessTypeEnum), nullable=False)
    guess_zone = Column(Integer, nullable=False)

    # 結果
    result_type = Column(Enum(ResultTypeEnum), nullable=False)
    is_ball = Column(Boolean, nullable=False)

    # コンテキスト
    balls_before = Column(Integer, nullable=False)
    strikes_before = Column(Integer, nullable=False)
    outs_before = Column(Integer, nullable=False)
    inning = Column(Integer, nullable=False)
    is_pitcher_player = Column(Boolean, nullable=False)

    created_at = Column(TIMESTAMP, server_default=func.now())

    # リレーション
    game = relationship("Game", back_populates="pitches")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_name = Column(String(100), nullable=False)
    strategy_a = Column(String(50), nullable=False)
    strategy_b = Column(String(50), nullable=False)
    iterations = Column(Integer, nullable=False)
    strategy_a_wins = Column(Integer, default=0)
    strategy_b_wins = Column(Integer, default=0)
    total_games = Column(Integer, default=0)
    avg_score_a = Column(DECIMAL(4, 2), default=0)
    avg_score_b = Column(DECIMAL(4, 2), default=0)
    completed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


class StrategyStats(Base):
    __tablename__ = "strategy_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(50), nullable=False)
    pitch_type = Column(Enum(PitchTypeEnum), nullable=False)
    context_balls = Column(Integer, nullable=False)
    context_strikes = Column(Integer, nullable=False)
    usage_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    hit_count = Column(Integer, default=0)
