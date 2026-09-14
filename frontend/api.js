// Thin client for the Snake Arena API. Every call here corresponds to an
// operation in /openapi.yaml at the repo root — keep them in sync.
import { API_BASE_URL } from "./config.js";

export async function fetchLeaderboard(limit = 10) {
  const res = await fetch(`${API_BASE_URL}/api/scores?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Failed to load leaderboard (HTTP ${res.status})`);
  }
  return res.json();
}

export async function submitScore(playerName, score) {
  const res = await fetch(`${API_BASE_URL}/api/scores`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_name: playerName, score }),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && body.detail) detail = JSON.stringify(body.detail);
    } catch (_) {
      // response wasn't JSON; keep the generic detail
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`);
    return res.ok;
  } catch (_) {
    return false;
  }
}
