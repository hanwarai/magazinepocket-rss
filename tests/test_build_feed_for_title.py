"""build_feed_for_title のエンドツーエンド（HTTP はモック）テスト。

タイトルページの HTML + NUXT_DATA を与え、エピソード API レスポンスを
モックして、feeds/<id>.xml が生成され戻り値が期待通りか検証する。
"""

import json
from pathlib import Path

import pytest
import requests_mock as rm_module

import main

FEED_ID = "01153"
TITLE_URL = f"{main.TITLE_BASE_URL}{FEED_ID}"


def _title_html(
    title: str = "テスト作品",
    description: str = "あらすじ本文",
    image: str | None = "https://example.com/cover.jpg",
    nuxt_payload: list | None = None,
) -> str:
    nuxt = json.dumps(
        nuxt_payload
        if nuxt_payload is not None
        else [{"episode_id_list": 1}, [2], {"episode_id": 42}]
    )
    img_html = f'<img src="{image}">' if image else ""
    return f"""
    <!doctype html>
    <html><body>
      <h1>{title}</h1>
      <div class="p-episode__comic-description">{description}</div>
      <div class="p-episode__comic-img">{img_html}</div>
      <script id="__NUXT_DATA__">{nuxt}</script>
    </body></html>
    """


@pytest.fixture
def feeds_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(main, "FEEDS_DIR", tmp_path)
    return tmp_path


def test_generates_xml_and_returns_metadata(
    requests_mock: rm_module.Mocker, feeds_dir: Path
) -> None:
    requests_mock.get(TITLE_URL, text=_title_html())
    requests_mock.post(
        main.API_URL,
        json={
            "episode_list": [
                {
                    "episode_id": 42,
                    "point": 0,
                    "episode_name": "第1話",
                    "start_time": "2026-04-01 10:00:00",
                },
                {
                    "episode_id": 43,
                    "point": 50,  # 有料は除外されるはず
                    "episode_name": "第2話",
                    "start_time": "2026-04-08 10:00:00",
                },
            ]
        },
    )

    result = main.build_feed_for_title(main.create_session(), FEED_ID)

    assert result == {"id": FEED_ID, "title": "テスト作品"}
    xml_path = feeds_dir / f"{FEED_ID}.xml"
    assert xml_path.exists()
    xml = xml_path.read_text()
    assert "第1話" in xml
    assert "第2話" not in xml  # 有料回は含まれない
    assert f"{TITLE_URL}/episode/42" in xml


def test_returns_none_on_404(requests_mock: rm_module.Mocker, feeds_dir: Path) -> None:
    requests_mock.get(TITLE_URL, status_code=404)

    assert main.build_feed_for_title(main.create_session(), FEED_ID) is None
    assert not (feeds_dir / f"{FEED_ID}.xml").exists()


def test_returns_none_when_no_nuxt_data(
    requests_mock: rm_module.Mocker, feeds_dir: Path
) -> None:
    requests_mock.get(
        TITLE_URL,
        text="<html><body><h1>タイトル</h1></body></html>",
    )

    assert main.build_feed_for_title(main.create_session(), FEED_ID) is None


def test_returns_none_when_no_h1(
    requests_mock: rm_module.Mocker, feeds_dir: Path
) -> None:
    html = '<html><body><script id="__NUXT_DATA__">[]</script></body></html>'
    requests_mock.get(TITLE_URL, text=html)

    assert main.build_feed_for_title(main.create_session(), FEED_ID) is None


def test_writes_feed_even_when_episode_api_fails(
    requests_mock: rm_module.Mocker, feeds_dir: Path
) -> None:
    # API が落ちてもタイトルページのフィードは生成される（エピソードは空）
    requests_mock.get(TITLE_URL, text=_title_html(title="連載中"))
    requests_mock.post(main.API_URL, status_code=500)

    result = main.build_feed_for_title(main.create_session(), FEED_ID)

    assert result == {"id": FEED_ID, "title": "連載中"}
    assert (feeds_dir / f"{FEED_ID}.xml").exists()


def test_handles_missing_description_and_image(
    requests_mock: rm_module.Mocker, feeds_dir: Path
) -> None:
    html = f"""
    <html><body>
      <h1>最小構成</h1>
      <script id="__NUXT_DATA__">[]</script>
    </body></html>
    """
    requests_mock.get(TITLE_URL, text=html)
    requests_mock.post(main.API_URL, json={"episode_list": []})

    result = main.build_feed_for_title(main.create_session(), FEED_ID)

    assert result == {"id": FEED_ID, "title": "最小構成"}
