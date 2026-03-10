"""
Comprehensive tests for domain value objects.

Tests cover:
- RiskScore: validation (0-10 range), severity levels, to_dict serialization
- TimePeriod: validation (start before end), contains, last_n_days, rolling_windows
"""

import pytest
from datetime import datetime, timedelta, UTC

from domain.value_objects.risk_score import RiskScore
from domain.value_objects.time_period import TimePeriod


# ============================================================================
# RiskScore Tests
# ============================================================================


class TestRiskScore:
    """Tests for RiskScore value object."""

    def test_construction_valid_values(self):
        """RiskScore can be constructed with valid values 0-10."""
        for value in [0.0, 2.5, 5.0, 7.5, 10.0]:
            score = RiskScore(value=value)
            assert score.value == value

    def test_construction_with_label_and_evidence(self):
        """RiskScore can include label and evidence."""
        score = RiskScore(
            value=5.0,
            label="Team Knowledge Risk",
            evidence="3 components with knowledge concentration"
        )
        assert score.label == "Team Knowledge Risk"
        assert score.evidence == "3 components with knowledge concentration"

    def test_validation_rejects_below_zero(self):
        """RiskScore raises ValueError for value <0."""
        with pytest.raises(ValueError, match="RiskScore must be between 0 and 10"):
            RiskScore(value=-0.1)

    def test_validation_rejects_above_ten(self):
        """RiskScore raises ValueError for value >10."""
        with pytest.raises(ValueError, match="RiskScore must be between 0 and 10"):
            RiskScore(value=10.1)

    def test_validation_boundary_zero(self):
        """RiskScore accepts 0.0."""
        score = RiskScore(value=0.0)
        assert score.value == 0.0

    def test_validation_boundary_ten(self):
        """RiskScore accepts 10.0."""
        score = RiskScore(value=10.0)
        assert score.value == 10.0

    def test_severity_minimal_below_2(self):
        """severity returns 'minimal' for value <2."""
        for value in [0.0, 0.5, 1.9]:
            score = RiskScore(value=value)
            assert score.severity == "minimal"

    def test_severity_low_2_to_4(self):
        """severity returns 'low' for 2 <= value <4."""
        for value in [2.0, 3.0, 3.9]:
            score = RiskScore(value=value)
            assert score.severity == "low"

    def test_severity_medium_4_to_6(self):
        """severity returns 'medium' for 4 <= value <6."""
        for value in [4.0, 5.0, 5.9]:
            score = RiskScore(value=value)
            assert score.severity == "medium"

    def test_severity_high_6_to_8(self):
        """severity returns 'high' for 6 <= value <8."""
        for value in [6.0, 7.0, 7.9]:
            score = RiskScore(value=value)
            assert score.severity == "high"

    def test_severity_critical_8_and_above(self):
        """severity returns 'critical' for value >= 8."""
        for value in [8.0, 9.0, 10.0]:
            score = RiskScore(value=value)
            assert score.severity == "critical"

    def test_to_dict_serialization(self):
        """to_dict returns dict with value, severity, label, evidence."""
        score = RiskScore(
            value=7.5,
            label="Test Risk",
            evidence="Test evidence"
        )
        result = score.to_dict()

        assert result["value"] == 7.5
        assert result["severity"] == "high"
        assert result["label"] == "Test Risk"
        assert result["evidence"] == "Test evidence"

    def test_to_dict_without_label_and_evidence(self):
        """to_dict includes empty label and evidence by default."""
        score = RiskScore(value=5.0)
        result = score.to_dict()

        assert result["value"] == 5.0
        assert result["severity"] == "medium"
        assert result["label"] == ""
        assert result["evidence"] == ""

    def test_risk_score_is_frozen(self):
        """RiskScore instance is immutable."""
        score = RiskScore(value=5.0)
        with pytest.raises(AttributeError):
            score.value = 6.0


# ============================================================================
# TimePeriod Tests
# ============================================================================


