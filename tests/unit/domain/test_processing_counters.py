"""Test ProcessingCounters invariants and coherence."""

import dataclasses

import pytest
from src.domain.value_objects import ProcessingCounters


class TestProcessingCounters:
    """Test ProcessingCounters with sum coherence and invariants."""

    def test_sum_errors_warnings_not_exceed_processed(self):
        """ProcessingCounters should reject when errors + warnings > processed."""
        with pytest.raises(ValueError):
            ProcessingCounters(total=10, processed=5, errors=3, warnings=3)  # 6 > 5

        with pytest.raises(ValueError):
            ProcessingCounters(total=100, processed=50, errors=30, warnings=21)  # 51 > 50

        with pytest.raises(ValueError):
            ProcessingCounters(total=10, processed=10, errors=6, warnings=5)  # 11 > 10

    def test_processed_not_exceed_total(self):
        """ProcessingCounters should reject when processed > total."""
        with pytest.raises(ValueError):
            ProcessingCounters(total=10, processed=11, errors=0, warnings=0)

        with pytest.raises(ValueError):
            ProcessingCounters(total=100, processed=101, errors=0, warnings=0)

    def test_accepts_valid_counters(self):
        """ProcessingCounters should accept valid counter combinations."""
        # All zeros
        counters = ProcessingCounters(total=0, processed=0, errors=0, warnings=0)
        assert counters.total == 0
        assert counters.processed == 0
        assert counters.errors == 0
        assert counters.warnings == 0

        # Normal case
        counters = ProcessingCounters(total=100, processed=100, errors=5, warnings=10)
        assert counters.total == 100
        assert counters.processed == 100
        assert counters.errors == 5
        assert counters.warnings == 10

        # Partial processing
        counters = ProcessingCounters(total=100, processed=50, errors=5, warnings=10)
        assert counters.total == 100
        assert counters.processed == 50

        # Errors + warnings = processed (edge case)
        counters = ProcessingCounters(total=10, processed=10, errors=5, warnings=5)
        assert counters.errors + counters.warnings == counters.processed

    def test_rejects_negative_values(self):
        """ProcessingCounters should reject negative values."""
        with pytest.raises(ValueError):
            ProcessingCounters(total=-1, processed=0, errors=0, warnings=0)

        with pytest.raises(ValueError):
            ProcessingCounters(total=10, processed=-1, errors=0, warnings=0)

        with pytest.raises(ValueError):
            ProcessingCounters(total=10, processed=10, errors=-1, warnings=0)

        with pytest.raises(ValueError):
            ProcessingCounters(total=10, processed=10, errors=0, warnings=-1)

    def test_success_count_calculation(self):
        """ProcessingCounters should calculate success count correctly."""
        counters = ProcessingCounters(total=100, processed=100, errors=5, warnings=10)
        # Success = processed - errors - warnings
        assert counters.get_success_count() == 85  # 100 - 5 - 10

        counters = ProcessingCounters(total=50, processed=40, errors=3, warnings=7)
        assert counters.get_success_count() == 30  # 40 - 3 - 7

        counters = ProcessingCounters(total=10, processed=10, errors=10, warnings=0)
        assert counters.get_success_count() == 0  # All errors

    def test_success_rate_calculation(self):
        """ProcessingCounters should calculate success rate correctly."""
        counters = ProcessingCounters(total=100, processed=100, errors=5, warnings=10)
        assert counters.get_success_rate() == 0.85  # 85/100

        counters = ProcessingCounters(total=100, processed=50, errors=5, warnings=5)
        # Success rate based on processed, not total
        assert counters.get_success_rate() == 0.80  # 40/50

        # Edge case: no processing
        counters = ProcessingCounters(total=100, processed=0, errors=0, warnings=0)
        assert counters.get_success_rate() == 0.0  # or 1.0 depending on business logic

    def test_error_rate_calculation(self):
        """ProcessingCounters should calculate error rate correctly."""
        counters = ProcessingCounters(total=100, processed=100, errors=10, warnings=0)
        assert counters.get_error_rate() == 0.10  # 10/100

        counters = ProcessingCounters(total=100, processed=50, errors=5, warnings=0)
        assert counters.get_error_rate() == 0.10  # 5/50

        counters = ProcessingCounters(total=100, processed=100, errors=0, warnings=0)
        assert counters.get_error_rate() == 0.0

    def test_warning_rate_calculation(self):
        """ProcessingCounters should calculate warning rate correctly."""
        counters = ProcessingCounters(total=100, processed=100, errors=0, warnings=15)
        assert counters.get_warning_rate() == 0.15  # 15/100

        counters = ProcessingCounters(total=100, processed=50, errors=0, warnings=10)
        assert counters.get_warning_rate() == 0.20  # 10/50

    def test_is_complete_check(self):
        """ProcessingCounters should check if processing is complete."""
        counters = ProcessingCounters(total=100, processed=100, errors=5, warnings=10)
        assert counters.is_complete() is True

        counters = ProcessingCounters(total=100, processed=99, errors=5, warnings=10)
        assert counters.is_complete() is False

        counters = ProcessingCounters(total=0, processed=0, errors=0, warnings=0)
        assert counters.is_complete() is True  # Empty is complete

    def test_has_errors_check(self):
        """ProcessingCounters should check if there are any errors."""
        counters = ProcessingCounters(total=100, processed=100, errors=1, warnings=0)
        assert counters.has_errors() is True

        counters = ProcessingCounters(total=100, processed=100, errors=0, warnings=10)
        assert counters.has_errors() is False

    def test_has_warnings_check(self):
        """ProcessingCounters should check if there are any warnings."""
        counters = ProcessingCounters(total=100, processed=100, errors=0, warnings=1)
        assert counters.has_warnings() is True

        counters = ProcessingCounters(total=100, processed=100, errors=10, warnings=0)
        assert counters.has_warnings() is False

    def test_is_perfect_check(self):
        """ProcessingCounters should check if processing was perfect (no issues)."""
        counters = ProcessingCounters(total=100, processed=100, errors=0, warnings=0)
        assert counters.is_perfect() is True

        counters = ProcessingCounters(total=100, processed=100, errors=1, warnings=0)
        assert counters.is_perfect() is False

        counters = ProcessingCounters(total=100, processed=100, errors=0, warnings=1)
        assert counters.is_perfect() is False

        # Not complete = not perfect
        counters = ProcessingCounters(total=100, processed=99, errors=0, warnings=0)
        assert counters.is_perfect() is False

    def test_counters_immutability(self):
        """ProcessingCounters should be immutable."""
        counters = ProcessingCounters(total=100, processed=100, errors=5, warnings=10)

        with pytest.raises(dataclasses.FrozenInstanceError):
            counters.total = 200

        with pytest.raises(dataclasses.FrozenInstanceError):
            counters.processed = 50

        with pytest.raises(dataclasses.FrozenInstanceError):
            counters.errors = 10

        with pytest.raises(dataclasses.FrozenInstanceError):
            counters.warnings = 20

    def test_counters_equality(self):
        """ProcessingCounters should be equal if all values match."""
        c1 = ProcessingCounters(total=100, processed=100, errors=5, warnings=10)
        c2 = ProcessingCounters(total=100, processed=100, errors=5, warnings=10)
        c3 = ProcessingCounters(total=100, processed=100, errors=5, warnings=11)

        assert c1 == c2
        assert c1 != c3

    def test_counters_string_representation(self):
        """ProcessingCounters should have meaningful string representation."""
        counters = ProcessingCounters(total=100, processed=100, errors=5, warnings=10)
        str_repr = str(counters)

        assert "100" in str_repr  # total
        assert "5" in str_repr  # errors
        assert "10" in str_repr  # warnings
