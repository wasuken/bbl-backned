import json
import os
from datetime import datetime, date
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.game import Game, Pitch, SimulationRun  # SimulationRun追加
from ..models.logging import (
    ParameterVersion,
    GameDetail,
    PlayerStatistics,
    ParameterAdjustment,
    GameTypeEnum,
    WinnerEnum,
    PlayerTypeEnum,
    AdjustmentTypeEnum,
)


class ParameterManager:
    """パラメータバージョン管理"""

    def __init__(self):
        self.shared_path = "/shared/config"

    def get_current_version(self, db: Session) -> str:
        """現在のアクティブバージョンを取得"""
        version = (
            db.query(ParameterVersion)
            .filter(ParameterVersion.is_active == True)
            .first()
        )

        if not version:
            # デフォルトバージョンを作成
            return self.create_default_version(db)

        return version.version

    def get_parameters(self, db: Session, version: str = None) -> Dict[str, Any]:
        """指定バージョンのパラメータを取得"""
        if not version:
            version = self.get_current_version(db)

        param_version = (
            db.query(ParameterVersion)
            .filter(ParameterVersion.version == version)
            .first()
        )

        if param_version:
            return param_version.parameters
        else:
            return self.get_default_parameters()

    def create_default_version(self, db: Session) -> str:
        """デフォルトバージョンを作成"""
        default_params = self.get_default_parameters()

        version = ParameterVersion(
            version="1.0.0",
            parameters=default_params,
            description="Initial default parameters",
            is_active=True,
            created_by="system",
        )

        db.add(version)
        db.commit()
        return "1.0.0"

    def get_default_parameters(self) -> Dict[str, Any]:
        """デフォルトパラメータ"""
        return {
            "batting": {
                "power_base": 75,
                "contact_base": 70,
                "speed_base": 65,
                "power_variance": 15,
                "contact_variance": 12,
                "speed_variance": 10,
            },
            "pitching": {
                "velocity_base": 80,
                "control_base": 75,
                "stamina_base": 70,
                "velocity_variance": 12,
                "control_variance": 15,
                "stamina_variance": 18,
            },
            "game_mechanics": {
                "hit_probability_base": 0.25,
                "homerun_probability_base": 0.03,
                "strikeout_probability_base": 0.22,
                "walk_probability_base": 0.08,
            },
        }

    def create_new_version(
        self,
        db: Session,
        new_version: str,
        base_version: str,
        parameter_changes: Dict[str, Any],
        description: str = "",
        created_by: str = "system",
    ) -> ParameterVersion:
        """新しいパラメータバージョンを作成"""

        # ベースとなるパラメータを取得
        base_params = self.get_parameters(db, base_version)

        # パラメータをアップデート
        new_params = self._apply_parameter_changes(base_params, parameter_changes)

        # 新バージョンを作成
        new_param_version = ParameterVersion(
            version=new_version,
            parameters=new_params,
            description=description,
            is_active=False,  # 手動でアクティブ化
            created_by=created_by,
        )

        db.add(new_param_version)

        # 調整履歴を記録
        adjustment = ParameterAdjustment(
            base_version=base_version,
            new_version=new_version,
            adjustment_type=AdjustmentTypeEnum.manual,
            parameter_changes=parameter_changes,
            reason=description,
            created_by=created_by,
        )

        db.add(adjustment)
        db.commit()

        return new_param_version

    def _apply_parameter_changes(
        self, base_params: Dict[str, Any], changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """パラメータ変更を適用"""
        new_params = base_params.copy()

        for key, value in changes.items():
            # ネストしたキーをサポート（例: "batting.power_base"）
            keys = key.split(".")
            current = new_params

            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]

            current[keys[-1]] = value

        return new_params


