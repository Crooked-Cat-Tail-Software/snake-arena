"""Game metrics (backend/app/game_metrics.py): counted on the real
endpoints, read back through an in-memory OpenTelemetry reader."""
import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.game_metrics import GameMetrics


@pytest.fixture()
def game_metrics(client):
    """Swaps the app's metrics for an in-memory recorder for one test."""
    reader = InMemoryMetricReader()
    app = client.app
    original = app.state.game_metrics
    app.state.game_metrics = GameMetrics(
        MeterProvider(metric_readers=[reader]).get_meter("test")
    )
    yield reader
    app.state.game_metrics = original


def _points(reader: InMemoryMetricReader) -> dict:
    """{metric name: [data points]} from everything recorded so far."""
    data = reader.get_metrics_data()
    if data is None:
        return {}
    return {
        metric.name: list(metric.data.data_points)
        for resource_metrics in data.resource_metrics
        for scope_metrics in resource_metrics.scope_metrics
        for metric in scope_metrics.metrics
    }


def _total(reader: InMemoryMetricReader, name: str) -> int:
    return sum(point.value for point in _points(reader).get(name, []))


def _submit(client, name: str, score: int):
    return client.post("/api/scores", json={"player_name": name, "score": score})


def test_accepted_score_counted_and_recorded(client, game_metrics):
    assert _submit(client, "ada", 12).status_code == 201

    assert _total(game_metrics, "scores.submitted") == 1
    [histogram] = _points(game_metrics)["scores.value"]
    assert (histogram.count, histogram.sum) == (1, 12)


def test_new_top_score_only_when_beating_every_earlier_score(client, game_metrics):
    _submit(client, "ada", 10)  # first score ever -> #1
    _submit(client, "bob", 5)  # lower -> no
    _submit(client, "cy", 10)  # tie -> no (earlier submission keeps #1)
    _submit(client, "dee", 11)  # higher -> #1

    assert _total(game_metrics, "leaderboard.new_top_score") == 2
    assert _total(game_metrics, "scores.submitted") == 4


@pytest.mark.parametrize(
    "body, reason",
    [
        ({"player_name": "", "score": 5}, "player_name"),
        ({"player_name": "ada", "score": -1}, "score"),
        ({"player_name": "ada"}, "score"),
        ("not json", "malformed"),
    ],
)
def test_rejected_score_counted_by_reason(client, game_metrics, body, reason):
    if isinstance(body, str):
        response = client.post(
            "/api/scores", content=body, headers={"content-type": "application/json"}
        )
    else:
        response = client.post("/api/scores", json=body)

    assert response.status_code == 422
    # Unchanged contract: still FastAPI's standard {"detail": [...]} body.
    assert isinstance(response.json()["detail"], list)
    [point] = _points(game_metrics)["scores.rejected"]
    assert (point.value, dict(point.attributes)) == (1, {"reason": reason})
    assert _total(game_metrics, "scores.submitted") == 0


def test_leaderboard_reads_counted(client, game_metrics):
    client.get("/api/scores")
    client.get("/api/scores?limit=5")

    assert _total(game_metrics, "leaderboard.reads") == 2


def test_bad_leaderboard_query_is_not_a_rejected_score(client, game_metrics):
    assert client.get("/api/scores?limit=0").status_code == 422

    assert "scores.rejected" not in _points(game_metrics)
