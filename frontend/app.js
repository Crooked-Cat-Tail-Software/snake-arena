import { SnakeGame } from "./game.js";
import { fetchLeaderboard, submitScore } from "./api.js";

const startScreen = document.getElementById("start-screen");
const gameOverScreen = document.getElementById("game-over-screen");
const canvas = document.getElementById("game-canvas");
const hud = document.getElementById("hud");
const currentScoreEl = document.getElementById("current-score");
const finalScoreEl = document.getElementById("final-score");
const submitStatusEl = document.getElementById("submit-status");
const nameInput = document.getElementById("player-name");
const startButton = document.getElementById("start-button");
const playAgainButton = document.getElementById("play-again-button");
const leaderboardList = document.getElementById("leaderboard-list");
const leaderboardStatus = document.getElementById("leaderboard-status");

let playerName = "";

const game = new SnakeGame(canvas, {
  onScoreChange: (score) => {
    currentScoreEl.textContent = String(score);
  },
  onGameOver: (score) => {
    handleGameOver(score);
  },
});

function show(el) {
  el.classList.remove("hidden");
}
function hide(el) {
  el.classList.add("hidden");
}

function startGame() {
  const name = nameInput.value.trim();
  if (!name) {
    nameInput.focus();
    return;
  }
  playerName = name;

  hide(startScreen);
  hide(gameOverScreen);
  show(hud);
  show(canvas);

  game.start();
  canvas.focus();
}

async function handleGameOver(score) {
  hide(hud);
  hide(canvas);
  finalScoreEl.textContent = String(score);
  document.querySelectorAll(".retry-button").forEach((el) => el.remove());
  show(gameOverScreen);
  await trySubmit(score);
}

async function trySubmit(score) {
  submitStatusEl.textContent = "Saving your score…";
  submitStatusEl.className = "status";
  try {
    await submitScore(playerName, score);
    submitStatusEl.textContent = "Score saved.";
    submitStatusEl.className = "status status-ok";
    await loadLeaderboard();
  } catch (err) {
    submitStatusEl.textContent = `Couldn't save your score: ${err.message}`;
    submitStatusEl.className = "status status-error";
    addRetryButton(score);
  }
}

function addRetryButton(score) {
  const retryButton = document.createElement("button");
  retryButton.textContent = "Retry save";
  retryButton.className = "retry-button";
  retryButton.addEventListener("click", () => {
    retryButton.remove();
    trySubmit(score);
  });
  submitStatusEl.after(retryButton);
}

async function loadLeaderboard() {
  leaderboardStatus.textContent = "Loading…";
  try {
    const scores = await fetchLeaderboard(10);
    leaderboardList.innerHTML = "";
    if (scores.length === 0) {
      leaderboardStatus.textContent = "No scores yet — be the first!";
    } else {
      leaderboardStatus.textContent = "";
      scores.forEach((row) => {
        const li = document.createElement("li");
        li.textContent = `${row.player_name} — ${row.score}`;
        leaderboardList.appendChild(li);
      });
    }
  } catch (err) {
    leaderboardStatus.textContent = `Couldn't load leaderboard: ${err.message}`;
  }
}

const KEY_DIRECTIONS = {
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
  w: [0, -1],
  s: [0, 1],
  a: [-1, 0],
  d: [1, 0],
};

document.addEventListener("keydown", (e) => {
  // Don't hijack WASD/arrow keys while the user is typing into a form
  // field (e.g. their name) -- only steer the snake when the game itself
  // has focus/is the intended target.
  const targetTag = e.target.tagName;
  if (targetTag === "INPUT" || targetTag === "TEXTAREA" || e.target.isContentEditable) {
    return;
  }

  const dir = KEY_DIRECTIONS[e.key];
  if (!dir) return;
  e.preventDefault();
  game.setDirection(dir[0], dir[1]);
});

startButton.addEventListener("click", startGame);
nameInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") startGame();
});
playAgainButton.addEventListener("click", () => {
  show(startScreen);
  hide(gameOverScreen);
  nameInput.focus();
});

loadLeaderboard();
