"""Usage snapshot data types and the pure display formatters that render them.

No Qt, no network — these are the pieces every backend and the info bar agree on.
"""
import pytest


def test_token_counts_total_sums_input_and_output_only():
    from SciQLop.components.agents.backend import TokenCounts

    # cache_read is deliberately excluded: providers differ on whether cached
    # tokens are already counted inside input_tokens, so adding them would
    # double-count on some backends.
    t = TokenCounts(input=1000, output=250, cache_read=9000)
    assert t.total == 1250


def test_token_counts_total_is_none_when_nothing_known():
    from SciQLop.components.agents.backend import TokenCounts

    assert TokenCounts().total is None


def test_context_percent_needs_both_halves():
    from SciQLop.components.agents.backend import UsageSnapshot

    assert UsageSnapshot(context_tokens=50_000, context_max=200_000).context_percent == 25.0
    assert UsageSnapshot(context_tokens=50_000).context_percent is None
    assert UsageSnapshot(context_max=200_000).context_percent is None
    assert UsageSnapshot(context_tokens=0, context_max=0).context_percent is None


def test_fmt_tokens_scales_by_magnitude():
    from SciQLop.components.agents.chat.formatters import fmt_tokens

    assert fmt_tokens(None) == ""
    assert fmt_tokens(950) == "950"
    assert fmt_tokens(127_000) == "127.0k"
    assert fmt_tokens(2_400_000) == "2.40M"


def test_fmt_cost_distinguishes_usd_from_credits():
    from SciQLop.components.agents.backend import Cost
    from SciQLop.components.agents.chat.formatters import fmt_cost

    assert fmt_cost(None) == ""
    assert fmt_cost(Cost(amount=0.42)) == "$0.42"
    assert fmt_cost(Cost(amount=1.5, unit="credits")) == "1.50 credits"


def test_fmt_duration_switches_to_minutes():
    from SciQLop.components.agents.chat.formatters import fmt_duration

    assert fmt_duration(None) == ""
    assert fmt_duration(0) == ""
    assert fmt_duration(4200) == "4.2s"
    assert fmt_duration(108_000) == "1m 48s"


def test_fmt_quota_prefers_percent_then_absolute():
    from SciQLop.components.agents.backend import Quota
    from SciQLop.components.agents.chat.formatters import fmt_quota

    assert fmt_quota(None) == ""
    assert fmt_quota(Quota(label="budget", unlimited=True)) == "unlimited budget"
    # consumption, not headroom — a percentage in this strip always reads as
    # "how much of the window is gone", so 82.4% remaining shows as 18%.
    assert fmt_quota(
        Quota(label="premium requests", percent_remaining=82.4)
    ) == "premium requests 18%"
    assert fmt_quota(
        Quota(label="premium requests", remaining=1200)
    ) == "1.2k premium requests left"


def test_fmt_carbon_scales_grams_to_kilos():
    from SciQLop.components.agents.backend import CarbonFootprint
    from SciQLop.components.agents.chat.formatters import fmt_carbon

    assert fmt_carbon(None) == ""
    assert fmt_carbon(CarbonFootprint(kg_co2eq=0.0043)) == "4.3 gCO₂eq"
    assert fmt_carbon(CarbonFootprint(kg_co2eq=2.5)) == "2.50 kgCO₂eq"
    assert fmt_carbon(CarbonFootprint(kwh=0.012)) == "12.0 Wh"


def test_info_segments_renders_only_what_is_present():
    from SciQLop.components.agents.backend import Cost, TokenCounts, UsageSnapshot
    from SciQLop.components.agents.chat.formatters import info_segments

    tokens_only = UsageSnapshot(tokens=TokenCounts(input=1000, output=200))
    assert info_segments(tokens_only) == ["1.2k"]

    rich = UsageSnapshot(
        model="Opus 4.5",
        tokens=TokenCounts(input=100_000, output=27_000),
        cost=Cost(amount=0.42),
        context_tokens=168_000,
        context_max=500_000,
    )
    assert info_segments(rich, effort="high") == [
        "Opus 4.5", "high", "127.0k", "34%", "$0.42",
    ]


def test_info_segments_empty_for_nothing_to_show():
    from SciQLop.components.agents.backend import UsageSnapshot
    from SciQLop.components.agents.chat.formatters import info_segments

    assert info_segments(None) == []
    assert info_segments(UsageSnapshot()) == []


def test_quota_percent_used_is_derived_from_remaining():
    from SciQLop.components.agents.backend import Quota

    assert Quota(label="5h", percent_remaining=18.0).percent_used == 82.0
    assert Quota(label="5h").percent_used is None


def test_fmt_reset_time_renders_clock_for_today_and_day_for_later():
    from SciQLop.components.agents.chat.formatters import fmt_reset_time

    # 2026-07-31 19:30 local, seen from 14:00 the same day -> clock only.
    now = _local_epoch(2026, 7, 31, 14, 0)
    assert fmt_reset_time(_local_epoch(2026, 7, 31, 19, 30), now=now) == "19:30"
    # Monday 09:00, four days out -> weekday qualifies it.
    assert fmt_reset_time(_local_epoch(2026, 8, 3, 9, 0), now=now) == "Mon 09:00"
    assert fmt_reset_time(None, now=now) == ""


def test_fmt_quota_reports_usage_and_reset():
    from SciQLop.components.agents.backend import Quota
    from SciQLop.components.agents.chat.formatters import fmt_quota

    now = _local_epoch(2026, 7, 31, 14, 0)
    quota = Quota(label="5h", percent_remaining=18.0,
                  resets_at=_local_epoch(2026, 7, 31, 19, 30))
    assert fmt_quota(quota, now=now) == "5h 82% ↻19:30"


def test_fmt_quota_without_a_reset_time_omits_the_arrow():
    from SciQLop.components.agents.backend import Quota
    from SciQLop.components.agents.chat.formatters import fmt_quota

    assert fmt_quota(Quota(label="5h", percent_remaining=18.0)) == "5h 82%"


def test_fmt_quota_still_handles_unlimited_and_absolute_counts():
    from SciQLop.components.agents.backend import Quota
    from SciQLop.components.agents.chat.formatters import fmt_quota

    assert fmt_quota(Quota(label="budget", unlimited=True)) == "unlimited budget"
    assert fmt_quota(Quota(label="premium requests", remaining=1200)) == \
        "1.2k premium requests left"


def test_info_segments_renders_every_quota_window():
    from SciQLop.components.agents.backend import Quota, UsageSnapshot
    from SciQLop.components.agents.chat.formatters import info_segments

    now = _local_epoch(2026, 7, 31, 14, 0)
    snapshot = UsageSnapshot(
        model="Opus 4.5",
        quotas=(
            Quota(label="5h", percent_remaining=18.0,
                  resets_at=_local_epoch(2026, 7, 31, 19, 30)),
            Quota(label="week", percent_remaining=59.0,
                  resets_at=_local_epoch(2026, 8, 3, 9, 0)),
        ),
    )
    assert info_segments(snapshot, now=now) == [
        "Opus 4.5", "5h 82% ↻19:30", "week 41% ↻Mon 09:00",
    ]


def _local_epoch(year, month, day, hour, minute) -> float:
    from datetime import datetime

    return datetime(year, month, day, hour, minute).timestamp()
