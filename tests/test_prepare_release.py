from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_prepare_release_module():
    module_path = Path(__file__).resolve().parents[1] / "release" / "prepare_release.py"
    spec = importlib.util.spec_from_file_location("prepare_release", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rendered_release_notes_end_with_single_trailing_newline() -> None:
    prepare_release = _load_prepare_release_module()

    notes = prepare_release.render_notes(
        "1.2.3",
        [("feat: add release helper", ""), ("fix: normalize markdown output", "")],
        "Summary paragraph.",
    )
    normalized = prepare_release.ensure_single_trailing_newline(notes)

    assert normalized.endswith("\n")
    assert not normalized.endswith("\n\n")


def test_summary_file_without_trailing_newline_is_fixed(tmp_path: Path) -> None:
    prepare_release = _load_prepare_release_module()

    summary_file = tmp_path / "AI_RELEASE_SUMMARY.md"
    summary_file.write_text("Line one\nLine two", encoding="utf-8")

    summary_text = prepare_release.read_summary_text(summary_file)

    assert summary_text == "Line one\nLine two"
    assert summary_file.read_text(encoding="utf-8").endswith("\n")
