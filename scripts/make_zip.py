#!/usr/bin/env python
"""Package the repo into autoagent-project.zip (cross-platform, stdlib only).

Excludes: node_modules, .venv, __pycache__, .next, .git, .pytest_cache, any real .env file
(.env.example files are kept). Then verifies the archive: lists contents and scans for secrets.

Usage: python scripts/make_zip.py [--out PATH] [--no-list]
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOP = "autoagent-project"
EXCLUDE_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".next", ".git", ".pytest_cache", ".mypy_cache",
                ".idea", ".vscode", "dist"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".log", ".sqlite3", ".sqlite", ".tsbuildinfo", ".zip"}
EXCLUDE_NAMES = {".dev-pids", ".DS_Store", "Thumbs.db"}

SECRET_PATTERNS = {
    "Groq key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    "Zoho OAuth token/code": re.compile(r"\b1000\.[0-9a-f]{32}\.[0-9a-f]{32}\b"),
    "Private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "Bearer/oauth token": re.compile(r"Zoho-oauthtoken\s+[0-9a-f]{16,}"),
}
SECRET_ENV_KEY = re.compile(r"^[ \t]*([A-Z0-9_]*(KEY|SECRET|TOKEN|PASSWORD)[A-Z0-9_]*)[ \t]*=[ \t]*(\S*)", re.M)


def is_real_env(name: str) -> bool:
    return name == ".env" or (name.startswith(".env") and not name.endswith(".example"))


def included(path: Path, out: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
        return False
    n = path.name
    return not (path == out or n in EXCLUDE_NAMES or is_real_env(n) or path.suffix in EXCLUDE_SUFFIX)


def build(out: Path) -> list[str]:
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and included(p, out))
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in files:
            zf.write(p, f"{TOP}/{p.relative_to(ROOT).as_posix()}")
    return [f"{TOP}/{p.relative_to(ROOT).as_posix()}" for p in files]


def verify(out: Path, show: bool) -> int:
    problems: list[str] = []
    with zipfile.ZipFile(out) as zf:
        assert zf.testzip() is None, "corrupt zip"
        names = zf.namelist()
        for n in names:
            parts = n.split("/")
            base = parts[-1]
            if any(p in EXCLUDE_DIRS for p in parts[:-1]):
                problems.append(f"excluded directory leaked: {n}")
            if is_real_env(base):
                problems.append(f"real env file inside: {n}")
            data = zf.read(n)
            if b"\0" in data[:2048]:
                continue
            text = data.decode("utf-8", "replace")
            for label, rx in SECRET_PATTERNS.items():
                if rx.search(text):
                    problems.append(f"{label} pattern in {n}")
            if base.endswith(".example"):
                for m in SECRET_ENV_KEY.finditer(text):
                    if m.group(3).strip():
                        problems.append(f"non-empty secret-like value in {n}: {m.group(1)}")
        required = [f"{TOP}/{p}" for p in ("backend/.env.example", "frontend/.env.example", "README.md",
                                           "scripts/dev.ps1", "scripts/seed_zoho.py", "docs/architecture.md",
                                           "backend/alembic/versions/0001_init.py")]
        problems += [f"missing from zip: {r}" for r in required if r not in names]
        if show:
            print(f"\nContents of {out.name} ({len(names)} files):")
            for info in zf.infolist():
                print(f"  {info.file_size:>9,}  {info.filename}")
    print(f"\nzip: {out}  ({out.stat().st_size:,} bytes)")
    if problems:
        print("VERIFICATION FAILED:\n  - " + "\n  - ".join(problems))
        return 1
    print("VERIFICATION PASSED: no real .env files, no excluded directories, no secret patterns, "
          "no filled-in secrets in .env.example files.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "autoagent-project.zip"))
    ap.add_argument("--no-list", action="store_true")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    build(out)
    return verify(out, show=not a.no_list)


if __name__ == "__main__":
    sys.exit(main())
