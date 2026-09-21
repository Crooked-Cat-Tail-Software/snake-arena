export default function GameOverScreen({ finalScore, submitStatus, onRetry, onPlayAgain }) {
  const statusClass = submitStatus.kind ? `status status-${submitStatus.kind}` : "status";

  return (
    <div id="game-over-screen" className="panel">
      <h2>Game over</h2>
      <p>
        Final score: <strong id="final-score">{finalScore}</strong>
      </p>
      <p id="submit-status" className={statusClass}>
        {submitStatus.text}
      </p>
      {submitStatus.kind === "error" && (
        <button className="retry-button" onClick={onRetry}>
          Retry save
        </button>
      )}
      <button id="play-again-button" onClick={onPlayAgain}>
        Play again
      </button>
    </div>
  );
}
