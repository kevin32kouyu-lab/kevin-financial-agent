"""统一验证入口：运行后端测试、前端类型检查、构建、密钥扫描和 E2E。"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_command(command: list[str], label: str) -> None:
    """运行一个验证命令，失败时立即停止。"""
    print(f"\n==> {label}")
    completed = subprocess.run(_resolve_command(command), cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _resolve_command(command: list[str]) -> list[str]:
    """解析跨平台命令路径，兼容 Windows 的 npm.cmd。"""
    executable = shutil.which(command[0]) or command[0]
    return [executable, *command[1:]]


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="Run Financial Agent verification checks.")
    parser.add_argument("--skip-e2e", action="store_true", help="Skip Playwright browser tests.")
    parser.add_argument("--only-e2e", action="store_true", help="Run only Playwright browser tests.")
    args = parser.parse_args()

    if args.only_e2e:
        run_command(["npm", "run", "test:e2e"], "E2E smoke tests")
        return 0

    run_command([sys.executable, "-m", "pytest", "-q"], "Backend tests")
    run_command([sys.executable, "scripts/check_secrets.py"], "Secret scan")
    run_command(["npm", "run", "typecheck"], "Frontend type check")
    run_command(["npm", "run", "build"], "Frontend production build")
    if not args.skip_e2e:
        run_command(["npm", "run", "test:e2e"], "E2E smoke tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
