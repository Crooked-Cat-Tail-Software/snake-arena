"""Browser-driven tests for the frontend, run against a real backend +
frontend (see conftest.py) with an actual (headless) browser via
Playwright. These exercise things the backend's API tests can't: DOM
behavior, keyboard handling, and screen transitions.

Two of these are direct regression tests for real bugs found during
manual review — see docs/ai-usage-report.md for the full story.
"""
import uuid


def test_name_field_accepts_movement_key_letters(game_page):
    """Regression test: the game's keyboard handler used to intercept
    W/A/S/D globally, even while typing in this field, so a name like
    "Donna" (which contains a lowercase "a") could never be fully typed.
    """
    name_input = game_page.locator("#player-name")
    name_input.click()
    for ch in "wasd":
        game_page.keyboard.press(ch)
    assert name_input.input_value() == "wasd"


def test_name_input_has_enough_room_to_type_in(game_page):
    """Regression test: the name field's containing panel used to have no
    width of its own, so some browsers rendered the box far too narrow to
    see what you'd typed, even though the value itself was fine.
    """
    box = game_page.locator("#player-name").bounding_box()
    assert box["width"] >= 250, f"name input is only {box['width']}px wide"


def test_empty_name_does_not_start_game(game_page):
    game_page.click("#start-button")
    assert game_page.is_visible("#start-screen")
    assert game_page.is_hidden("#game-canvas")


def test_start_screen_transitions_to_game(game_page):
    game_page.fill("#player-name", "StartTest")
    game_page.click("#start-button")
    assert game_page.is_hidden("#start-screen")
    assert game_page.is_visible("#game-canvas")


def test_full_game_submits_score_and_appears_on_leaderboard(game_page):
    player_name = f"E2E-{uuid.uuid4().hex[:8]}"
    game_page.fill("#player-name", player_name)
    game_page.click("#start-button")
    assert game_page.is_visible("#game-canvas")

    # Drive straight into a wall to end the game deterministically,
    # regardless of where the random food happens to spawn.
    game_page.keyboard.press("ArrowDown")
    game_page.wait_for_selector("#game-over-screen:not(.hidden)", timeout=10000)

    status_text = game_page.locator("#submit-status").inner_text()
    assert "Score saved" in status_text, f"unexpected submit status: {status_text}"

    leaderboard_items = game_page.locator("#leaderboard-list li").all_inner_texts()
    assert any(player_name in item for item in leaderboard_items), (
        f"expected {player_name!r} on the leaderboard, got {leaderboard_items}"
    )


def test_play_again_returns_to_start_screen(game_page):
    game_page.fill("#player-name", f"Replay-{uuid.uuid4().hex[:6]}")
    game_page.click("#start-button")
    game_page.keyboard.press("ArrowDown")
    game_page.wait_for_selector("#game-over-screen:not(.hidden)", timeout=10000)

    game_page.click("#play-again-button")
    assert game_page.is_visible("#start-screen")
    assert game_page.is_hidden("#game-over-screen")
