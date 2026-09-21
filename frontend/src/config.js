// Where the backend is running. Empty string means "same origin as this
// page" (used when the backend serves this frontend itself, e.g. in
// Docker). Override at build time with VITE_API_BASE_URL -- see
// .env.example -- rather than editing this file.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
