from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func  # 追加
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from ..database import get_db
from ..services.logging_service import ParameterManager, GameLogger, StatisticsService
from ..models.game import Game
from ..models.logging import (
    ParameterVersion,
    GameDetail,
    PlayerStatistics,
    GameTypeEnum,
    PlayerTypeEnum,
    WinnerEnum,  # 追加
)
from pydantic import BaseModel

router = APIRouter(prefix="/api/logging", tags=["logging"])

# 依存性注入用のサービス
param_manager = ParameterManager()
game_logger = GameLogger(param_manager)
stats_service = StatisticsService(param_manager)


class ParameterVersionResponse(BaseModel):
    version: str
    parameters: Dict[str, Any]
    created_at: datetime
    created_by: str
    description: Optional[str]
    is_active: bool


class CreateVersionRequest(BaseModel):
    new_version: str
    base_version: str
    parameter_changes: Dict[str, Any]
    description: str = ""
    created_by: str = "admin"


class GameDetailResponse(BaseModel):
    id: int
    game_id: str
    version: str
    game_type: str
    final_player_score: int
    final_cpu_score: int
    winner: str
    total_pitches: int
    hits_player: int
    hits_cpu: int
    completed_at: datetime


class StatisticsResponse(BaseModel):
    version: str
    player_type: str
    games_played: int
    batting_avg: float
    win_rate: float
    date_from: date
    date_to: date


# パラメータ管理エンドポイント
@router.get("/parameters/versions", response_model=List[ParameterVersionResponse])
def get_all_versions(db: Session = Depends(get_db)):
    """全パラメータバージョンを取得"""
    versions = (
        db.query(ParameterVersion).order_by(ParameterVersion.created_at.desc()).all()
    )

    return [
        ParameterVersionResponse(
            version=v.version,
            parameters=v.parameters,
            created_at=v.created_at,
            created_by=v.created_by,
            description=v.description,
            is_active=v.is_active,
        )
        for v in versions
    ]


@router.get("/parameters/current")
def get_current_parameters(db: Session = Depends(get_db)):
    """現在のアクティブパラメータを取得"""
    current_version = param_manager.get_current_version(db)
    parameters = param_manager.get_parameters(db, current_version)

    return {"version": current_version, "parameters": parameters}


@router.get("/parameters/{version}")
def get_parameters_by_version(version: str, db: Session = Depends(get_db)):
    """指定バージョンのパラメータを取得"""
    parameters = param_manager.get_parameters(db, version)
    if not parameters:
        raise HTTPException(status_code=404, detail="Version not found")

    return {"version": version, "parameters": parameters}


