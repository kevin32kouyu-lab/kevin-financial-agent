"""仓库密钥扫描：阻止明显 API Key 或 token 进入提交。"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "dist", "__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".sqlite3", ".db"}
PLACEHOLDER_MARKERS = ("replace-with", "your-", "example", "placeholder", "dummy", "changeme")
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{24,}"),
]
ASSIGNMENT_PATTERN = re.compile(r"(?i)^\s*([A-Z0-9_]*(?:API[_-]?KEY|SECRET|TOKEN)|api[_-]?key|secret|token)\s*[:=]\s*[\"']?([^\"'#\s,]+)")


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """描述一个疑似密钥命中。"""

    path: Path
    line_number: int
    excerpt: str


def iter_scannable_files(root: Path = ROOT) -> list[Path]:
    """列出需要扫描的文本文件。"""
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = set(path.relative_to(root).parts)
        if relative_parts & EXCLUDED_PARTS:
            continue
        if "runtime" in relative_parts and "data" in relative_parts:
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return files


def find_secret_candidates(paths: Iterable[Path]) -> list[SecretFinding]:
    """扫描文件，返回疑似真实密钥。"""
    findings: list[SecretFinding] = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            lowered = line.lower()
            if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
                continue
            if _line_contains_secret(line):
                findings.append(
                    SecretFinding(
                        path=path,
                        line_number=line_number,
                        excerpt=_redact(line.strip()),
                    )
                )
    return findings


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="Scan repository files for likely committed secrets.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    findings = find_secret_candidates(iter_scannable_files(args.root.resolve()))
    if not findings:
        print("Secret scan passed: no obvious API keys or tokens found.")
        return 0
    print("Secret scan failed:")
    for finding in findings:
        rel = finding.path.relative_to(args.root.resolve()) if finding.path.is_relative_to(args.root.resolve()) else finding.path
        print(f"- {rel}:{finding.line_number}: {finding.excerpt}")
    return 1


def _redact(value: str) -> str:
    """隐藏命中行中部，避免日志再次泄露。"""
    if len(value) <= 16:
        return "***"
    return f"{value[:8]}...{value[-4:]}"


def _line_contains_secret(line: str) -> bool:
    """判断一行是否包含明显真实密钥。"""
    if any(pattern.search(line) for pattern in SECRET_PATTERNS):
        return True
    assignment = ASSIGNMENT_PATTERN.search(line)
    if not assignment:
        return False
    return _looks_like_secret_value(assignment.group(2))


def _looks_like_secret_value(value: str) -> bool:
    """排除代码引用，只保留像真实密钥的赋值。"""
    cleaned = value.strip().strip(",)")
    lowered = cleaned.lower()
    if lowered.startswith(("self.", "settings.", "appsettings", "os.", "getenv", "_get_")):
        return False
    if any(char in cleaned for char in ("(", ")", "{", "}", "[")):
        return False
    if "." in cleaned and "_" in cleaned:
        return False
    return len(cleaned) >= 24 and bool(re.search(r"[A-Za-z]", cleaned)) and bool(re.search(r"\d", cleaned))


if __name__ == "__main__":
    sys.exit(main())
