def test_submit_score_success(client):
    response = client.post("/api/scores", json={"player_name": "Donna", "score": 17})
    assert response.status_code == 201
    body = response.json()
    assert body["player_name"] == "Donna"
    assert body["score"] == 17
    assert "id" in body
    assert body["created_at"].endswith("Z")


def test_submit_score_rejects_blank_name(client):
    response = client.post("/api/scores", json={"player_name": "   ", "score": 5})
    assert response.status_code == 422


def test_submit_score_rejects_negative_score(client):
    response = client.post("/api/scores", json={"player_name": "Donna", "score": -1})
    assert response.status_code == 422


def test_submit_score_rejects_name_too_long(client):
    response = client.post("/api/scores", json={"player_name": "x" * 21, "score": 1})
    assert response.status_code == 422


def test_leaderboard_orders_by_score_desc(client):
    client.post("/api/scores", json={"player_name": "Low", "score": 3})
    client.post("/api/scores", json={"player_name": "High", "score": 42})
    client.post("/api/scores", json={"player_name": "Mid", "score": 10})

    response = client.get("/api/scores")
    assert response.status_code == 200
    names_in_order = [row["player_name"] for row in response.json()]
    assert names_in_order == ["High", "Mid", "Low"]


def test_leaderboard_respects_limit(client):
    for i in range(5):
        client.post("/api/scores", json={"player_name": f"P{i}", "score": i})

    response = client.get("/api/scores?limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_leaderboard_limit_out_of_range_rejected(client):
    assert client.get("/api/scores?limit=0").status_code == 422
    assert client.get("/api/scores?limit=101").status_code == 422


def test_leaderboard_empty_by_default(client):
    response = client.get("/api/scores")
    assert response.status_code == 200
    assert response.json() == []
