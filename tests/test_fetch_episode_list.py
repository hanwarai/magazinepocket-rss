"""fetch_episode_list の HTTP 契約テスト。

requests-mock で API レスポンスを差し替え、以下を検証する:
- エンドポイント URL / POST メソッド / フォームエンコード
- 必須ヘッダー (x-manga-hash / Referer / platform)
- episode_id_list は直近 EPISODE_HASH_WINDOW 件のみをカンマ区切りで送る
- 4xx/5xx は raise_for_status で例外送出
"""

import pytest
import requests
import requests_mock as rm_module

import main


def test_posts_to_api_url_with_required_headers(requests_mock: rm_module.Mocker) -> None:
    requests_mock.post(main.API_URL, json={"episode_list": []})

    episodes = main.fetch_episode_list(main.create_session(), [1, 2, 3])

    assert episodes == []
    req = requests_mock.last_request
    assert req is not None
    assert req.method == "POST"
    assert req.url == main.API_URL
    assert req.headers["Referer"] == "https://pocket.shonenmagazine.com/"
    assert req.headers["x-manga-is-crawler"] == "false"
    assert req.headers["x-manga-platform"] == "3"
    assert req.headers["x-manga-hash"]  # 非空


def test_sends_last_window_of_episode_ids_form_encoded(
    requests_mock: rm_module.Mocker,
) -> None:
    requests_mock.post(main.API_URL, json={"episode_list": []})
    ids = list(range(100, 100 + main.EPISODE_HASH_WINDOW + 3))  # 13件

    main.fetch_episode_list(main.create_session(), ids)

    req = requests_mock.last_request
    assert req is not None
    sent = req.text  # application/x-www-form-urlencoded
    expected_tail = ",".join(str(i) for i in ids[-main.EPISODE_HASH_WINDOW :])
    # urlencode された形 ("episode_id_list=100%2C101%2C...")
    assert expected_tail.replace(",", "%2C") in sent


def test_hash_matches_Ae_of_payload(requests_mock: rm_module.Mocker) -> None:
    requests_mock.post(main.API_URL, json={"episode_list": []})
    ids = [1, 2, 3]

    main.fetch_episode_list(main.create_session(), ids)

    expected = main.Ae({"episode_id_list": "1,2,3"})
    req = requests_mock.last_request
    assert req is not None
    assert req.headers["x-manga-hash"] == expected


def test_returns_episode_list_from_json(requests_mock: rm_module.Mocker) -> None:
    payload = {
        "episode_list": [
            {"episode_id": 1, "point": 0, "episode_name": "A", "start_time": "2026-01-01 00:00:00"},
            {
                "episode_id": 2,
                "point": 50,
                "episode_name": "B",
                "start_time": "2026-01-08 00:00:00",
            },
        ]
    }
    requests_mock.post(main.API_URL, json=payload)

    episodes = main.fetch_episode_list(main.create_session(), [1])

    assert episodes == payload["episode_list"]


def test_missing_episode_list_key_returns_empty(requests_mock: rm_module.Mocker) -> None:
    requests_mock.post(main.API_URL, json={"other": "data"})

    assert main.fetch_episode_list(main.create_session(), [1]) == []


def test_raises_on_http_error(requests_mock: rm_module.Mocker) -> None:
    requests_mock.post(main.API_URL, status_code=500)

    with pytest.raises(requests.HTTPError):
        main.fetch_episode_list(main.create_session(), [1])


def test_empty_episode_ids_sends_empty_payload(requests_mock: rm_module.Mocker) -> None:
    requests_mock.post(main.API_URL, json={"episode_list": []})

    main.fetch_episode_list(main.create_session(), [])

    req = requests_mock.last_request
    assert req is not None
    assert "episode_id_list=" in req.text
