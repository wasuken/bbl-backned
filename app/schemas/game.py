from pydantic import BaseModel
from typing import Optional, Literal
from enum import Enum


class PitchType(str, Enum):
    fastball = "fastball"
    changeup = "changeup"
    slider = "slider"
    forkball = "forkball"


class GuessType(str, Enum):
    fastball = "fastball"
    changeup = "changeup"
    slider = "slider"
    forkball = "forkball"
    any = "any"


class ResultType(str, Enum):
    hit = "hit"
    strike = "strike"
    ball = "ball"
    foul = "foul"
    swing_miss = "swing_miss"


class GamePhase(str, Enum):
    selecting = "selecting"
    result = "result"


class Pitch(BaseModel):
    type: PitchType
    zone: int  # 1-17


class Guess(BaseModel):
    type: GuessType
    zone: int  # 1-9


class Score(BaseModel):
    player: int
    cpu: int


class GameResult(BaseModel):
    type: str
    description: str
    icon: str
    color: str


class StartGameRequest(BaseModel):
    player_pitching: bool = True


class PitchRequest(BaseModel):
    player_pitch: Optional[Pitch] = None
    player_guess: Optional[Guess] = None


class GameStateResponse(BaseModel):
    game_id: str
    balls: int
    strikes: int
    outs: int
    inning: int
    score: Score
    is_player_pitching: bool
    game_phase: GamePhase


class PitchResultResponse(BaseModel):
    actual_pitch: Pitch
    batter_guess: Guess
    result: GameResult
    updated_state: GameStateResponse


# シミュレーション用
class SimulationRequest(BaseModel):
    iterations: int = 1000
    strategy_a: str = "default"
    strategy_b: str = "default"


class SimulationResult(BaseModel):
    run_id: int
    strategy_a_wins: int
    strategy_b_wins: int
    total_games: int
    win_rate_a: float
    avg_score_a: float
    avg_score_b: float


class PitchStats(BaseModel):
    pitch_type: PitchType
    usage_rate: float
    strike_rate: float
    hit_rate: float
    success_rate: float
