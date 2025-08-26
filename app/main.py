from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uuid
from typing import Optional

from .database import get_db, engine
from .models import game as game_models
from .models import logging as logging_models
from .schemas import game as game_schemas
from .services.game_engine import GameEngine
from .services.logging_service import ParameterManager, GameLogger
from .routers.logging import router as logging_router

# テーブル作成（同じBaseを使用）
game_models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Baseball Game API", version="1.0.0")

# カスタムOpenAPI関数を削除して、デフォルトを使用

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# サービス初期化
game_engine = GameEngine()
param_manager = ParameterManager()
game_logger = GameLogger(param_manager)

# ログAPIルーターを追加
app.include_router(logging_router)


@app.get("/")
def read_root():
    return {"message": "Baseball Game API", "status": "running"}


@app.post("/game/start", response_model=game_schemas.GameStateResponse)
def start_game(request: game_schemas.StartGameRequest, db: Session = Depends(get_db)):
    """新しいゲームを開始"""
    game_id = str(uuid.uuid4())

    # DB にゲーム状態を保存
    db_game = game_models.Game(id=game_id, is_player_pitching=request.player_pitching)
    db.add(db_game)
    db.commit()

    return game_schemas.GameStateResponse(
        game_id=game_id,
        balls=0,
        strikes=0,
        outs=0,
        inning=1,
        score=game_schemas.Score(player=0, cpu=0),
        is_player_pitching=request.player_pitching,
        game_phase="selecting",
    )


@app.get("/game/{game_id}/state", response_model=game_schemas.GameStateResponse)
def get_game_state(game_id: str, db: Session = Depends(get_db)):
    """ゲーム状態を取得"""
    db_game = db.query(game_models.Game).filter(game_models.Game.id == game_id).first()
    if not db_game:
        raise HTTPException(status_code=404, detail="Game not found")

    return game_schemas.GameStateResponse(
        game_id=game_id,
        balls=db_game.balls,
        strikes=db_game.strikes,
        outs=db_game.outs,
        inning=db_game.inning,
        score=game_schemas.Score(player=db_game.player_score, cpu=db_game.cpu_score),
        is_player_pitching=db_game.is_player_pitching,
        game_phase=db_game.game_phase,
    )


@app.post("/game/{game_id}/pitch", response_model=game_schemas.PitchResultResponse)
def execute_pitch(
    game_id: str, request: game_schemas.PitchRequest, db: Session = Depends(get_db)
):
    """投球を実行（メインロジック）"""
    db_game = db.query(game_models.Game).filter(game_models.Game.id == game_id).first()
    if not db_game:
        raise HTTPException(status_code=404, detail="Game not found")

    # 投球とバッティングを決定
    if db_game.is_player_pitching:
        if not request.player_pitch:
            raise HTTPException(status_code=400, detail="Player pitch required")
        actual_pitch = request.player_pitch
        batter_guess = game_engine.generate_cpu_guess(
            {
                "balls": db_game.balls,
                "strikes": db_game.strikes,
                "inning": db_game.inning,
            }
        )
    else:
        if not request.player_guess:
            raise HTTPException(status_code=400, detail="Player guess required")
        actual_pitch = game_engine.generate_cpu_pitch(
            {
                "balls": db_game.balls,
                "strikes": db_game.strikes,
                "inning": db_game.inning,
            }
        )
        batter_guess = request.player_guess

    # 結果計算
    result_type, is_ball = game_engine.calculate_result(actual_pitch, batter_guess)
    result_display = game_engine.get_result_display(result_type, is_ball)

    # ゲーム状態更新
    updated_state = game_engine.update_game_state(
        current_state=db_game, result_type=result_type, is_ball=is_ball
    )

    # DB更新
    db_game.balls = updated_state["balls"]
    db_game.strikes = updated_state["strikes"]
    db_game.outs = updated_state["outs"]
    db_game.player_score = updated_state["score"]["player"]
    db_game.cpu_score = updated_state["score"]["cpu"]
    db_game.game_phase = "result"

    # 投球履歴を保存
    pitch_record = game_models.Pitch(
        game_id=game_id,
        pitch_number=len(db_game.pitches) + 1,
        pitch_type=actual_pitch.type,
        pitch_zone=actual_pitch.zone,
        guess_type=batter_guess.type,
        guess_zone=batter_guess.zone,
        result_type=result_type,
        is_ball=is_ball,
        balls_before=db_game.balls,
        strikes_before=db_game.strikes,
        outs_before=db_game.outs,
        inning=db_game.inning,
        is_pitcher_player=db_game.is_player_pitching,
    )
    db.add(pitch_record)
    db.commit()

    return game_schemas.PitchResultResponse(
        actual_pitch=actual_pitch,
        batter_guess=batter_guess,
        result=result_display,
        updated_state=game_schemas.GameStateResponse(
            game_id=game_id,
            balls=updated_state["balls"],
            strikes=updated_state["strikes"],
            outs=updated_state["outs"],
            inning=updated_state["inning"],
            score=game_schemas.Score(
                player=updated_state["score"]["player"],
                cpu=updated_state["score"]["cpu"],
            ),
            is_player_pitching=db_game.is_player_pitching,
            game_phase="result",
        ),
    )


