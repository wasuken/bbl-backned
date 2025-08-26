# tests/test_config.py を削除し、テスト用設定を conftest.py に統合する

# 代わりに、テスト実行用の簡単なスクリプトを作成
import subprocess
import sys
import os


def run_tests():
    """テスト実行用ヘルパー"""

    # テスト環境変数設定
    os.environ["ENVIRONMENT"] = "testing"

    # pytestコマンド実行
    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--disable-warnings",
        "--maxfail=5",  # 5個のテスト失敗で停止
    ]

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"テスト実行エラー: {e}")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
