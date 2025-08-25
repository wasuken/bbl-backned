import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestLoggingAPI:
    """ログAPI E2Eテスト"""

    def test_parameter_management_lifecycle(self, client: TestClient):
        """パラメータ管理ライフサイクルテスト"""

        # 1. 全バージョン取得
        response = client.get("/api/logging/parameters/versions")
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) >= 1  # デフォルトバージョンが存在

        default_version = versions[0]
        assert default_version["version"] == "1.0.0"
        assert default_version["is_active"] is True

        # 2. 現在のパラメータ取得
        response = client.get("/api/logging/parameters/current")
        assert response.status_code == 200
        current = response.json()
        assert current["version"] == "1.0.0"
        assert "parameters" in current
        assert "batting" in current["parameters"]
        assert "pitching" in current["parameters"]

        # 3. 新バージョン作成
        new_version_request = {
            "new_version": "1.1.0",
            "base_version": "1.0.0",
            "parameter_changes": {
                "batting.power_base": 80,
                "pitching.velocity_base": 85,
            },
            "description": "Test parameter adjustment",
            "created_by": "test_user",
        }

        response = client.post(
            "/api/logging/parameters/versions", json=new_version_request
        )
        assert response.status_code == 200
        new_version = response.json()
        assert new_version["version"] == "1.1.0"
        assert new_version["is_active"] is False
        assert new_version["parameters"]["batting"]["power_base"] == 80

        # 4. 特定バージョンのパラメータ取得
        response = client.get("/api/logging/parameters/1.1.0")
        assert response.status_code == 200
        version_params = response.json()
        assert version_params["version"] == "1.1.0"
        assert version_params["parameters"]["batting"]["power_base"] == 80

        # 5. バージョンアクティブ化
        response = client.put("/api/logging/parameters/1.1.0/activate")
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "activated"
        assert result["version"] == "1.1.0"

        # 6. アクティブ化後の確認
        response = client.get("/api/logging/parameters/current")
        assert response.status_code == 200
        current = response.json()
        assert current["version"] == "1.1.0"

    def test_game_logging_integration(self, client: TestClient):
        """ゲームログ統合テスト"""

        # ゲーム作成・実行
        response = client.post("/api/game/start", json={"player_pitching": True})
        game_data = response.json()
        game_id = game_data["game_id"]

        # 数回投球してゲーム進行
        for i in range(5):
            client.post(
                f"/api/game/{game_id}/pitch",
                json={"player_pitch": {"type": "fastball", "zone": i + 1}},
            )
            client.post(f"/api/game/{game_id}/next-pitch")

        # ゲーム終了をログに記録
        response = client.post(
            f"/api/logging/games/{game_id}/complete",
            params={"game_type": "player_vs_cpu"},
        )
        assert response.status_code == 200

        completion_result = response.json()
        assert completion_result["status"] == "logged"
        assert "game_detail_id" in completion_result
        assert "winner" in completion_result
        assert completion_result["version"] == "1.0.0"

        # ゲーム詳細取得
        response = client.get(f"/api/logging/games/details/{game_id}")
        assert response.status_code == 200

        detail = response.json()
        assert detail["game_id"] == game_id
        assert detail["version"] == "1.0.0"
        assert detail["total_pitches"] == 5

        # 最近のゲーム一覧取得
        response = client.get("/api/logging/games/recent")
        assert response.status_code == 200

        recent_games = response.json()
        assert len(recent_games) >= 1
        assert recent_games[0]["game_id"] == game_id

    def test_statistics_api(self, client: TestClient):
        """統計API テスト"""

        # テスト用ゲームを複数実行
        game_ids = []

        for i in range(3):
            # ゲーム作成
            response = client.post("/api/game/start", json={"player_pitching": True})
            game_id = response.json()["game_id"]
            game_ids.append(game_id)

            # 投球実行
            for j in range(3):
                client.post(
                    f"/api/game/{game_id}/pitch",
                    json={
                        "player_pitch": {
                            "type": "fastball" if j % 2 == 0 else "changeup",
                            "zone": j + 1,
                        }
                    },
                )
                client.post(f"/api/game/{game_id}/next-pitch")

            # ゲーム完了
            client.post(f"/api/logging/games/{game_id}/complete")

        # プレイヤー統計取得
        response = client.get("/api/logging/statistics/1.0.0/players")
        assert response.status_code == 200

        player_stats = response.json()
        assert len(player_stats) >= 1

        for stat in player_stats:
            assert "version" in stat
            assert "player_type" in stat
            assert "games_played" in stat

        # 投球分析取得
        response = client.get("/api/logging/statistics/1.0.0/pitches")
        assert response.status_code == 200

        pitch_analysis = response.json()
        assert isinstance(pitch_analysis, dict)
        # fastballとchangeupの統計が含まれるはず
        if "fastball" in pitch_analysis:
            assert "usage_count" in pitch_analysis["fastball"]
            assert "strike_rate" in pitch_analysis["fastball"]

        # ダッシュボードデータ取得
        response = client.get("/api/logging/statistics/dashboard")
        assert response.status_code == 200

        dashboard = response.json()
        assert "current_version" in dashboard
        assert "total_games" in dashboard
        assert "recent_activity" in dashboard
        assert dashboard["current_version"] == "1.0.0"
        assert dashboard["total_games"] >= 3

    def test_version_comparison(self, client: TestClient):
        """バージョン比較統計テスト"""

        # v1.0.0でゲーム実行
        response = client.post("/api/game/start", json={"player_pitching": True})
        game_id_v1 = response.json()["game_id"]

        client.post(
            f"/api/game/{game_id_v1}/pitch",
            json={"player_pitch": {"type": "fastball", "zone": 5}},
        )
        client.post(f"/api/logging/games/{game_id_v1}/complete")

        # 新バージョン作成・アクティブ化
        client.post(
            "/api/logging/parameters/versions",
            json={
                "new_version": "1.2.0",
                "base_version": "1.0.0",
                "parameter_changes": {"batting.power_base": 90},
                "description": "Power increase test",
            },
        )
        client.put("/api/logging/parameters/1.2.0/activate")

        # v1.2.0でゲーム実行
        response = client.post("/api/game/start", json={"player_pitching": True})
        game_id_v2 = response.json()["game_id"]

        client.post(
            f"/api/game/{game_id_v2}/pitch",
            json={"player_pitch": {"type": "changeup", "zone": 3}},
        )
        client.post(f"/api/logging/games/{game_id_v2}/complete")

        # バージョン比較統計
        response = client.get(
            "/api/logging/statistics/versions/comparison",
            params={"versions": ["1.0.0", "1.2.0"]},
        )
        assert response.status_code == 200

        comparison = response.json()
        assert "1.0.0" in comparison
        assert "1.2.0" in comparison
        assert comparison["1.0.0"]["games_played"] >= 1
        assert comparison["1.2.0"]["games_played"] >= 1

    def test_error_cases(self, client: TestClient):
        """エラーケーステスト"""

        # 存在しないバージョンの取得
        response = client.get("/api/logging/parameters/nonexistent")
        assert response.status_code == 404

        # 存在しないゲームの完了
        response = client.post("/api/logging/games/fake-game-id/complete")
        assert response.status_code == 404

        # 存在しないゲームの詳細取得
        response = client.get("/api/logging/games/details/fake-game-id")
        assert response.status_code == 404

        # 存在しないバージョンのアクティブ化
        response = client.put("/api/logging/parameters/nonexistent/activate")
        assert response.status_code == 404

        # 無効なバージョン作成（ベースバージョン存在しない）
        response = client.post(
            "/api/logging/parameters/versions",
            json={
                "new_version": "2.0.0",
                "base_version": "nonexistent",
                "parameter_changes": {"batting.power_base": 100},
                "description": "Should fail",
            },
        )
        assert response.status_code == 400


