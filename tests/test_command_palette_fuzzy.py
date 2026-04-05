from tests.fixtures import *


def test_exact_match_scores_highest():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score
    score_exact = fuzzy_score("plot", "plot")
    score_partial = fuzzy_score("plot", "plot product")
    assert score_exact > score_partial


def test_prefix_match_scores_higher_than_middle():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score
    score_prefix = fuzzy_score("plot", "plot product in panel")
    score_middle = fuzzy_score("plot", "new plot panel")
    assert score_prefix > score_middle


def test_word_boundary_bonus():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score
    score_boundary = fuzzy_score("np", "new panel")
    score_no_boundary = fuzzy_score("np", "snap")
    assert score_boundary > score_no_boundary


def test_no_match_returns_zero():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score
    assert fuzzy_score("xyz", "plot product") == 0


def test_case_insensitive():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score
    assert fuzzy_score("PLOT", "plot product") > 0


def test_fuzzy_match_positions():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_match
    score, positions = fuzzy_match("np", "new panel")
    assert score > 0
    assert 0 in positions
    assert 4 in positions


def test_empty_query_matches_everything():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score
    assert fuzzy_score("", "anything") > 0
