#!/usr/bin/env python3
"""
Baseball Game API テスト実行スクリプト（コンテナ内実行版）
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def wait_for_mysql():
    """MySQL接続待機（コンテナ内から）"""
    print("⏳ Waiting for MySQL to be ready...")

    max_retries = 30
    for i in range(max_retries):
        try:
            # コンテナ内からmysqlコンテナに接続テスト
            import pymysql

            conn = pymysql.connect(
                host="mysql",  # Docker Compose サービス名
                port=3306,
                user="baseball_user",
                password="baseball_pass",
                database="baseball_game",
                connect_timeout=5,
            )
            conn.ping()
            conn.close()
            print("✅ MySQL is ready")
            return True

        except Exception as e:
            if i == max_retries - 1:
                print(f"❌ MySQL connection failed: {e}")
                return False

        print(f"⏳ MySQL not ready, retrying... ({i + 1}/{max_retries})")
        time.sleep(2)

    return False


def run_tests(test_pattern="tests/", verbose=False, coverage=False, stop_on_fail=True):
    """テスト実行"""
    print(f"🚀 Running tests: {test_pattern}")

    # 環境変数設定
    env = os.environ.copy()
    env["ENVIRONMENT"] = "testing"
    env["PYTHONPATH"] = "/app"

    # pytestコマンド構築
    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    if coverage:
        cmd.extend(
            ["--cov=app", "--cov-report=term-missing", "--cov-report=html:htmlcov"]
        )

    # テスト実行オプション
    cmd.extend(
        [
            "--tb=short",
            "--disable-warnings",
            "--strict-markers",
        ]
    )

    if stop_on_fail:
        cmd.append("--maxfail=3")

    cmd.append(test_pattern)

    print(f"📋 Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, env=env, check=False)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Test execution error: {e}")
        return False


def run_specific_test_class(class_name):
    """特定のテストクラスのみ実行"""
    print(f"🎯 Running specific test class: {class_name}")

    if "Game" in class_name:
        test_file = "tests/test_game_api.py"
    elif "Logging" in class_name:
        test_file = "tests/test_logging_api.py"
    else:
        test_file = "tests/"

    pattern = f"{test_file}::{class_name}"
    return run_tests(pattern, verbose=True, stop_on_fail=False)


def main():
    """メイン実行"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Baseball Game API Tests (Container Version)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                     # 全テスト実行
  python run_tests.py -v                  # 詳細出力
  python run_tests.py -c                  # カバレッジ付き
  python run_tests.py --class TestGameAPI # 特定クラスのみ
        """,
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="詳細出力")
    parser.add_argument(
        "--coverage", "-c", action="store_true", help="カバレッジレポート生成"
    )
    parser.add_argument("--class", dest="test_class", help="特定のテストクラスのみ実行")
    parser.add_argument("--pattern", default="tests/", help="テストファイルパターン")
    parser.add_argument(
        "--no-mysql-check", action="store_true", help="MySQL接続チェックをスキップ"
    )

    args = parser.parse_args()

    success = True

    try:
        # MySQL接続確認
        if not args.no_mysql_check:
            if not wait_for_mysql():
                print("❌ MySQL is not ready")
                sys.exit(1)

        # テスト実行
        if args.test_class:
            success = run_specific_test_class(args.test_class)
        else:
            success = run_tests(
                test_pattern=args.pattern, verbose=args.verbose, coverage=args.coverage
            )

        # 結果表示
        if success:
            print("\n🎉 All tests passed!")
            if args.coverage:
                print("📊 Coverage report: htmlcov/index.html")
        else:
            print("\n❌ Some tests failed!")

    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