class TestParameterVersioning:
    """パラメータバージョニング詳細テスト"""

    def test_parameter_inheritance(self, client: TestClient):
        """パラメータ継承テスト"""

        # ベースバージョンのパラメータ取得
        response = client.get("/api/logging/parameters/1.0.0")
        base_params = response.json()["parameters"]
        original_power = base_params["batting"]["power_base"]

        # 一部パラメータのみ変更した新バージョン作成
        response = client.post(
            "/api/logging/parameters/versions",
            json={
                "new_version": "1.0.1",
                "base_version": "1.0.0",
                "parameter_changes": {"batting.power_base": original_power + 5},
                "description": "Power boost test",
            },
        )
        assert response.status_code == 200

        # 新バージョンのパラメータ確認
        response = client.get("/api/logging/parameters/1.0.1")
        new_params = response.json()["parameters"]

        # 変更されたパラメータ
        assert new_params["batting"]["power_base"] == original_power + 5

        # 変更されていないパラメータは継承されている
        assert (
            new_params["batting"]["contact_base"]
            == base_params["batting"]["contact_base"]
        )
        assert (
            new_params["pitching"]["velocity_base"]
            == base_params["pitching"]["velocity_base"]
        )
        assert new_params["game_mechanics"] == base_params["game_mechanics"]

    def test_nested_parameter_changes(self, client: TestClient):
        """ネストしたパラメータ変更テスト"""

        response = client.post(
            "/api/logging/parameters/versions",
            json={
                "new_version": "1.0.2",
                "base_version": "1.0.0",
                "parameter_changes": {
                    "batting.power_base": 85,
                    "batting.contact_base": 75,
                    "pitching.velocity_base": 90,
                    "game_mechanics.hit_probability_base": 0.30,
                },
                "description": "Multiple nested changes",
            },
        )
        assert response.status_code == 200

        response = client.get("/api/logging/parameters/1.0.2")
        params = response.json()["parameters"]

        assert params["batting"]["power_base"] == 85
        assert params["batting"]["contact_base"] == 75
        assert params["pitching"]["velocity_base"] == 90
        assert params["game_mechanics"]["hit_probability_base"] == 0.30

    def test_version_activation_history(self, client: TestClient):
        """バージョンアクティブ化履歴テスト"""

        # 複数バージョン作成
        for i in range(3):
            version = f"1.{i + 1}.0"
            client.post(
                "/api/logging/parameters/versions",
                json={
                    "new_version": version,
                    "base_version": "1.0.0",
                    "parameter_changes": {"batting.power_base": 75 + i * 5},
                    "description": f"Version {version} test",
                },
            )

        # バージョン切り替え
        for version in ["1.1.0", "1.2.0", "1.3.0", "1.1.0"]:
            response = client.put(f"/api/logging/parameters/{version}/activate")
            assert response.status_code == 200

            # アクティブバージョン確認
            current = client.get("/api/logging/parameters/current").json()
            assert current["version"] == version

        # 全バージョン取得してアクティブ状態確認
        versions = client.get("/api/logging/parameters/versions").json()
        active_versions = [v for v in versions if v["is_active"]]
        assert len(active_versions) == 1  # アクティブは1つだけ
        assert active_versions[0]["version"] == "1.1.0"


