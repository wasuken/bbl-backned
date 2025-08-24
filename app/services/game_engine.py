import random
from typing import Dict, Any, Tuple, List
from ..schemas.game import Pitch, Guess, GameResult, PitchType, GuessType


class GameEngine:
    """野球ゲームのメインロジック（フロントエンドから移行）"""

    def __init__(self):
        # 球種特性（将来の拡張用）
        self.PITCH_CONTROL = {
            "fastball": 0.9,
            "changeup": 0.8,
            "slider": 0.6,
            "forkball": 0.4,
        }

        # 結果表示マッピング
        self.RESULT_DISPLAYS = {
            "hit": {
                "icon": "⚾",
                "color": "text-blue-600",
                "type": "ヒット！",
                "description": "バッターの勝利！",
            },
            "strike": {
                "icon": "👊",
                "color": "text-red-600",
                "type": "ストライク！",
                "description": "ピッチャーの勝利！",
            },
            "swing_miss": {
                "icon": "💨",
                "color": "text-red-600",
                "type": "空振り！",
                "description": "ボール球を振ってしまった！",
            },
            "foul": {
                "icon": "⚽",
                "color": "text-yellow-600",
                "type": "ファウル",
                "description": "惜しい！",
            },
            "ball": {
                "icon": "🟢",
                "color": "text-green-600",
                "type": "ボール",
                "description": "よく見送った！",
            },
        }

    def generate_cpu_pitch(self, context: Dict[str, Any]) -> Pitch:
        """CPUの投球生成（既存ロジックを移行）"""
        balls = context.get("balls", 0)
        strikes = context.get("strikes", 0)

        # カウント別戦略調整
        if balls >= 2:  # 追い込まれ状況
            should_throw_ball = 0.1  # 慎重にストライク狙い
        elif strikes >= 2:  # 追い込み状況
            should_throw_ball = 0.4  # ボール球で釣る
        else:
            should_throw_ball = 0.3  # 通常

        # 球種選択（現在は2球種、将来4球種に拡張）
        pitch_type = PitchType.changeup if random.random() > 0.6 else PitchType.fastball

        # ゾーン選択
        if random.random() < should_throw_ball:
            zone = random.randint(10, 17)  # ボールゾーン
        else:
            zone = random.randint(1, 9)  # ストライクゾーン

        return Pitch(type=pitch_type, zone=zone)

    def generate_cpu_guess(self, context: Dict[str, Any]) -> Guess:
        """CPUバッターの予想生成"""
        balls = context.get("balls", 0)
        strikes = context.get("strikes", 0)

        # カウント別戦略
        if strikes >= 2:  # 追い込まれ
            # 慎重に、任意球種で対応
            guess_type = GuessType.any if random.random() > 0.8 else GuessType.fastball
        elif balls >= 3:  # フルカウント
            # ストライク確実性重視
            guess_type = (
                GuessType.fastball if random.random() > 0.3 else GuessType.changeup
            )
        else:
            # 通常時ランダム
            types = [GuessType.fastball, GuessType.changeup, GuessType.any]
            guess_type = random.choice(types)

        zone = random.randint(1, 9)  # ストライクゾーンのみ予想
        return Guess(type=guess_type, zone=zone)

    def calculate_result(
        self, actual_pitch: Pitch, batter_guess: Guess
    ) -> Tuple[str, bool]:
        """結果判定（既存ロジックを忠実に移行）"""
        is_strike = actual_pitch.zone <= 9

        if not is_strike:
            # ボール球の場合
            swing_chance = self._get_ball_swing_chance(actual_pitch, batter_guess)
            if random.random() < swing_chance:
                return "swing_miss", False  # ボール球を振って空振り
            else:
                return "ball", True

        # ストライク球の場合
        zone_match = actual_pitch.zone == batter_guess.zone
        type_match = (
            batter_guess.type == GuessType.any
            or actual_pitch.type.value == batter_guess.type.value
        )

        hit_chance = self._calculate_hit_chance(
            zone_match, type_match, actual_pitch, batter_guess
        )
        random_val = random.random()

        if random_val < hit_chance:
            return "hit", False
        elif random_val < hit_chance + 0.2:
            return "foul", False
        else:
            return "strike", False

    def _get_ball_swing_chance(self, pitch: Pitch, guess: Guess) -> float:
        """ボール球スイング確率（拡張可能）"""
        base_chance = 0.2

        # ゾーン近接度による調整
        if pitch.zone in [10, 11]:  # 左右際どいボール
            base_chance *= 1.3
        elif pitch.zone in [12, 13]:  # 高低際どいボール
            base_chance *= 1.1
        elif pitch.zone >= 14:  # 明らかなボール球
            base_chance *= 0.5

        return min(base_chance, 0.6)

    def _calculate_hit_chance(
        self, zone_match: bool, type_match: bool, pitch: Pitch, guess: Guess
    ) -> float:
        """ヒット確率計算（球種特性考慮可能）"""
        base_chance = 0.1

        if zone_match:
            base_chance += 0.4
        if type_match:
            base_chance += 0.3
        if zone_match and type_match:
            base_chance += 0.2  # 完全的中ボーナス

        # 球種特性による調整（将来拡張）
        if pitch.type == PitchType.changeup and type_match:
            base_chance += 0.1  # チェンジアップ的中はさらに有利

        return min(base_chance, 0.9)

    def update_game_state(
        self, current_state: Any, result_type: str, is_ball: bool
    ) -> Dict[str, Any]:
        """ゲーム状態更新ロジック"""
        new_balls = current_state.balls
        new_strikes = current_state.strikes
        new_outs = current_state.outs
        new_score = {
            "player": current_state.player_score,
            "cpu": current_state.cpu_score,
        }

        if is_ball:
            new_balls += 1
            if new_balls >= 4:  # 四球
                if current_state.is_player_pitching:
                    new_score["cpu"] += 1
                else:
                    new_score["player"] += 1
                new_balls = 0
                new_strikes = 0
        else:
            if result_type == "hit":
                if current_state.is_player_pitching:
                    new_score["cpu"] += 1
                else:
                    new_score["player"] += 1
                new_balls = 0
                new_strikes = 0
            elif result_type == "foul":
                if new_strikes < 2:
                    new_strikes += 1
            elif result_type in ["strike", "swing_miss"]:
                new_strikes += 1
                if new_strikes >= 3:  # 三振
                    new_outs += 1
                    new_balls = 0
                    new_strikes = 0

        return {
            "balls": new_balls,
            "strikes": new_strikes,
            "outs": new_outs,
            "inning": current_state.inning,
            "score": new_score,
        }

    def get_result_display(self, result_type: str, is_ball: bool) -> GameResult:
        """結果表示情報生成"""
        display = self.RESULT_DISPLAYS.get(
            result_type,
            {"icon": "❓", "color": "text-gray-600", "type": "結果", "description": ""},
        )

        return GameResult(
            type=display["type"],
            description=display["description"],
            icon=display["icon"],
            color=display["color"],
        )

    def analyze_pitch_effectiveness(self, pitch_data: List[Any]) -> Dict[str, Any]:
        """球種別効果分析（統計API用）"""
        stats = {}

        for pitch_type in PitchType:
            type_pitches = [p for p in pitch_data if p.pitch_type == pitch_type.value]

            if type_pitches:
                total = len(type_pitches)
                strikes = len([p for p in type_pitches if not p.is_ball])
                hits = len([p for p in type_pitches if p.result_type == "hit"])

                stats[pitch_type.value] = {
                    "usage_rate": total / len(pitch_data) if pitch_data else 0,
                    "strike_rate": strikes / total if total > 0 else 0,
                    "hit_rate": hits / strikes if strikes > 0 else 0,
                    "total_pitches": total,
                }

        return stats


