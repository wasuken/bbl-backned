#!/usr/bin/env python3
"""
Baseball Game API テスト実行スクリプト
E2Eテストの実行とレポート生成
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def check_docker_services():
    """Dockerサービス確認"""
    print("🔍 Checking Docker services...")

    try:
        result = subprocess.run(
            ["docker-compose", "ps", "--services", "--filter", "status=running"],
            capture_output=True,
            text=True,
            check=True,
        )

        running_services = result.stdout.strip().split("\n")
        required_services = ["mysql", "baseball_backend"]

        for service in required_services:
            if service not in running_services:
                print(f"❌ {service} is not running")
                return False

        print("✅ All required services are running")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Error checking Docker services: {e}")
        return False


def wait_for_services():
    """サービス起動待機"""
    print("⏳ Waiting for services to be ready...")

    import requests
    import time

    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        try:
            response = requests.get("http://localhost:8000/", timeout=5)
            if response.status_code == 200:
                print("✅ API service is ready")
                return True
        except requests.exceptions.RequestException:
            pass

        retry_count += 1
        time.sleep(2)
        print(f"⏳ Retrying... ({retry_count}/{max_retries})")

    print("❌ Services did not become ready in time")
    return False


def run_tests(test_path="tests/", verbose=False, coverage=False):
    """テスト実行"""
    print(f"🚀 Running tests from {test_path}")

    # pytestコマンド構築
    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend(
            ["--cov=app", "--cov-report=html:htmlcov", "--cov-report=term-missing"]
        )

    # テスト出力の改善
    cmd.extend(["--tb=short", "--strict-markers", "--disable-warnings"])

    cmd.append(test_path)

    print(f"📋 Running command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Test execution failed: {e}")
        return False


def generate_test_report():
    """テストレポート生成"""
    print("📊 Generating test report...")

    # JUnitレポート付きでテスト再実行
    cmd = [
        "python",
        "-m",
        "pytest",
        "--junitxml=test-results.xml",
        "--cov=app",
        "--cov-report=xml",
        "--cov-report=html:htmlcov",
        "tests/",
    ]

    try:
        subprocess.run(cmd, check=True)
        print("✅ Test report generated:")
        print("  - JUnit XML: test-results.xml")
        print("  - Coverage HTML: htmlcov/index.html")
        print("  - Coverage XML: coverage.xml")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to generate test report")
        return False


def cleanup_test_environment():
    """テスト環境クリーンアップ"""
    print("🧹 Cleaning up test environment...")

    # テスト用一時ファイル削除
    temp_files = ["test-results.xml", "coverage.xml", ".coverage"]

    for file in temp_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"  Removed {file}")

    # テスト用DBクリーンアップは conftest.py で自動実行
    print("✅ Cleanup completed")


def main():
    """メイン実行"""
    import argparse

    parser = argparse.ArgumentParser(description="Run Baseball Game API E2E tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--coverage", "-c", action="store_true", help="Generate coverage report"
    )
    parser.add_argument(
        "--report", "-r", action="store_true", help="Generate full test report"
    )
    parser.add_argument(
        "--skip-service-check", action="store_true", help="Skip Docker service check"
    )
    parser.add_argument("--test-path", default="tests/", help="Path to test files")
    parser.add_argument("--cleanup", action="store_true", help="Only run cleanup")

    args = parser.parse_args()

    if args.cleanup:
        cleanup_test_environment()
        return

    success = True

    try:
        # Docker サービス確認
        # if not args.skip_service_check:
        #     if not check_docker_services():
        #         print("💡 Try running: docker-compose up -d")
        #         sys.exit(1)

        #     if not wait_for_services():
        #         print("💡 Check if services are running properly")
        #         sys.exit(1)

        # テスト実行
        if args.report:
            success = generate_test_report()
        else:
            success = run_tests(
                test_path=args.test_path, verbose=args.verbose, coverage=args.coverage
            )

        if success:
            print("\n🎉 All tests passed!")
            print("\n📈 Next steps:")
            print("  - Check test coverage: open htmlcov/index.html")
            print("  - Review test results: test-results.xml")
            print("  - Add more test cases as needed")
        else:
            print("\n❌ Some tests failed!")
            print("\n🔧 Debug suggestions:")
            print("  - Check service logs: docker-compose logs")
            print("  - Verify database connection")
            print(
                "  - Run tests individually: pytest tests/test_game_api.py::TestGameAPI::test_root_endpoint -v"
            )

    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
        success = False

    finally:
        if not success:
            sys.exit(1)


pif __name__ == "__main__":
    main()
