import pytest

from app.runner.postgres import PostgresQueue


@pytest.mark.parametrize(
    ("attempt", "sample", "expected"),
    [
        (1, 0.0, 24),
        (1, 0.5, 30),
        (1, 1.0, 42),
        (2, 0.5, 60),
        (3, 0.5, 120),
        (4, 0.5, 240),
        (8, 1.0, 3600),
        (100, 0.0, 2880),
    ],
)
def test_retry_delay_uses_exponential_backoff_with_bounded_jitter(
    attempt, sample, expected
):
    assert PostgresQueue.retry_delay_for_attempt(
        attempt, jitter_sample=sample
    ) == expected


def test_retry_delay_rejects_invalid_attempt_or_random_sample():
    with pytest.raises(ValueError, match="attempt_no"):
        PostgresQueue.retry_delay_for_attempt(0, jitter_sample=0.5)
    with pytest.raises(ValueError, match="jitter_sample"):
        PostgresQueue.retry_delay_for_attempt(1, jitter_sample=1.1)
