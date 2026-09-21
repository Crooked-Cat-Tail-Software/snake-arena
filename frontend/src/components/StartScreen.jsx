export default function StartScreen({ playerName, onPlayerNameChange, onStart }) {
  function handleInputKeyDown(e) {
    if (e.key === "Enter") onStart();
  }

  return (
    <div id="start-screen" className="panel">
      <label htmlFor="player-name">Your name</label>
      <input
        id="player-name"
        maxLength={20}
        placeholder="e.g. Donna"
        autoComplete="off"
        value={playerName}
        onChange={(e) => onPlayerNameChange(e.target.value)}
        onKeyDown={handleInputKeyDown}
      />
      <button id="start-button" onClick={onStart}>
        Start game
      </button>
      <p className="hint">
        Arrow keys or WASD to move. Eat the red food, avoid walls and yourself.
      </p>
    </div>
  );
}