class GameLogger:
    """ゲーム結果のログ記録"""

    def __init__(self, parameter_manager: ParameterManager):
        self.param_manager = parameter_manager

    def log_game_completion(
        self,
        db: Session,
        game: Game,
        game_type: GameTypeEnum = GameTypeEnum.player_vs_cpu,
        simulation_run_id: Optional[int] = None,
        game_duration_seconds: Optional[int] = None,
    ) -> GameDetail:
        """ゲーム完了時のログ記録"""

        # 現在のバージョンを取得
        current_version = self.param_manager.get_current_version(db)

        # 勝者判定
        winner = self._determine_winner(game.player_score, game.cpu_score)

        # 投球数とヒット数を集計
        pitches = db.query(Pitch).filter(Pitch.game_id == game.id).all()
        total_pitches = len(pitches)

        hits_player = len(
            [p for p in pitches if not p.is_pitcher_player and p.result_type == "hit"]
        )
        hits_cpu = len(
            [p for p in pitches if p.is_pitcher_player and p.result_type == "hit"]
        )

        # ゲーム詳細ログを作成
        game_detail = GameDetail(
            game_id=game.id,
            version=current_version,
            game_type=game_type,
            final_player_score=game.player_score,
            final_cpu_score=game.cpu_score,
            total_innings=game.inning,
            winner=winner,
            total_pitches=total_pitches,
            hits_player=hits_player,
            hits_cpu=hits_cpu,
            errors_player=0,  # 今後実装
            errors_cpu=0,  # 今後実装
            game_duration_seconds=game_duration_seconds,
            simulation_run_id=simulation_run_id,
        )

        db.add(game_detail)
        db.commit()

        # 統計を更新
        self._update_player_statistics(db, current_version, game_detail, pitches)

        return game_detail

    def _determine_winner(self, player_score: int, cpu_score: int) -> WinnerEnum:
        """勝者判定"""
        if player_score > cpu_score:
            return WinnerEnum.player
        elif cpu_score > player_score:
            return WinnerEnum.cpu
        else:
            return WinnerEnum.tie

    def _update_player_statistics(
        self, db: Session, version: str, game_detail: GameDetail, pitches: list
    ):
        """プレイヤー統計を更新"""
        today = date.today()

        # プレイヤーとCPU両方の統計を更新
        for player_type in [PlayerTypeEnum.human, PlayerTypeEnum.cpu]:
            stats = (
                db.query(PlayerStatistics)
                .filter(
                    PlayerStatistics.version == version,
                    PlayerStatistics.player_type == player_type,
                    PlayerStatistics.date_from <= today,
                    PlayerStatistics.date_to >= today,
                )
                .first()
            )

            if not stats:
                # 新規作成
                stats = PlayerStatistics(
                    version=version,
                    player_type=player_type,
                    date_from=today,
                    date_to=today,
                )
                db.add(stats)

            # 統計を更新
            stats.games_played += 1

            if player_type == PlayerTypeEnum.human:
                # プレイヤーの統計
                player_pitches = [p for p in pitches if not p.is_pitcher_player]
                player_hits = len([p for p in player_pitches if p.result_type == "hit"])

                stats.at_bats += len(player_pitches)
                stats.hits += player_hits
                stats.batting_avg = (
                    stats.hits / stats.at_bats if stats.at_bats > 0 else 0.000
                )

                if game_detail.winner == WinnerEnum.player:
                    stats.wins += 1
                elif game_detail.winner == WinnerEnum.cpu:
                    stats.losses += 1
            else:
                # CPUの統計
                cpu_pitches = [p for p in pitches if p.is_pitcher_player]
                cpu_hits = len([p for p in cpu_pitches if p.result_type == "hit"])

                stats.at_bats += len(cpu_pitches)
                stats.hits += cpu_hits
                stats.batting_avg = (
                    stats.hits / stats.at_bats if stats.at_bats > 0 else 0.000
                )

                if game_detail.winner == WinnerEnum.cpu:
                    stats.wins += 1
                elif game_detail.winner == WinnerEnum.player:
                    stats.losses += 1

            # 勝率計算
            total_games = stats.wins + stats.losses
            stats.win_rate = stats.wins / total_games if total_games > 0 else 0.000

            # 日付範囲を更新
            if today > stats.date_to:
                stats.date_to = today

        db.commit()


class StatisticsService:
    """統計分析サービス"""

    def __init__(self, parameter_manager: ParameterManager):
        self.param_manager = parameter_manager

    def get_version_comparison(self, db: Session, versions: list) -> Dict[str, Any]:
        """バージョン間の比較統計"""
        comparison = {}

        for version in versions:
            stats = (
                db.query(PlayerStatistics)
                .filter(PlayerStatistics.version == version)
                .all()
            )

            version_stats = {
                "games_played": sum(s.games_played for s in stats),
                "avg_batting_avg": sum(s.batting_avg for s in stats) / len(stats)
                if stats
                else 0,
                "avg_win_rate": sum(s.win_rate for s in stats) / len(stats)
                if stats
                else 0,
            }

            comparison[version] = version_stats

        return comparison

    def get_recent_games(
        self, db: Session, version: str = None, limit: int = 50
    ) -> list:
        """最近のゲーム結果を取得"""
        if not version:
            version = self.param_manager.get_current_version(db)

        games = (
            db.query(GameDetail)
            .filter(GameDetail.version == version)
            .order_by(GameDetail.completed_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "game_id": g.game_id,
                "final_score": {
                    "player": g.final_player_score,
                    "cpu": g.final_cpu_score,
                },
                "winner": g.winner.value,
                "total_pitches": g.total_pitches,
                "completed_at": g.completed_at.isoformat(),
                "game_type": g.game_type.value,
            }
            for g in games
        ]

    def get_pitch_analysis(self, db: Session, version: str = None) -> Dict[str, Any]:
        """投球分析（バージョン別）"""
        if not version:
            version = self.param_manager.get_current_version(db)

        # バージョン関連のゲームIDを取得
        game_ids = (
            db.query(GameDetail.game_id)
            .filter(GameDetail.version == version)
            .subquery()
        )

        # 投球データを分析
        pitches = db.query(Pitch).filter(Pitch.game_id.in_(game_ids)).all()

        analysis = {}

        for pitch_type in ["fastball", "changeup", "slider", "forkball"]:
            type_pitches = [p for p in pitches if p.pitch_type.value == pitch_type]

            if type_pitches:
                total = len(type_pitches)
                strikes = len([p for p in type_pitches if not p.is_ball])
                hits = len([p for p in type_pitches if p.result_type.value == "hit"])

                analysis[pitch_type] = {
                    "usage_count": total,
                    "usage_rate": total / len(pitches) if pitches else 0,
                    "strike_rate": strikes / total,
                    "hit_rate": hits / strikes if strikes > 0 else 0,
                    "effectiveness": (strikes - hits) / strikes if strikes > 0 else 0,
                }

        return analysis