class TestTimePeriod:
    """Tests for TimePeriod value object."""

    def test_construction_valid_period(self):
        """TimePeriod can be constructed with start before end."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 12, 31, tzinfo=UTC)
        period = TimePeriod(start=start, end=end)

        assert period.start == start
        assert period.end == end

    def test_validation_rejects_equal_times(self):
        """TimePeriod raises ValueError when start equals end."""
        dt = datetime(2024, 1, 1, tzinfo=UTC)
        with pytest.raises(ValueError, match="TimePeriod start must be before end"):
            TimePeriod(start=dt, end=dt)

    def test_validation_rejects_start_after_end(self):
        """TimePeriod raises ValueError when start is after end."""
        start = datetime(2024, 12, 31, tzinfo=UTC)
        end = datetime(2024, 1, 1, tzinfo=UTC)
        with pytest.raises(ValueError, match="TimePeriod start must be before end"):
            TimePeriod(start=start, end=end)

    def test_days_calculation(self):
        """days returns number of days between start and end."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 11, tzinfo=UTC)
        period = TimePeriod(start=start, end=end)

        assert period.days == 10

    def test_days_single_day_difference(self):
        """days returns 1 for consecutive days."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 2, tzinfo=UTC)
        period = TimePeriod(start=start, end=end)

        assert period.days == 1

    def test_days_across_months(self):
        """days correctly calculates across month boundaries."""
        start = datetime(2024, 1, 31, tzinfo=UTC)
        end = datetime(2024, 2, 29, tzinfo=UTC)  # 2024 is a leap year
        period = TimePeriod(start=start, end=end)

        assert period.days == 29

    def test_contains_returns_true_for_contained_datetime(self):
        """contains returns True for datetime within period."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 31, tzinfo=UTC)
        period = TimePeriod(start=start, end=end)

        dt = datetime(2024, 1, 15, tzinfo=UTC)
        assert period.contains(dt)

    def test_contains_returns_true_for_boundary_start(self):
        """contains returns True for datetime at start boundary."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 31, tzinfo=UTC)
        period = TimePeriod(start=start, end=end)

        assert period.contains(start)

    def test_contains_returns_true_for_boundary_end(self):
        """contains returns True for datetime at end boundary."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 31, tzinfo=UTC)
        period = TimePeriod(start=start, end=end)

        assert period.contains(end)

    def test_contains_returns_false_for_outside_datetime(self):
        """contains returns False for datetime outside period."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 31, tzinfo=UTC)
        period = TimePeriod(start=start, end=end)

        before = datetime(2023, 12, 31, tzinfo=UTC)
        after = datetime(2024, 2, 1, tzinfo=UTC)

        assert not period.contains(before)
        assert not period.contains(after)

    def test_contains_returns_false_just_before_start(self):
        """contains returns False for datetime just before start."""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 31, tzinfo=UTC)
        period = TimePeriod(start=start, end=end)

        just_before = datetime(2024, 1, 1, 11, 59, 59, tzinfo=UTC)
        assert not period.contains(just_before)

    def test_last_n_days_creates_recent_period(self):
        """last_n_days returns TimePeriod for last N days."""
        period = TimePeriod.last_n_days(30)

        assert period.days == 30
        now = datetime.now(UTC)
        # Start should be roughly 30 days ago (within 1 second)
        assert (now - period.start).days == 30 or (now - period.start).days == 29
        # End should be now (within a few seconds)
        assert (now - period.end).total_seconds() < 5

    def test_last_n_days_1_day(self):
        """last_n_days(1) creates 1-day period."""
        period = TimePeriod.last_n_days(1)
        assert period.days == 1

    def test_last_n_days_90_days(self):
        """last_n_days(90) creates 90-day period."""
        period = TimePeriod.last_n_days(90)
        assert period.days == 90

    def test_last_n_days_180_days(self):
        """last_n_days(180) creates 180-day period."""
        period = TimePeriod.last_n_days(180)
        assert period.days == 180

    def test_rolling_windows_returns_three_periods(self):
        """rolling_windows returns list of 3 TimePeriods."""
        windows = TimePeriod.rolling_windows()

        assert len(windows) == 3

    def test_rolling_windows_30_90_180_days(self):
        """rolling_windows returns 30, 90, and 180-day windows."""
        windows = TimePeriod.rolling_windows()

        assert windows[0].days == 30
        assert windows[1].days == 90
        assert windows[2].days == 180

    def test_rolling_windows_ordered_short_to_long(self):
        """rolling_windows returns windows ordered from shortest to longest."""
        windows = TimePeriod.rolling_windows()

        for i in range(len(windows) - 1):
            assert windows[i].days < windows[i + 1].days

    def test_rolling_windows_all_contain_now(self):
        """rolling_windows returns periods that all contain current time."""
        now = datetime.now(UTC)
        windows = TimePeriod.rolling_windows()

        for window in windows:
            # Check that now is within a few seconds of the window
            assert window.end >= now or (now - window.end).total_seconds() < 2

    def test_rolling_windows_nested(self):
        """rolling_windows shorter windows are subsets of longer windows."""
        windows = TimePeriod.rolling_windows()

        # The 30-day window start should be after the 90-day window start
        assert windows[0].start > windows[1].start
        # The 90-day window start should be after the 180-day window start
        assert windows[1].start > windows[2].start

    def test_time_period_is_frozen(self):
        """TimePeriod instance is immutable."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 31, tzinfo=UTC)
        period = TimePeriod(start=start, end=end)

        with pytest.raises(AttributeError):
            period.start = datetime(2024, 2, 1, tzinfo=UTC)


# ============================================================================
# Integration Tests (Value Objects)
# ============================================================================


class TestValueObjectIntegration:
    """Integration tests between value objects."""

    def test_risk_score_severity_matches_quality_dimensions(self):
        """RiskScore severity mapping is consistent for all values."""
        severity_ranges = [
            (0.0, 1.9, "minimal"),
            (2.0, 3.9, "low"),
            (4.0, 5.9, "medium"),
            (6.0, 7.9, "high"),
            (8.0, 10.0, "critical"),
        ]

        for low, high, expected_severity in severity_ranges:
            for value in [low, (low + high) / 2, high]:
                score = RiskScore(value=value)
                assert score.severity == expected_severity, \
                    f"Severity mismatch for value {value}"

    def test_time_period_contains_with_multiple_datetimes(self):
        """TimePeriod.contains works correctly with various datetime formats."""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)
        period = TimePeriod(start=start, end=end)

        test_cases = [
            (datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC), True),
            (datetime(2023, 12, 31, 23, 59, 59, tzinfo=UTC), False),
            (datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC), False),
            (datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC), True),
        ]

        for dt, expected in test_cases:
            assert period.contains(dt) == expected
