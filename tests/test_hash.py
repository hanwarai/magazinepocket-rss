"""API 検証ハッシュ関数のゴールデン値テスト。

サーバーが期待する `x-manga-hash` を生成するため、リファクタで
実装が変わっても出力が1bit単位で変わらないことを保証する。
"""

import main


def test_mc_sha256() -> None:
    assert main.mc("hello") == ("2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
    assert len(main.mc("anything")) == 64


def test_vh_sha512() -> None:
    assert main.vh("hello") == (
        "9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca7"
        "2323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043"
    )
    assert len(main.vh("anything")) == 128


def test_od_composes_sha256_and_sha512() -> None:
    sha256_part, _, sha512_part = main.Od("a", "b").partition("_")
    assert sha256_part == main.mc("a")
    assert sha512_part == main.vh("b")


def test_wh_sorted_keys_produce_stable_hash() -> None:
    a = main.wh({"k1": "v1", "k2": "v2"})
    b = main.wh({"k2": "v2", "k1": "v1"})
    assert a == b
    assert a == (
        "9b2ec8e420a774fec72d381688b980e28e4d039cc36da38fcc7edfab339f5f44"
        "24173863eab1902ef23ac03f2385361fc49eb4ace291a1dceb79e19a6fe10811"
    )


def test_wh_episode_payload_golden() -> None:
    # x-manga-hash の実 API 用ペイロード形状のゴールデン値
    assert main.wh({"episode_id_list": "1,2,3"}) == (
        "29b12def22e0499d66b654551f3280c202a1354f4a592718869ad69b2b984f52"
        "27adda06e32b273d3808f69e0e1cb558a4b2b7bfd79ec04637437b7c3efefbd9"
    )


def test_wh_empty_dict() -> None:
    assert main.wh({}) == (
        "5dfa62945f99778738d39e9e73d7ae2d8963409b6bf67bcd9344fc48cfb36882"
        "f8ce83356488b000f4cb7640eccf8d24084ca7d9f19006d8c44ca62631ac6ad3"
    )


def test_ae_is_alias_of_wh() -> None:
    payload = {"episode_id_list": "1,2,3"}
    assert main.Ae(payload) == main.wh(payload)
