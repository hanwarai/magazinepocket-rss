"""NUXT_DATA payload から episode_id を抽出するロジックのテスト。"""

import main


def test_extracts_ids_via_index_lookup():
    # 典型的な NUXT_DATA 形状: 最初の dict が episode_id_list のインデックス、
    # そのインデックスが配列、配列の各要素はさらに別のインデックス
    values = [
        {"episode_id_list": 1},
        [2, 3, 4],
        100,
        200,
        300,
    ]
    assert main.episode_id_list(values) == [100, 200, 300]


def test_returns_none_when_key_absent():
    values = [{"other_key": 1}, "foo", 42]
    assert main.episode_id_list(values) is None


def test_returns_none_for_empty_list():
    assert main.episode_id_list([]) is None


def test_finds_key_in_later_dict():
    values = [
        {"something_else": 0},
        {"episode_id_list": 2},
        [3],
        999,
    ]
    assert main.episode_id_list(values) == [999]
