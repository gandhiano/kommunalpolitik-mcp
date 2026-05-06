from __future__ import annotations

from src.tools.witzenhausen import _fts_query


def test_fts_query_filters_question_stopwords_and_uses_or_prefixes() -> None:
    query = _fts_query("Welche Beschlüsse oder Diskussionen gab es zum Haushalt seit 2021?")

    assert "Welche" not in query
    assert "oder" not in query
    assert "Haushalt*" in query
    assert "Beschlüsse*" in query
    assert "Diskussionen*" in query
    assert " OR " in query


def test_fts_query_falls_back_for_punctuation_only() -> None:
    assert _fts_query("?!") == '"?!"'
