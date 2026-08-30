"""feed.csv パース関数 read_feed_ids の仕様テスト。"""

from pathlib import Path

import pytest

import main


def _write(tmp_path: Path, content: str) -> Path:
    csv_path = tmp_path / "feed.csv"
    csv_path.write_text(content)
    return csv_path


def test_reads_valid_numeric_ids(tmp_path: Path) -> None:
    path = _write(tmp_path, "01153\n01524\n02368\n")
    assert list(main.read_feed_ids(path)) == ["01153", "01524", "02368"]


def test_skips_empty_lines_and_whitespace(tmp_path: Path) -> None:
    path = _write(tmp_path, "01153\n\n   \n01524\n")
    assert list(main.read_feed_ids(path)) == ["01153", "01524"]


def test_skips_non_numeric_ids(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = _write(tmp_path, "01153\n../etc/passwd\nfoo\n01524\n")
    with caplog.at_level("WARNING", logger="magazinepocket-rss"):
        assert list(main.read_feed_ids(path)) == ["01153", "01524"]
    assert any("invalid feed ID" in rec.message for rec in caplog.records)


def test_deduplicates_repeated_ids(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = _write(tmp_path, "01153\n01524\n01153\n01524\n02368\n")
    with caplog.at_level("WARNING", logger="magazinepocket-rss"):
        assert list(main.read_feed_ids(path)) == ["01153", "01524", "02368"]
    assert sum("duplicate feed ID" in rec.message for rec in caplog.records) == 2


def test_uses_only_first_column(tmp_path: Path) -> None:
    path = _write(tmp_path, "01153,extra,columns\n01524,ignored\n")
    assert list(main.read_feed_ids(path)) == ["01153", "01524"]


def test_strips_surrounding_whitespace_from_id(tmp_path: Path) -> None:
    path = _write(tmp_path, "  01153  \n")
    assert list(main.read_feed_ids(path)) == ["01153"]
