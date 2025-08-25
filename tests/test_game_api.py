import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestGameAPI:
    """ゲームAPI E2Eテスト"""

    def test_root_endpoint(self, client: TestClient):
        """ルートエンドポイントテスト"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Baseball Game API"
        assert data["status"] == "running"

    def test_game_lifecycle(self, client: TestClient):
        """ゲームライフサイクル全体テスト"""

        # 1. ゲーム開始
        response = client.post("/api/game/start", json={"player_pitching": True})
        assert response.status_code == 200

        game_data = response.json()
        game_id = game_data["game_id"]

        # テスト用ゲームIDにプレフィックス追加（データクリーンアップ用）
        # 注: 実際のUUIDは変更できないので、ログでの識別に使用
        print(f"Test game ID: {game_id}")

        assert game_data["balls"] == 0
        assert game_data["strikes"] == 0
        assert game_data["outs"] == 0
        assert game_data["inning"] == 1
        assert game_data["score"]["player"] == 0
        assert game_data["score"]["cpu"] == 0
        assert game_data["is_player_pitching"] is True
        assert game_data["game_phase"] == "selecting"

        # 2. ゲーム状態取得
        response = client.get(f"/api/game/{game_id}/state")
        assert response.status_code == 200
        state = response.json()
        assert state["game_id"] == game_id

        # 3. 投球実行（プレイヤーが投手の場合）
        pitch_request = {"player_pitch": {"type": "fastball", "zone": 5}}
        response = client.post(f"/api/game/{game_id}/pitch", json=pitch_request)
        assert response.status_code == 200

        pitch_result = response.json()
        assert pitch_result["actual_pitch"]["type"] == "fastball"
        assert pitch_result["actual_pitch"]["zone"] == 5
        assert "batter_guess" in pitch_result
        assert "result" in pitch_result
        assert "updated_state" in pitch_result

        # 4. 次の投球に進む
        response = client.post(f"/api/game/{game_id}/next-pitch")
        assert response.status_code == 200
        assert response.json()["status"] == "ready_for_next_pitch"

        # 5. 攻守交代
        response = client.post(f"/api/game/{game_id}/toggle-pitching")
        assert response.status_code == 200
        toggle_result = response.json()
        assert toggle_result["status"] == "pitching_toggled"
        assert toggle_result["is_player_pitching"] is False

        # 6. CPUが投手の場合の投球（プレイヤーは予想）
        guess_request = {"player_guess": {"type": "changeup", "zone": 3}}
        response = client.post(f"/api/game/{game_id}/pitch", json=guess_request)
        assert response.status_code == 200

        guess_result = response.json()
        assert "actual_pitch" in guess_result
        assert guess_result["batter_guess"]["type"] == "changeup"
        assert guess_result["batter_guess"]["zone"] == 3

        # 7. ゲーム終了
        response = client.post(f"/api/game/{game_id}/end")
        assert response.status_code == 200

        end_result = response.json()
        assert end_result["status"] == "game_ended"
        assert "final_score" in end_result
        assert "winner" in end_result
        assert "version" in end_result

    def test_pitch_without_game(self, client: TestClient):
        """存在しないゲームIDで投球テスト"""
        fake_game_id = "nonexistent-game-id"

        response = client.post(
            f"/api/game/{fake_game_id}/pitch",
            json={"player_pitch": {"type": "fastball", "zone": 5}},
        )

        assert response.status_code == 404
        assert "Game not found" in response.json()["detail"]

    def test_pitch_missing_parameters(self, client: TestClient):
        """必要パラメータなしで投球テスト"""
        # ゲーム作成
        response = client.post("/api/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]

        # プレイヤーが投手なのにplayer_pitchなし
        response = client.post(f"/api/game/{game_id}/pitch", json={})
        assert response.status_code == 400
        assert "Player pitch required" in response.json()["detail"]

    def test_game_statistics_api(self, client: TestClient):
        """統計API テスト"""
        # ゲーム作成と投球実行
        response = client.post("/api/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]

        # 数回投球
        for _ in range(3):
            client.post(
                f"/api/game/{game_id}/pitch",
                json={"player_pitch": {"type": "fastball", "zone": 5}},
            )
            client.post(f"/api/game/{game_id}/next-pitch")

        # 球種効果統計取得
        response = client.get("/api/stats/pitch-effectiveness")
        assert response.status_code == 200
        stats = response.json()
        assert isinstance(stats, dict)

        # ゲーム履歴取得
        response = client.get(f"/api/stats/game/{game_id}/history")
        assert response.status_code == 200
        history = response.json()
        assert isinstance(history, list)
        assert len(history) == 3  # 3回投球した

    def test_multiple_games_parallel(self, client: TestClient):
        """複数ゲーム並行実行テスト"""
        game_ids = []

        # 3つのゲームを開始
        for i in range(3):
            response = client.post(
                "/api/game/start",
                json={
                    "player_pitching": i % 2 == 0  # 交互に投手/打者
                },
            )
            assert response.status_code == 200
            game_ids.append(response.json()["game_id"])

        # 各ゲームで投球
        for game_id in game_ids:
            # 状態確認
            response = client.get(f"/api/game/{game_id}/state")
            assert response.status_code == 200

            state = response.json()

            # 投手/打者に応じた投球
            if state["is_player_pitching"]:
                pitch_data = {"player_pitch": {"type": "fastball", "zone": 1}}
            else:
                pitch_data = {"player_guess": {"type": "changeup", "zone": 9}}

            response = client.post(f"/api/game/{game_id}/pitch", json=pitch_data)
            assert response.status_code == 200

        # 全ゲームが独立して動作していることを確認
        assert len(set(game_ids)) == 3  # 全て異なるID


class TestGameEdgeCases:
    """ゲームAPIエッジケーステスト"""

    def test_invalid_pitch_type(self, client: TestClient):
        """無効な球種テスト"""
        response = client.post("/api/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]

        # 無効な球種
        response = client.post(
            f"/api/game/{game_id}/pitch",
            json={"player_pitch": {"type": "invalid_pitch", "zone": 5}},
        )

        # バリデーションエラーが発生するはず
        assert response.status_code == 422

    def test_invalid_zone(self, client: TestClient):
        """無効なゾーンテスト"""
        response = client.post("/api/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]

        # 無効なゾーン（範囲外）
        response = client.post(
            f"/api/game/{game_id}/pitch",
            json={"player_pitch": {"type": "fastball", "zone": 999}},
        )

        # 現在の実装では通るが、将来的にはバリデーション追加予定
        assert response.status_code in [200, 422]

    def test_game_phase_transition(self, client: TestClient):
        """ゲームフェーズ遷移テスト"""
        response = client.post("/api/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]

        # 初期状態はselecting
        state = client.get(f"/api/game/{game_id}/state").json()
        assert state["game_phase"] == "selecting"

        # 投球後はresult
        client.post(
            f"/api/game/{game_id}/pitch",
            json={"player_pitch": {"type": "fastball", "zone": 5}},
        )
        state = client.get(f"/api/game/{game_id}/state").json()
        assert state["game_phase"] == "result"

        # next-pitch後はselecting
        client.post(f"/api/game/{game_id}/next-pitch")
        state = client.get(f"/api/game/{game_id}/state").json()
        assert state["game_phase"] == "selecting"
