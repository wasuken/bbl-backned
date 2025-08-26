import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestLoggingAPI:
    """ログAPI E2Eテスト"""

    def test_get_current_parameters(self, client: TestClient):
        """現在のパラメータ取得テスト"""
        response = client.get("/logging/parameters/current")
        assert response.status_code == 200

        current = response.json()
        assert "version" in current
        assert "parameters" in current
        assert current["version"] == "1.0.0"

        # パラメータ構造確認
        params = current["parameters"]
        assert "batting" in params
        assert "pitching" in params
        assert "game_mechanics" in params

    def test_get_all_parameter_versions(self, client: TestClient):
        """全パラメータバージョン取得テスト"""
        response = client.get("/logging/parameters/versions")
        assert response.status_code == 200

        versions = response.json()
        assert len(versions) >= 1  # デフォルトバージョンが存在

        # デフォルトバージョン確認
        default_version = [v for v in versions if v["is_active"] is True][0]
        assert default_version["version"] == "1.0.0"
        assert default_version["is_active"] is True
        assert "parameters" in default_version
        assert "created_at" in default_version

    def test_get_specific_version_parameters(self, client: TestClient):
        """特定バージョンのパラメータ取得テスト"""
        response = client.get("/logging/parameters/1.0.0")
        assert response.status_code == 200

        version_data = response.json()
        assert version_data["version"] == "1.0.0"
        assert "parameters" in version_data

        # パラメータの基本構造確認
        params = version_data["parameters"]
        assert "batting" in params
        assert "power_base" in params["batting"]
        assert "contact_base" in params["batting"]

    def test_create_new_parameter_version(self, client: TestClient):
        """新パラメータバージョン作成テスト"""
        new_version_request = {
            "new_version": "1.1.0-test",
            "base_version": "1.0.0",
            "parameter_changes": {
                "batting.power_base": 80,
                "pitching.velocity_base": 85,
            },
            "description": "Test parameter adjustment",
            "created_by": "test_user",
        }

        response = client.post("/logging/parameters/versions", json=new_version_request)
        assert response.status_code == 200

        new_version = response.json()
        assert new_version["version"] == "1.1.0-test"
        assert new_version["is_active"] is False
        assert new_version["created_by"] == "test_user"

        # パラメータ変更が適用されているか確認
        assert new_version["parameters"]["batting"]["power_base"] == 80
        assert new_version["parameters"]["pitching"]["velocity_base"] == 85

    def test_activate_parameter_version(self, client: TestClient):
        """パラメータバージョンアクティブ化テスト"""
        # まず新バージョン作成
        client.post(
            "/logging/parameters/versions",
            json={
                "new_version": "1.2.1-test",
                "base_version": "1.0.0",
                "parameter_changes": {"batting.power_base": 90},
                "description": "Test activation",
            },
        )

        # アクティブ化
        response = client.put("/logging/parameters/1.2.1-test/activate")
        assert response.status_code == 200

        result = response.json()
        assert result["status"] == "activated"
        assert result["version"] == "1.2.1-test"

        # 現在のバージョンが変更されていることを確認
        current = client.get("/logging/parameters/current").json()
        assert current["version"] == "1.2.1-test"

    def test_game_completion_logging(self, client: TestClient):
        """ゲーム完了ログ記録テスト"""
        # ゲーム作成・実行
        response = client.post("/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]
        print(response.json())

        # 数回投球
        for i in range(3):
            client.post(
                f"/game/{game_id}/pitch",
                json={"player_pitch": {"type": "fastball", "zone": i + 1}},
            )
            client.post(f"/game/{game_id}/next-pitch")

        # ゲーム完了をログに記録
        response = client.post(
            f"/logging/games/{game_id}/complete",
            params={"game_type": "player_vs_cpu"},
        )
        assert response.status_code == 200

        completion_result = response.json()
        assert completion_result["status"] == "logged"
        assert "game_detail_id" in completion_result
        assert "winner" in completion_result
        assert "version" in completion_result

    def test_get_game_detail(self, client: TestClient):
        """ゲーム詳細取得テスト"""
        # ゲーム作成・完了
        response = client.post("/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]

        # 投球実行
        client.post(
            f"/game/{game_id}/pitch",
            json={"player_pitch": {"type": "fastball", "zone": 5}},
        )

        # ゲーム完了
        client.post(f"/logging/games/{game_id}/complete")

        # ゲーム詳細取得
        response = client.get(f"/logging/games/details/{game_id}")
        assert response.status_code == 200

        detail = response.json()
        assert detail["game_id"] == game_id
        assert "version" in detail
        assert detail["total_pitches"] >= 1
        assert "winner" in detail
        assert "final_player_score" in detail
        assert "final_cpu_score" in detail

    def test_get_recent_games(self, client: TestClient):
        """最近のゲーム取得テスト"""
        # テスト用ゲーム実行
        for i in range(2):
            response = client.post("/game/start", json={"player_pitching": True})
            game_id = response.json()["game_id"]

            # 投球実行
            client.post(
                f"/game/{game_id}/pitch",
                json={"player_pitch": {"type": "fastball", "zone": 1}},
            )

            # ゲーム完了
            client.post(f"/logging/games/{game_id}/complete")

        # 最近のゲーム取得
        response = client.get("/logging/games/recent")
        assert response.status_code == 200

        recent_games = response.json()
        assert len(recent_games) >= 2
        assert isinstance(recent_games, list)

        # 各ゲームデータの構造確認
        for game in recent_games[:2]:  # 最初の2件のみチェック
            assert "game_id" in game
            assert "final_score" in game
            assert "winner" in game
            assert "completed_at" in game

    def test_get_dashboard_data(self, client: TestClient):
        """ダッシュボードデータ取得テスト"""
        # テストデータ作成
        response = client.post("/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]

        client.post(
            f"/game/{game_id}/pitch",
            json={"player_pitch": {"type": "fastball", "zone": 5}},
        )
        client.post(f"/logging/games/{game_id}/complete")

        # ダッシュボードデータ取得
        response = client.get("/logging/statistics/dashboard")
        assert response.status_code == 200

        dashboard = response.json()
        assert "current_version" in dashboard
        assert "total_games" in dashboard
        assert "recent_activity" in dashboard
        assert "pitch_analysis" in dashboard
        assert dashboard["total_games"] >= 1

    def test_pitch_analysis_statistics(self, client: TestClient):
        """投球分析統計テスト"""
        # 複数の球種でテストデータ作成
        response = client.post("/game/start", json={"player_pitching": True})
        game_id = response.json()["game_id"]

        pitch_types = ["fastball", "changeup", "fastball"]
        for pitch_type in pitch_types:
            client.post(
                f"/game/{game_id}/pitch",
                json={"player_pitch": {"type": pitch_type, "zone": 5}},
            )
            client.post(f"/game/{game_id}/next-pitch")

        client.post(f"/logging/games/{game_id}/complete")

        # 投球分析取得
        response = client.get("/logging/statistics/1.0.0/pitches")
        assert response.status_code == 200

        pitch_analysis = response.json()
        assert isinstance(pitch_analysis, dict)

        # fastballの統計が存在すれば確認
        if "fastball" in pitch_analysis:
            fastball_stats = pitch_analysis["fastball"]
            assert "usage_count" in fastball_stats
            assert "strike_rate" in fastball_stats
            assert "usage_rate" in fastball_stats


class TestLoggingErrorCases:
    """ログAPIエラーケーステスト"""

    def test_nonexistent_version_parameters(self, client: TestClient):
        """存在しないバージョンのパラメータ取得"""
        response = client.get("/logging/parameters/nonexistent-version")
        print(response.json())
        assert response.status_code == 404

    def test_nonexistent_game_completion(self, client: TestClient):
        """存在しないゲームの完了"""
        response = client.post("/logging/games/fake-game-id/complete")
        assert response.status_code == 404

    def test_nonexistent_game_detail(self, client: TestClient):
        """存在しないゲームの詳細取得"""
        response = client.get("/logging/games/details/fake-game-id")
        assert response.status_code == 404

    def test_activate_nonexistent_version(self, client: TestClient):
        """存在しないバージョンのアクティブ化"""
        response = client.put("/logging/parameters/nonexistent/activate")
        assert response.status_code == 404

    def test_invalid_parameter_version_creation(self, client: TestClient):
        """無効なパラメータバージョン作成"""
        # 存在しないベースバージョンを指定
        response = client.post(
            "/logging/parameters/versions",
            json={
                "new_version": "2.0.0-invalid",
                "base_version": "nonexistent-base",
                "parameter_changes": {"batting.power_base": 100},
                "description": "Should fail",
            },
        )
        assert response.status_code == 400


class TestParameterInheritance:
    """パラメータ継承テスト"""

    def test_parameter_change_inheritance(self, client: TestClient):
        """パラメータ変更の継承テスト"""
        # ベースバージョンのパラメータ取得
        response = client.get("/logging/parameters/1.0.0")
        base_params = response.json()["parameters"]
        original_power = base_params["batting"]["power_base"]
        original_contact = base_params["batting"]["contact_base"]

        # 一部パラメータのみ変更
        response = client.post(
            "/logging/parameters/versions",
            json={
                "new_version": "1.0.1-inherit-test",
                "base_version": "1.0.0",
                "parameter_changes": {"batting.power_base": original_power + 5},
                "description": "Inheritance test",
            },
        )
        assert response.status_code == 200

        # 新バージョンのパラメータ確認
        response = client.get("/logging/parameters/1.0.1-inherit-test")
        new_params = response.json()["parameters"]

        # 変更されたパラメータ
        assert new_params["batting"]["power_base"] == original_power + 5

        # 変更されていないパラメータは継承されている
        assert new_params["batting"]["contact_base"] == original_contact
        assert new_params["pitching"] == base_params["pitching"]
        assert new_params["game_mechanics"] == base_params["game_mechanics"]

    def test_nested_parameter_changes(self, client: TestClient):
        """ネストしたパラメータ変更テスト"""
        response = client.post(
            "/logging/parameters/versions",
            json={
                "new_version": "1.0.2-nested-test",
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

        response = client.get("/logging/parameters/1.0.2-nested-test")
        params = response.json()["parameters"]

        assert params["batting"]["power_base"] == 85
        assert params["batting"]["contact_base"] == 75
        assert params["pitching"]["velocity_base"] == 90
        assert params["game_mechanics"]["hit_probability_base"] == 0.30


class TestVersionManagement:
    """バージョン管理テスト"""

    def test_version_activation_sequence(self, client: TestClient):
        """バージョンアクティブ化シーケンステスト"""
        # 複数バージョン作成
        versions = []
        for i in range(3):
            version_name = f"1.{i + 1}.0-seq-test"
            response = client.post(
                "/logging/parameters/versions",
                json={
                    "new_version": version_name,
                    "base_version": "1.0.0",
                    "parameter_changes": {"batting.power_base": 75 + i * 5},
                    "description": f"Sequential test version {i + 1}",
                },
            )
            assert response.status_code == 200
            versions.append(version_name)

        # バージョン切り替え
        for version in versions:
            response = client.put(f"/logging/parameters/{version}/activate")
            assert response.status_code == 200

            # アクティブバージョン確認
            current = client.get("/logging/parameters/current").json()
            assert current["version"] == version

        # 全バージョン取得してアクティブ状態確認
        all_versions = client.get("/logging/parameters/versions").json()
        active_versions = [v for v in all_versions if v["is_active"]]
        assert len(active_versions) == 1  # アクティブは1つだけ
        assert (
            active_versions[0]["version"] == versions[-1]
        )  # 最後にアクティブ化したもの
