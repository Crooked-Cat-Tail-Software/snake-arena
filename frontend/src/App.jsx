import { useCallback, useEffect, useRef, useState } from "react";
import { SnakeGame } from "./game.js";
import { fetchLeaderboard, submitScore } from "./api.js";
import StartScreen from "./components/StartScreen.jsx";
import GameOverScreen from "./components/GameOverScreen.jsx";
import Leaderboard from "./components/Leaderboard.jsx";

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

export default function App() {
  const [screen, setScreen] = useState("start"); // "start" | "playing" | "gameover"
  const [playerName, setPlayerName] = useState("");
  const [currentScore, setCurrentScore] = useState(0);
  const [finalScore, setFinalScore] = useState(0);
  const [submitStatus, setSubmitStatus] = useState({ text: "", kind: "" });
  const [leaderboard, setLeaderboard] = useState([]);
  const [leaderboardStatus, setLeaderboardStatus] = useState("");

  const canvasRef = useRef(null);
  const gameRef = useRef(null);
  // The name to submit on game over. A ref (not state) because the game's
  // onGameOver callback is created once per game and must see the name as
  // it was when the game started, without needing to be recreated.
  const playerNameRef = useRef("");

  const loadLeaderboard = useCallback(async () => {
    setLeaderboardStatus("Loading…");
    try {
      const scores = await fetchLeaderboard(10);
      setLeaderboard(scores);
      setLeaderboardStatus(scores.length === 0 ? "No scores yet — be the first!" : "");
    } catch (err) {
      setLeaderboardStatus(`Couldn't load leaderboard: ${err.message}`);
    }
  }, []);

  useEffect(() => {
    loadLeaderboard();
  }, [loadLeaderboard]);

  // WASD/arrow keys steer the snake -- but never while typing in a form
  // field. This guard is a regression fix for a real bug found during
  // manual review (see docs/ai-usage-report.md): without it, a name
  // containing "w", "a", "s" or "d" could never be fully typed, because
  // this handler would intercept those keystrokes for movement instead of
  // letting them reach the input.
  useEffect(() => {
    function handleKeyDown(e) {
      const targetTag = e.target.tagName;
      if (targetTag === "INPUT" || targetTag === "TEXTAREA" || e.target.isContentEditable) {
        return;
      }
      const dir = KEY_DIRECTIONS[e.key];
      if (!dir) return;
      e.preventDefault();
      gameRef.current?.setDirection(dir[0], dir[1]);
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  const trySubmit = useCallback(
    async (score) => {
      setSubmitStatus({ text: "Saving your score…", kind: "" });
      try {
        await submitScore(playerNameRef.current, score);
        setSubmitStatus({ text: "Score saved.", kind: "ok" });
        await loadLeaderboard();
      } catch (err) {
        setSubmitStatus({ text: `Couldn't save your score: ${err.message}`, kind: "error" });
      }
    },
    [loadLeaderboard]
  );

  // Create and start a game whenever the canvas is mounted (i.e. whenever
  // we enter the "playing" screen), and make sure to stop it -- clearing
  // its interval timer -- on the way out, whether that's a normal game
  // over or the component unmounting.
  useEffect(() => {
    if (screen !== "playing" || !canvasRef.current) return undefined;

    const game = new SnakeGame(canvasRef.current, {
      onScoreChange: setCurrentScore,
      onGameOver: (score) => {
        setFinalScore(score);
        setScreen("gameover");
        trySubmit(score);
      },
    });
    gameRef.current = game;
    game.start();

    return () => {
      game.stop();
      gameRef.current = null;
    };
  }, [screen, trySubmit]);

  function handleStart() {
    const name = playerName.trim();
    if (!name) return;
    playerNameRef.current = name;
    setCurrentScore(0);
    setSubmitStatus({ text: "", kind: "" });
    setScreen("playing");
  }

  function handlePlayAgain() {
    setScreen("start");
  }

  return (
    <div className="app">
      <h1>Snake Arena</h1>

      <div className="layout">
        <div className="game-column">
          {screen === "start" && (
            <StartScreen
              playerName={playerName}
              onPlayerNameChange={setPlayerName}
              onStart={handleStart}
            />
          )}

          {screen === "playing" && (
            <>
              <div id="hud" className="hud">
                <span>
                  Score: <strong id="current-score">{currentScore}</strong>
                </span>
              </div>
              <canvas id="game-canvas" ref={canvasRef} width={400} height={400} tabIndex={0} />
            </>
          )}

          {screen === "gameover" && (
            <GameOverScreen
              finalScore={finalScore}
              submitStatus={submitStatus}
              onRetry={() => trySubmit(finalScore)}
              onPlayAgain={handlePlayAgain}
            />
          )}
        </div>

        <div className="leaderboard-column panel">
          <h2>Leaderboard</h2>
          <Leaderboard items={leaderboard} />
          <p id="leaderboard-status" className="status">
            {leaderboardStatus}
          </p>
        </div>
      </div>
    </div>
  );
}
