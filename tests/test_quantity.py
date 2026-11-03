"""Тесты разбора количества ингредиентов (ЛР-6)."""

from quantity import parse_quantity


def test_parse_integer():
    assert parse_quantity("3") == (3.0, "3")


def test_parse_dot_decimal():
    assert parse_quantity("2.5") == (2.5, "2.5")


def test_parse_comma_decimal():
    assert parse_quantity("50,5") == (50.5, "50,5")


def test_parse_whitespace():
    assert parse_quantity("  3 ") == (3.0, "3")


def test_parse_empty_string():
    assert parse_quantity("") == (None, "")


def test_parse_none():
    assert parse_quantity(None) == (None, "")


def test_parse_not_a_number():
    assert parse_quantity("по вкусу") == (None, "по вкусу")