class TestGameDataIntegrity:
    """ゲームデータ整合性テスト"""

    def test_pitch_data_consistency(self, client: TestClient):
        """投球データ整合性テスト"""

        # ゲーム作成
        response = client.post("/api/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]

        pitch_data = []

        # 複数回投球
        for i in range(5):
            pitch_request = {
                "player_pitch": {
                    "type": "fastball" if i % 2 == 0 else "changeup",
                    "zone": (i % 9) + 1,
                }
            }

            response = client.post(f"/api/game/{game_id}/pitch", json=pitch_request)
            result = response.json()

            pitch_data.append(
                {"request": pitch_request, "result": result, "pitch_number": i + 1}
            )

            client.post(f"/api/game/{game_id}/next-pitch")

        # ゲーム完了
        client.post(f"/api/logging/games/{game_id}/complete")

        # 投球履歴取得
        response = client.get(f"/api/stats/game/{game_id}/history")
        history = response.json()

        # データ整合性確認
        assert len(history) == 5

        for i, (pitch, history_entry) in enumerate(zip(pitch_data, history)):
            assert history_entry["pitch_number"] == i + 1
            assert (
                history_entry["pitch"]["type"]
                == pitch["request"]["player_pitch"]["type"]
            )
            assert (
                history_entry["pitch"]["zone"]
                == pitch["request"]["player_pitch"]["zone"]
            )
            assert "guess" in history_entry
            assert "result" in history_entry
            assert "context" in history_entry

    def test_score_tracking_accuracy(self, client: TestClient):
        """スコア追跡精度テスト"""

        # ゲーム作成
        response = client.post("/api/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]

        initial_state = client.get(f"/api/game/{game_id}/state").json()
        assert initial_state["score"]["player"] == 0
        assert initial_state["score"]["cpu"] == 0

        scores_history = []

        # 投球とスコア変化を追跡
        for i in range(10):
            # 現在の状態を記録
            current_state = client.get(f"/api/game/{game_id}/state").json()
            scores_history.append(
                {"before": current_state["score"].copy(), "pitch_number": i + 1}
            )

            # 投球実行
            response = client.post(
                f"/api/game/{game_id}/pitch",
                json={"player_pitch": {"type": "fastball", "zone": 5}},
            )

            pitch_result = response.json()
            scores_history[-1]["after"] = pitch_result["updated_state"]["score"].copy()
            scores_history[-1]["result_type"] = pitch_result["result"]["type"]

            client.post(f"/api/game/{game_id}/next-pitch")

        # ゲーム完了
        client.post(f"/api/logging/games/{game_id}/complete")

        # 最終スコアの整合性確認
        final_state = client.get(f"/api/game/{game_id}/state").json()
        game_detail = client.get(f"/api/logging/games/details/{game_id}").json()

        assert final_state["score"]["player"] == game_detail["final_player_score"]
        assert final_state["score"]["cpu"] == game_detail["final_cpu_score"]

        # スコア変化の論理性確認
        for score_entry in scores_history:
            player_before = score_entry["before"]["player"]
            cpu_before = score_entry["before"]["cpu"]
            player_after = score_entry["after"]["player"]
            cpu_after = score_entry["after"]["cpu"]

            # スコアは単調増加のみ
            assert player_after >= player_before
            assert cpu_after >= cpu_before

            # 1投球で両チームのスコアが同時に上がることはない
            player_increased = player_after > player_before
            cpu_increased = cpu_after > cpu_before
            assert not (player_increased and cpu_increased)

    def test_concurrent_games_isolation(self, client: TestClient):
        """並行ゲーム分離テスト"""

        # 複数ゲーム同時開始
        games = []
        for i in range(3):
            response = client.post("/api/game/start", json={"player_pitching": True})
            games.append({"id": response.json()["game_id"], "expected_pitches": []})

        # 各ゲームで異なるパターンの投球
        for round_num in range(5):
            for game_idx, game in enumerate(games):
                pitch_type = ["fastball", "changeup", "slider"][game_idx % 3]
                zone = (round_num * 3 + game_idx) % 9 + 1

                pitch_request = {"player_pitch": {"type": pitch_type, "zone": zone}}

                response = client.post(
                    f"/api/game/{game['id']}/pitch", json=pitch_request
                )
                assert response.status_code == 200

                game["expected_pitches"].append(pitch_request["player_pitch"])
                client.post(f"/api/game/{game['id']}/next-pitch")

        # 各ゲームの履歴を検証
        for game in games:
            response = client.get(f"/api/stats/game/{game['id']}/history")
            history = response.json()

            assert len(history) == 5

            for i, (expected, actual) in enumerate(
                zip(game["expected_pitches"], history)
            ):
                assert actual["pitch"]["type"] == expected["type"]
                assert actual["pitch"]["zone"] == expected["zone"]
                assert actual["pitch_number"] == i + 1
