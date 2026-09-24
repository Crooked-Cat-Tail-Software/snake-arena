"""Core integration scenarios against the real docker-compose stack.

See conftest.py's module docstring for requirements and the important
warning about the Postgres volume being wiped before and after this runs.

Four scenarios -- the ones only a real `docker compose up` can actually
prove, as opposed to reproducing the Dockerfile/compose file's steps by
hand (which is how every earlier verification in docs/ai-usage-report.md
was done, since Docker wasn't available in that environment):

1. The image(s) actually build.
2. The backend only starts once Postgres reports healthy, and its health
   endpoint is reachable once everything's up.
3. The backend can actually talk to Postgres over the compose network
   (not just some other, previously-verified database).
4. The backend serves the real, built frontend, and a full game -- played
   through a real browser against the container -- works end to end.
"""
import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration


def test_build_succeeds(docker_build):
    assert docker_build.returncode == 0, (
        "docker compose build failed:\n"
        f"--- stdout ---\n{docker_build.stdout}\n"
        f"--- stderr ---\n{docker_build.stderr}"
    )


def test_health_check_becomes_available(compose_up):
    # The compose_up fixture already waited for this to come up (and would
    # have failed the whole session, with logs, if it never did) -- this
    # test asserts on it directly so a health-check regression shows up as
    # its own named failure, not just "some fixture broke".
    response = httpx.get(f"{compose_up}/api/health", timeout=5)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_score_round_trips_through_postgres(compose_up):
    """Submits a score through the real backend container and reads it
    back from the leaderboard -- proving the backend can actually reach
    Postgres over the compose network (DNS resolution of the `db`
    hostname, the DATABASE_URL wiring, psycopg2 installed correctly in
    the built image), not a database this project already knows works.
    """
    player_name = f"Integration-{uuid.uuid4().hex[:8]}"
    submit = httpx.post(
        f"{compose_up}/api/scores",
        json={"player_name": player_name, "score": 7},
        timeout=5,
    )
    assert submit.status_code == 201
    assert submit.json()["player_name"] == player_name

    leaderboard = httpx.get(f"{compose_up}/api/scores", timeout=5)
    assert leaderboard.status_code == 200
    names = [row["player_name"] for row in leaderboard.json()]
    assert player_name in names


def test_frontend_is_served_and_playable(compose_up, page):
    """Loads the app from the container (not a dev server) in a real
    browser and plays a full game, the same way tests/frontend/
    test_frontend.py does -- but here the frontend is the actual built
    artifact the Dockerfile produces, served by the actual backend
    container, talking to the actual Postgres container.
    """
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto(f"{compose_up}/")
    page.wait_for_selector("#player-name")

    player_name = f"Integration-{uuid.uuid4().hex[:6]}"
    page.fill("#player-name", player_name)
    page.click("#start-button")
    assert page.is_visible("#game-canvas")

    page.keyboard.press("ArrowDown")
    page.wait_for_selector("#game-over-screen:not(.hidden)", timeout=10000)

    status = page.locator("#submit-status").inner_text()
    assert "Score saved" in status, f"unexpected submit status: {status}"

    leaderboard_items = page.locator("#leaderboard-list li").all_inner_texts()
    assert any(player_name in item for item in leaderboard_items), (
        f"expected {player_name!r} on the leaderboard, got {leaderboard_items}"
    )

    real_errors = [e for e in errors if "favicon" not in e.lower()]
    assert not real_errors, f"console errors: {real_errors}"
