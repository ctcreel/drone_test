"""Tests for logging context management."""

from src.logging.context import (
    clear_context,
    generate_correlation_id,
    get_correlation_id,
    get_extra_context,
    set_correlation_id,
    set_extra_context,
)


class TestCorrelationId:
    def test_default_empty(self):
        clear_context()
        assert get_correlation_id() == ""

    def test_set_and_get(self):
        set_correlation_id("test-123")
        assert get_correlation_id() == "test-123"
        clear_context()

    def test_generate_creates_uuid(self):
        result = generate_correlation_id()
        assert len(result) > 0
        assert get_correlation_id() == result
        clear_context()


class TestExtraContext:
    def test_default_empty(self):
        clear_context()
        assert get_extra_context() == {}

    def test_set_and_get(self):
        clear_context()
        set_extra_context(mission_id="m-123")
        context = get_extra_context()
        assert context["mission_id"] == "m-123"
        clear_context()

    def test_multiple_values(self):
        clear_context()
        set_extra_context(mission_id="m-123", drone_id="d-001")
        context = get_extra_context()
        assert context["mission_id"] == "m-123"
        assert context["drone_id"] == "d-001"
        clear_context()

    def test_returns_copy(self):
        clear_context()
        set_extra_context(key="value")
        first = get_extra_context()
        second = get_extra_context()
        assert first == second
        assert first is not second
        clear_context()


class TestClearContext:
    def test_clears_correlation_id(self):
        set_correlation_id("test")
        clear_context()
        assert get_correlation_id() == ""

    def test_clears_extra_context(self):
        set_extra_context(key="value")
        clear_context()
        assert get_extra_context() == {}
