import os

import pytest

from tests.utils.env import temp_env


def test_nl_parsing_basic_phrases():
    from temporal_utils import parse_natural_language_time

    with temp_env({"AXIOM_DATEPARSER_ENABLED": "1"}):
        assert parse_natural_language_time("What did we talk about yesterday?") == "since:1d"
        assert parse_natural_language_time("What happened last week?") == "since:7d"
        # Be robust to punctuation/casing
        assert parse_natural_language_time("LAST week summary.") == "since:7d"


def test_nl_parsing_absolute_date_before():
    from temporal_utils import parse_natural_language_time

    with temp_env({"AXIOM_DATEPARSER_ENABLED": "1"}):
        op = parse_natural_language_time("What happened before Christmas 2024?")
        assert op == "before:2024-12-25"


def test_nl_parsing_invalid_phrase_fallback():
    from temporal_utils import parse_natural_language_time

    with temp_env({"AXIOM_DATEPARSER_ENABLED": "1"}):
        assert parse_natural_language_time("remind me in the flibbertigibbet time") is None


def test_disable_nl_parsing_in_planner():
    import retrieval_planner as rp

    base = "What did we talk about yesterday?"
    with temp_env({
        "AXIOM_NL_TIME_PARSING_ENABLED": "0",
        "AXIOM_DATEPARSER_ENABLED": "1",
        "AXIOM_TEMPORAL_SEQUENCING_ENABLED": "1",
    }):
        out = rp.rewrite_query_with_temporal_nl(base)
        assert out == base  # no rewrite when disabled

