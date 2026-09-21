export default function Leaderboard({ items }) {
  return (
    <ol id="leaderboard-list">
      {items.map((item) => (
        <li key={item.id}>
          {item.player_name} — {item.score}
        </li>
      ))}
    </ol>
  );
}
