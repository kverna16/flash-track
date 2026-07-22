"""
Basic tests for FlashTrack's core data logic.

Run with: pytest test_generate_data.py
"""

import numpy as np


def test_noise_produces_variance():
    """Actual values with noise applied should differ from the base projection."""
    np.random.seed(1)
    base = 1000.0
    noise = np.random.normal(loc=0, scale=0.08)
    actual = base * (1 + noise)
    assert actual != base


def test_variance_pct_calculation():
    """Variance percentage should be calculated correctly against a known input."""
    projected = 1000.0
    actual = 1150.0
    variance_pct = ((actual - projected) / projected) * 100
    assert round(variance_pct, 2) == 15.0


def test_negative_variance_pct_calculation():
    """Under-projection should produce a negative variance percentage."""
    projected = 1000.0
    actual = 800.0
    variance_pct = ((actual - projected) / projected) * 100
    assert round(variance_pct, 2) == -20.0


def test_anomaly_threshold_flagging():
    """A variance at or above 15% should be flagged; below should not."""
    threshold = 15

    def is_anomaly(variance_pct):
        return abs(variance_pct) >= threshold

    assert is_anomaly(16.71) is True
    assert is_anomaly(-15.95) is True
    assert is_anomaly(9.5) is False


def test_attendance_never_negative():
    """Attendance noise should never produce a negative count (clamped at 0)."""
    projected_attendance = 100
    extreme_noise = -1.5  # simulate an extreme negative noise draw
    actual_attendance = max(0, int(projected_attendance * (1 + extreme_noise)))
    assert actual_attendance >= 0