# 戦略パターン（将来の拡張用）
class StrategyEngine:
    """AI戦略管理（シミュレーター用）"""

    STRATEGIES = {
        "aggressive": {
            "strike_preference": 0.8,
            "fastball_rate": 0.7,
            "swing_rate": 0.8,
        },
        "patient": {"strike_preference": 0.6, "fastball_rate": 0.5, "swing_rate": 0.4},
        "balanced": {"strike_preference": 0.7, "fastball_rate": 0.6, "swing_rate": 0.6},
    }

    def get_strategy_pitch(self, strategy_name: str, context: Dict[str, Any]) -> Pitch:
        """戦略に基づく投球生成"""
        strategy = self.STRATEGIES.get(strategy_name, self.STRATEGIES["balanced"])

        # 戦略的ゾーン選択
        if random.random() < strategy["strike_preference"]:
            zone = random.randint(1, 9)
        else:
            zone = random.randint(10, 17)

        # 戦略的球種選択
        pitch_type = (
            PitchType.fastball
            if random.random() < strategy["fastball_rate"]
            else PitchType.changeup
        )

        return Pitch(type=pitch_type, zone=zone)

    def get_strategy_guess(self, strategy_name: str, context: Dict[str, Any]) -> Guess:
        """戦略に基づくバッティング"""
        strategy = self.STRATEGIES.get(strategy_name, self.STRATEGIES["balanced"])

        # 積極性に基づく球種予想
        if random.random() < 0.3:
            guess_type = GuessType.any
        elif random.random() < strategy["fastball_rate"]:
            guess_type = GuessType.fastball
        else:
            guess_type = GuessType.changeup

        zone = random.randint(1, 9)
        return Guess(type=guess_type, zone=zone)