@router.post("/parameters/versions", response_model=ParameterVersionResponse)
def create_new_version(request: CreateVersionRequest, db: Session = Depends(get_db)):
    """新しいパラメータバージョンを作成"""
    try:
        new_version = param_manager.create_new_version(
            db=db,
            new_version=request.new_version,
            base_version=request.base_version,
            parameter_changes=request.parameter_changes,
            description=request.description,
            created_by=request.created_by,
        )

        return ParameterVersionResponse(
            version=new_version.version,
            parameters=new_version.parameters,
            created_at=new_version.created_at,
            created_by=new_version.created_by,
            description=new_version.description,
            is_active=new_version.is_active,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/parameters/{version}/activate")
def activate_version(version: str, db: Session = Depends(get_db)):
    """指定バージョンをアクティブ化"""
    # 現在のアクティブ版を非アクティブ化
    db.query(ParameterVersion).filter(ParameterVersion.is_active == True).update(
        {"is_active": False}
    )

    # 指定版をアクティブ化
    result = (
        db.query(ParameterVersion)
        .filter(ParameterVersion.version == version)
        .update({"is_active": True})
    )

    if result == 0:
        raise HTTPException(status_code=404, detail="Version not found")

    db.commit()

    return {"status": "activated", "version": version}


# ゲームログエンドポイント
@router.post("/games/{game_id}/complete")
def complete_game(
    game_id: str,
    game_type: GameTypeEnum = GameTypeEnum.player_vs_cpu,
    simulation_run_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """ゲーム完了をログに記録"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # ゲーム完了時間を計算（簡易版）
    game_duration = int((datetime.now() - game.created_at).total_seconds())

    game_detail = game_logger.log_game_completion(
        db=db,
        game=game,
        game_type=game_type,
        simulation_run_id=simulation_run_id,
        game_duration_seconds=game_duration,
    )

    return {
        "status": "logged",
        "game_detail_id": game_detail.id,
        "winner": game_detail.winner.value,
        "version": game_detail.version,
    }


@router.get("/games/recent", response_model=List[Dict[str, Any]])
def get_recent_games(
    version: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)
):
    """最近のゲーム結果を取得"""
    return stats_service.get_recent_games(db, version, limit)


@router.get("/games/details/{game_id}", response_model=GameDetailResponse)
def get_game_detail(game_id: str, db: Session = Depends(get_db)):
    """ゲーム詳細を取得"""
    detail = db.query(GameDetail).filter(GameDetail.game_id == game_id).first()

    if not detail:
        raise HTTPException(status_code=404, detail="Game detail not found")

    return GameDetailResponse(
        id=detail.id,
        game_id=detail.game_id,
        version=detail.version,
        game_type=detail.game_type.value,
        final_player_score=detail.final_player_score,
        final_cpu_score=detail.final_cpu_score,
        winner=detail.winner.value,
        total_pitches=detail.total_pitches,
        hits_player=detail.hits_player,
        hits_cpu=detail.hits_cpu,
        completed_at=detail.completed_at,
    )


# 統計エンドポイント
@router.get("/statistics/versions/comparison")
def get_version_comparison(versions: List[str], db: Session = Depends(get_db)):
    """バージョン間比較統計"""
    return stats_service.get_version_comparison(db, versions)


@router.get("/statistics/{version}/players", response_model=List[StatisticsResponse])
def get_player_statistics(version: str, db: Session = Depends(get_db)):
    """プレイヤー統計を取得"""
    stats = db.query(PlayerStatistics).filter(PlayerStatistics.version == version).all()

    return [
        StatisticsResponse(
            version=s.version,
            player_type=s.player_type.value,
            games_played=s.games_played,
            batting_avg=float(s.batting_avg),
            win_rate=float(s.win_rate),
            date_from=s.date_from,
            date_to=s.date_to,
        )
        for s in stats
    ]


@router.get("/statistics/{version}/pitches")
def get_pitch_analysis(version: Optional[str] = None, db: Session = Depends(get_db)):
    """投球分析統計"""
    return stats_service.get_pitch_analysis(db, version)


@router.get("/statistics/dashboard")
def get_dashboard_data(db: Session = Depends(get_db)):
    """管理画面ダッシュボード用データ"""
    current_version = param_manager.get_current_version(db)

    # 今日のゲーム数
    today = date.today()
    today_games = (
        db.query(GameDetail)
        .filter(
            GameDetail.version == current_version,
            func.date(GameDetail.completed_at) == today,
        )
        .count()
    )

    # 全体統計
    total_games = (
        db.query(GameDetail).filter(GameDetail.version == current_version).count()
    )

    # プレイヤー勝率
    player_wins = (
        db.query(GameDetail)
        .filter(
            GameDetail.version == current_version,
            GameDetail.winner == WinnerEnum.player,
        )
        .count()
    )

    win_rate = player_wins / total_games if total_games > 0 else 0

    # 最近のアクティビティ
    recent_games = stats_service.get_recent_games(db, current_version, 5)

    return {
        "current_version": current_version,
        "today_games": today_games,
        "total_games": total_games,
        "player_win_rate": win_rate,
        "recent_activity": recent_games,
        "pitch_analysis": stats_service.get_pitch_analysis(db, current_version),
    }
