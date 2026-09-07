#!/usr/bin/env python3
"""Prepare release notes and version updates from conventional commits."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def get_last_tag() -> str | None:
    try:
        return git("describe", "--tags", "--abbrev=0", "--match", "v*")
    except subprocess.CalledProcessError:
        return None


def parse_version(tag: str | None) -> tuple[int, int, int, int | None]:
    if not tag:
        return (0, 0, 0, None)
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)(?:b(\d+))?$", tag)
    if not match:
        raise ValueError(f"Unsupported tag format: {tag}")
    major, minor, patch, beta = match.groups()
    return int(major), int(minor), int(patch), int(beta) if beta else None


def bump_from_commits(commits: list[tuple[str, str]]) -> str:
    bump = "patch"
    for subject, body in commits:
        if re.search(r"(^|\n)BREAKING CHANGE", body, re.IGNORECASE) or re.match(
            r"^\w+\(?.*\)?!:", subject
        ):
            return "major"
        if re.match(r"^feat(\(.*\))?:", subject):
            bump = "minor"
    return bump


def next_version(last_tag: str | None, bump: str, beta: bool) -> str:
    major, minor, patch, beta_num = parse_version(last_tag)
    if beta and beta_num is not None:
        return f"{major}.{minor}.{patch}b{beta_num + 1}"

    if not beta and beta_num is not None:
        return f"{major}.{minor}.{patch}"

    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1

    if not beta:
        return f"{major}.{minor}.{patch}"

    return f"{major}.{minor}.{patch}b1"


def get_commits(last_tag: str | None) -> list[tuple[str, str]]:
    rev = f"{last_tag}..HEAD" if last_tag else "HEAD"
    out = git("log", rev, "--pretty=format:%s%x1f%b%x1e", "--no-merges")
    commits: list[tuple[str, str]] = []
    for item in out.split("\x1e"):
        item = item.strip(" \n\r\t")

        if not item:
            continue
        subject, body = item.split("\x1f", 1)
        commits.append((subject.strip(), body.strip()))
    return commits


def render_notes(version: str, commits: list[tuple[str, str]], summary_text: str) -> str:
    lines = [f"# Release {version}", ""]
    if summary_text:
        lines.extend([summary_text.strip(), "", "---", ""])
    for subject, _ in commits:
        lines.append(f"- {subject}")
    lines.append("")
    return "\n".join(lines)


def ensure_single_trailing_newline(text: str) -> str:
    return text.rstrip("\n") + "\n"


def read_summary_text(summary_file: Path) -> str:
    if not summary_file.exists():
        return ""

    raw_summary = summary_file.read_text(encoding="utf-8")
    normalized_summary = ensure_single_trailing_newline(raw_summary)
    if raw_summary != normalized_summary:
        summary_file.write_text(normalized_summary, encoding="utf-8")

    return normalized_summary.strip()


def replace_version(new_version: str) -> None:
    pyproject = ROOT / "pyproject.toml"
    init_py = ROOT / "ai_todo" / "__init__.py"
    legacy = ROOT / "legacy" / "todo.ai"

    pyproject.write_text(
        re.sub(
            r'^version = ".*"$', f'version = "{new_version}"', pyproject.read_text(), flags=re.M
        ),
        encoding="utf-8",
    )
    init_py.write_text(
        re.sub(
            r'^__version__ = ".*"$',
            f'__version__ = "{new_version}"',
            init_py.read_text(),
            flags=re.M,
        ),
        encoding="utf-8",
    )

    legacy_text = legacy.read_text(encoding="utf-8")
    legacy_text = re.sub(r'^VERSION=".*"$', f'VERSION="{new_version}"', legacy_text, flags=re.M)
    legacy_text = re.sub(r"^# Version: .*$", f"# Version: {new_version}", legacy_text, flags=re.M)
    legacy.write_text(legacy_text, encoding="utf-8")

    subprocess.run(["uv", "lock"], cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare release notes and version updates")
    parser.add_argument("--beta", action="store_true", help="Prepare a beta release")
    parser.add_argument("--summary", default="", help="Optional release summary text")
    args = parser.parse_args()

    last_tag = get_last_tag()
    commits = get_commits(last_tag)
    bump = bump_from_commits(commits)
    version = next_version(last_tag, bump, args.beta)

    summary_file = ROOT / "release" / "AI_RELEASE_SUMMARY.md"
    file_summary = read_summary_text(summary_file)
    summary_text = "\n\n".join(filter(None, [args.summary.strip(), file_summary]))

    notes = ensure_single_trailing_newline(render_notes(version, commits, summary_text))
    (ROOT / "release" / "RELEASE_NOTES.md").write_text(notes, encoding="utf-8")

    replace_version(version)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