@app.post("/game/{game_id}/next-pitch")
def next_pitch(game_id: str, db: Session = Depends(get_db)):
    """次の投球に進む"""
    db_game = db.query(game_models.Game).filter(game_models.Game.id == game_id).first()
    if not db_game:
        raise HTTPException(status_code=404, detail="Game not found")

    db_game.game_phase = "selecting"
    db.commit()

    return {"status": "ready_for_next_pitch"}


@app.post("/game/{game_id}/toggle-pitching")
def toggle_pitching(game_id: str, db: Session = Depends(get_db)):
    """攻守交代"""
    db_game = db.query(game_models.Game).filter(game_models.Game.id == game_id).first()
    if not db_game:
        raise HTTPException(status_code=404, detail="Game not found")

    db_game.is_player_pitching = not db_game.is_player_pitching
    db_game.balls = 0
    db_game.strikes = 0
    db_game.game_phase = "selecting"
    db.commit()

    return {
        "status": "pitching_toggled",
        "is_player_pitching": db_game.is_player_pitching,
    }


@app.post("/game/{game_id}/end")
def end_game(game_id: str, db: Session = Depends(get_db)):
    """ゲーム終了（ログに記録）"""
    db_game = db.query(game_models.Game).filter(game_models.Game.id == game_id).first()
    if not db_game:
        raise HTTPException(status_code=404, detail="Game not found")

    # ゲーム完了をログに記録
    try:
        game_detail = game_logger.log_game_completion(
            db=db, game=db_game, game_type=logging_models.GameTypeEnum.player_vs_cpu
        )

        return {
            "status": "game_ended",
            "final_score": {"player": db_game.player_score, "cpu": db_game.cpu_score},
            "winner": game_detail.winner.value,
            "version": game_detail.version,
            "game_detail_id": game_detail.id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log game: {str(e)}")


# 統計API
@app.get("/stats/pitch-effectiveness")
def get_pitch_effectiveness(db: Session = Depends(get_db)):
    """球種別効果統計"""
    results = db.query(
        game_models.Pitch.pitch_type,
        game_models.Pitch.result_type,
        game_models.Pitch.is_ball,
    ).all()

    stats = game_engine.analyze_pitch_effectiveness(results)
    return stats


@app.get("/stats/game/{game_id}/history")
def get_game_history(game_id: str, db: Session = Depends(get_db)):
    """ゲーム履歴取得"""
    pitches = (
        db.query(game_models.Pitch)
        .filter(game_models.Pitch.game_id == game_id)
        .order_by(game_models.Pitch.pitch_number)
        .all()
    )

    return [
        {
            "pitch_number": p.pitch_number,
            "pitch": {"type": p.pitch_type, "zone": p.pitch_zone},
            "guess": {"type": p.guess_type, "zone": p.guess_zone},
            "result": p.result_type,
            "context": {
                "balls": p.balls_before,
                "strikes": p.strikes_before,
                "outs": p.outs_before,
            },
        }
        for p in pitches
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
