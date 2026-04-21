"""SSL_VERIFY 等の環境変数をパースする _parse_bool の仕様テスト。"""

import pytest

from main import _parse_bool


@pytest.mark.parametrize("value", ["True", "true", "TRUE", "1", "yes", "on", "anything"])
def test_truthy_values(value):
    assert _parse_bool(value) is True


@pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF", ""])
def test_falsy_values(value):
    assert _parse_bool(value) is False


def test_whitespace_is_stripped():
    assert _parse_bool("  false  ") is False
    assert _parse_bool("  True  ") is True
