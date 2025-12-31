// API Client for RTL-SDR Radio
export const API_BASE = import.meta.env.VITE_API_URL || "/api"

// Special ID for browser playback
export const BROWSER_SPEAKER_ID = "browser:local"

// Helper to wait for stream to be ready with backoff
export async function waitForStreamReady(maxAttempts = 10, baseDelay = 200) {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const res = await fetch(`${API_BASE}/stream/ready`)
      const data = await res.json()
      if (data.ready) {
        return true
      }
    } catch (err) {
      console.debug("Stream ready check failed:", err)
    }
    // Exponential backoff
    const delay = baseDelay * Math.pow(1.5, attempt)
    await new Promise((resolve) => setTimeout(resolve, delay))
  }
  return false
}

// Generic fetch wrapper with error handling
async function apiFetch(endpoint, options = {}) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  })

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail) || `Request failed: ${res.status}`
    throw new Error(detail)
  }

  // Return null for 204 No Content
  if (res.status === 204) {
    return null
  }

  return res.json()
}

// Speakers API
export const speakersApi = {
  list: () => apiFetch("/speakers"),
  get: (id) => apiFetch(`/speakers/${id}`),
  setVolume: (id, volume) =>
    apiFetch(`/speakers/${id}/volume`, {
      method: "PUT",
      body: JSON.stringify({ volume }),
    }),
  power: (id, powerOn) =>
    apiFetch(`/speakers/${id}/power?power=${powerOn}`, {
      method: "POST",
    }),
}

// Stations API
export const stationsApi = {
  list: () => apiFetch("/stations"),
  get: (id) => apiFetch(`/stations/${id}`),
  create: (station) =>
    apiFetch("/stations", {
      method: "POST",
      body: JSON.stringify(station),
    }),
  update: (id, station) =>
    apiFetch(`/stations/${id}`, {
      method: "PUT",
      body: JSON.stringify(station),
    }),
  delete: (id) =>
    apiFetch(`/stations/${id}`, {
      method: "DELETE",
    }),
}

// Playback API
export const playbackApi = {
  status: () => apiFetch("/playback/status"),
  start: (body) =>
    apiFetch("/playback/start", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  stop: () =>
    apiFetch("/playback/stop", {
      method: "POST",
    }),
  pause: () =>
    apiFetch("/playback/pause", {
      method: "POST",
    }),
  resume: () =>
    apiFetch("/playback/resume", {
      method: "POST",
    }),
}

// Tuner API (FM)
export const tunerApi = {
  tune: (frequency, modulation = "wfm") =>
    apiFetch("/tuner/tune", {
      method: "POST",
      body: JSON.stringify({ frequency, modulation }),
    }),
  stop: () =>
    apiFetch("/tuner/stop", {
      method: "POST",
    }),
}

// DAB API
export const dabApi = {
  channels: () => apiFetch("/dab/channels"),
  programs: (channel) => apiFetch(`/dab/programs?channel=${channel}`),
  metadata: () => apiFetch("/dab/metadata"),
  tune: (channel, program, serviceId) =>
    apiFetch("/dab/tune", {
      method: "POST",
      body: JSON.stringify({
        channel,
        program,
        service_id: serviceId,
      }),
    }),
}

// Stream URL for browser playback
export function getStreamUrl() {
  return `${API_BASE}/stream`
}

// Get image URL (handles relative paths)
export function getImageUrl(url) {
  if (!url) return null
  if (url.startsWith("/")) {
    return `${API_BASE.replace("/api", "")}${url}`
  }
  return url
}
