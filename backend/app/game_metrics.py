"""Game metrics: what players do, as OpenTelemetry metrics.

Exported alongside traces (see telemetry.py); on AWS they land in
CloudWatch under the SnakeArena namespace, one series per environment.

Labels are deliberately low-cardinality -- CloudWatch bills each distinct
label combination as its own metric. Never label by player name.
"""
from opentelemetry.metrics import Meter

# Bounded set of rejection reasons for scores.rejected.
REJECTION_REASONS = ("player_name", "score")


class GameMetrics:
    def __init__(self, meter: Meter) -> None:
        self._submitted = meter.create_counter(
            "scores.submitted",
            unit="{score}",
            description="Scores accepted -- roughly, games finished.",
        )
        self._value = meter.create_histogram(
            "scores.value",
            unit="{point}",
            # Exported as an exponential histogram (see telemetry.py), so
            # CloudWatch can report percentiles such as the median score.
            description="Distribution of accepted scores.",
        )
        self._rejected = meter.create_counter(
            "scores.rejected",
            unit="{score}",
            description="Score submissions rejected by validation, by reason.",
        )
        self._leaderboard_reads = meter.create_counter(
            "leaderboard.reads",
            unit="{read}",
            description="Leaderboard requests.",
        )
        self._new_top_score = meter.create_counter(
            "leaderboard.new_top_score",
            unit="{score}",
            description="Accepted scores that beat every earlier score (took #1).",
        )

    def record_submission(self, score: int, is_new_top: bool) -> None:
        self._submitted.add(1)
        self._value.record(score)
        if is_new_top:
            self._new_top_score.add(1)

    def record_rejection(self, reason: str) -> None:
        if reason not in REJECTION_REASONS:
            reason = "malformed"
        self._rejected.add(1, {"reason": reason})

    def record_leaderboard_read(self) -> None:
        self._leaderboard_reads.add(1)
