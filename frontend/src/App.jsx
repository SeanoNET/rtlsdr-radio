import { useState, useEffect, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

export default function RadioApp() {
  const [speakers, setSpeakers] = useState([]);
  const [stations, setStations] = useState([]);
  const [selectedSpeaker, setSelectedSpeaker] = useState(null);
  const [selectedStation, setSelectedStation] = useState(null);
  const [playbackStatus, setPlaybackStatus] = useState(null);
  const [volume, setVolume] = useState(0.5);
  const [frequency, setFrequency] = useState(101.1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // New station form
  const [newStationName, setNewStationName] = useState("");
  const [newStationFreq, setNewStationFreq] = useState("");

  const fetchSpeakers = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/speakers`);
      const data = await res.json();
      setSpeakers(data);
    } catch (err) {
      setError("Failed to fetch speakers");
    }
  }, []);

  const fetchStations = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/stations`);
      const data = await res.json();
      setStations(data);
    } catch (err) {
      setError("Failed to fetch stations");
    }
  }, []);

  const fetchPlaybackStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/playback/status`);
      const data = await res.json();
      setPlaybackStatus(data);
    } catch (err) {
      console.error("Failed to fetch status");
    }
  }, []);

  useEffect(() => {
    fetchSpeakers();
    fetchStations();
    fetchPlaybackStatus();

    const interval = setInterval(fetchPlaybackStatus, 2000);
    return () => clearInterval(interval);
  }, [fetchSpeakers, fetchStations, fetchPlaybackStatus]);

  const handlePlay = async () => {
    if (!selectedSpeaker) {
      setError("Please select a speaker");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const body = {
        device_id: selectedSpeaker,
        ...(selectedStation
          ? { station_id: selectedStation }
          : { frequency: parseFloat(frequency), modulation: "wfm" }),
      };

      const res = await fetch(`${API_BASE}/playback/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to start playback");
      }

      await fetchPlaybackStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/playback/stop`, { method: "POST" });
      await fetchPlaybackStatus();
    } catch (err) {
      setError("Failed to stop playback");
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async () => {
    try {
      await fetch(`${API_BASE}/playback/pause`, { method: "POST" });
      await fetchPlaybackStatus();
    } catch (err) {
      setError("Failed to pause");
    }
  };

  const handleResume = async () => {
    try {
      await fetch(`${API_BASE}/playback/resume`, { method: "POST" });
      await fetchPlaybackStatus();
    } catch (err) {
      setError("Failed to resume");
    }
  };

  const handleVolumeChange = async (newVolume) => {
    setVolume(newVolume);
    if (selectedSpeaker) {
      try {
        await fetch(`${API_BASE}/speakers/${selectedSpeaker}/volume`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ volume: newVolume }),
        });
      } catch (err) {
        console.error("Failed to set volume");
      }
    }
  };

  const handleAddStation = async (e) => {
    e.preventDefault();
    if (!newStationName || !newStationFreq) return;

    try {
      const res = await fetch(`${API_BASE}/stations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newStationName,
          frequency: parseFloat(newStationFreq),
          modulation: "wfm",
        }),
      });

      if (res.ok) {
        setNewStationName("");
        setNewStationFreq("");
        await fetchStations();
      }
    } catch (err) {
      setError("Failed to add station");
    }
  };

  const handleDeleteStation = async (stationId) => {
    try {
      await fetch(`${API_BASE}/stations/${stationId}`, { method: "DELETE" });
      await fetchStations();
      if (selectedStation === stationId) {
        setSelectedStation(null);
      }
    } catch (err) {
      setError("Failed to delete station");
    }
  };

  const getSpeakerIcon = (type) => {
    return type === "chromecast" ? "📺" : "🔊";
  };

  const getSpeakerTypeLabel = (type) => {
    return type === "chromecast" ? "Chromecast" : "Squeezebox";
  };

  const isPlaying = playbackStatus?.state === "playing";
  const isPaused = playbackStatus?.state === "paused";

  // Group speakers by type
  const chromecastSpeakers = speakers.filter((s) => s.type === "chromecast");
  const lmsSpeakers = speakers.filter((s) => s.type === "lms");

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-4xl font-bold mb-2 text-center bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-400">
          📻 RTL-SDR Radio
        </h1>
        <p className="text-slate-400 text-center mb-8">
          Stream FM radio to Chromecast or Squeezebox
        </p>

        {error && (
          <div className="bg-red-500/20 border border-red-500 rounded-lg p-4 mb-6">
            <p className="text-red-300">{error}</p>
            <button
              onClick={() => setError(null)}
              className="text-red-400 text-sm underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Status Display */}
        {playbackStatus && (
          <div className="bg-white/5 backdrop-blur rounded-xl p-6 mb-6 border border-white/10">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Now Playing</p>
                <p className="text-2xl font-semibold">
                  {playbackStatus.frequency
                    ? `${playbackStatus.frequency} MHz`
                    : "Not tuned"}
                </p>
                {playbackStatus.device_name && (
                  <p className="text-sm text-purple-400">
                    {playbackStatus.device_type === "lms" ? "🔊" : "📺"}{" "}
                    {playbackStatus.device_name}
                  </p>
                )}
              </div>
              <div
                className={`w-4 h-4 rounded-full ${
                  isPlaying
                    ? "bg-green-500 animate-pulse"
                    : isPaused
                      ? "bg-yellow-500"
                      : "bg-slate-500"
                }`}
              />
            </div>
          </div>
        )}

        {/* Speaker Selection */}
        <div className="bg-white/5 backdrop-blur rounded-xl p-6 mb-6 border border-white/10">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            🔊 Select Speaker
            <button
              onClick={fetchSpeakers}
              className="text-sm text-purple-400 hover:text-purple-300 ml-auto"
            >
              Refresh
            </button>
          </h2>

          {speakers.length === 0 ? (
            <p className="text-slate-400">
              No speakers found. Make sure Chromecast or LMS devices are on the
              network.
            </p>
          ) : (
            <div className="space-y-4">
              {/* Chromecast Speakers */}
              {chromecastSpeakers.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">
                    Chromecast
                  </p>
                  <div className="grid gap-2">
                    {chromecastSpeakers.map((speaker) => (
                      <button
                        key={speaker.id}
                        onClick={() => setSelectedSpeaker(speaker.id)}
                        className={`p-4 rounded-lg text-left transition-all ${
                          selectedSpeaker === speaker.id
                            ? "bg-purple-600 border-purple-400"
                            : "bg-white/5 hover:bg-white/10 border-transparent"
                        } border`}
                      >
                        <p className="font-medium">
                          {getSpeakerIcon(speaker.type)} {speaker.name}
                        </p>
                        <p className="text-sm text-slate-400">
                          {speaker.model} • {speaker.ip_address}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* LMS/Squeezebox Speakers */}
              {lmsSpeakers.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">
                    Squeezebox / LMS
                  </p>
                  <div className="grid gap-2">
                    {lmsSpeakers.map((speaker) => (
                      <button
                        key={speaker.id}
                        onClick={() => setSelectedSpeaker(speaker.id)}
                        className={`p-4 rounded-lg text-left transition-all ${
                          selectedSpeaker === speaker.id
                            ? "bg-purple-600 border-purple-400"
                            : "bg-white/5 hover:bg-white/10 border-transparent"
                        } border`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">
                              {getSpeakerIcon(speaker.type)} {speaker.name}
                            </p>
                            <p className="text-sm text-slate-400">
                              {speaker.model} • {speaker.ip_address}
                            </p>
                          </div>
                          <span
                            className={`text-xs px-2 py-1 rounded ${
                              speaker.is_available
                                ? "bg-green-500/20 text-green-400"
                                : "bg-slate-500/20 text-slate-400"
                            }`}
                          >
                            {speaker.is_available ? "Online" : "Offline"}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Volume Control */}
        {selectedSpeaker && (
          <div className="bg-white/5 backdrop-blur rounded-xl p-6 mb-6 border border-white/10">
            <h2 className="text-lg font-semibold mb-4">🎚️ Volume</h2>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={volume}
              onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
            />
            <p className="text-center text-slate-400 mt-2">
              {Math.round(volume * 100)}%
            </p>
          </div>
        )}

        {/* Station Selection */}
        <div className="bg-white/5 backdrop-blur rounded-xl p-6 mb-6 border border-white/10">
          <h2 className="text-lg font-semibold mb-4">📻 Stations</h2>

          <div className="grid gap-2 mb-4">
            {stations.map((station) => (
              <div
                key={station.id}
                className={`p-4 rounded-lg flex items-center justify-between transition-all ${
                  selectedStation === station.id
                    ? "bg-purple-600 border-purple-400"
                    : "bg-white/5 hover:bg-white/10 border-transparent"
                } border`}
              >
                <button
                  onClick={() => {
                    setSelectedStation(station.id);
                    setFrequency(station.frequency);
                  }}
                  className="flex-1 text-left"
                >
                  <p className="font-medium">{station.name}</p>
                  <p className="text-sm text-slate-400">
                    {station.frequency} MHz
                  </p>
                </button>
                <button
                  onClick={() => handleDeleteStation(station.id)}
                  className="text-red-400 hover:text-red-300 p-2"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          {/* Manual Frequency */}
          <div className="border-t border-white/10 pt-4 mt-4">
            <p className="text-sm text-slate-400 mb-2">Or tune manually:</p>
            <div className="flex gap-2">
              <input
                type="number"
                step="0.1"
                min="87.5"
                max="108"
                value={frequency}
                onChange={(e) => {
                  setFrequency(e.target.value);
                  setSelectedStation(null);
                }}
                className="flex-1 bg-white/10 rounded-lg px-4 py-2 border border-white/10 focus:border-purple-500 focus:outline-none"
                placeholder="Frequency (MHz)"
              />
              <span className="flex items-center text-slate-400">MHz</span>
            </div>
          </div>

          {/* Add Station */}
          <form
            onSubmit={handleAddStation}
            className="border-t border-white/10 pt-4 mt-4"
          >
            <p className="text-sm text-slate-400 mb-2">Add new station:</p>
            <div className="flex gap-2">
              <input
                type="text"
                value={newStationName}
                onChange={(e) => setNewStationName(e.target.value)}
                className="flex-1 bg-white/10 rounded-lg px-4 py-2 border border-white/10 focus:border-purple-500 focus:outline-none"
                placeholder="Station name"
              />
              <input
                type="number"
                step="0.1"
                value={newStationFreq}
                onChange={(e) => setNewStationFreq(e.target.value)}
                className="w-24 bg-white/10 rounded-lg px-4 py-2 border border-white/10 focus:border-purple-500 focus:outline-none"
                placeholder="MHz"
              />
              <button
                type="submit"
                className="bg-purple-600 hover:bg-purple-500 rounded-lg px-4 py-2 font-medium"
              >
                Add
              </button>
            </div>
          </form>
        </div>

        {/* Playback Controls */}
        <div className="bg-white/5 backdrop-blur rounded-xl p-6 border border-white/10">
          <div className="flex justify-center gap-4">
            {isPlaying ? (
              <>
                <button
                  onClick={handlePause}
                  disabled={loading}
                  className="bg-yellow-600 hover:bg-yellow-500 disabled:opacity-50 rounded-full p-4 transition-all"
                >
                  <svg
                    className="w-8 h-8"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                  </svg>
                </button>
                <button
                  onClick={handleStop}
                  disabled={loading}
                  className="bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-full p-4 transition-all"
                >
                  <svg
                    className="w-8 h-8"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M6 6h12v12H6z" />
                  </svg>
                </button>
              </>
            ) : isPaused ? (
              <>
                <button
                  onClick={handleResume}
                  disabled={loading}
                  className="bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-full p-4 transition-all"
                >
                  <svg
                    className="w-8 h-8"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </button>
                <button
                  onClick={handleStop}
                  disabled={loading}
                  className="bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-full p-4 transition-all"
                >
                  <svg
                    className="w-8 h-8"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M6 6h12v12H6z" />
                  </svg>
                </button>
              </>
            ) : (
              <button
                onClick={handlePlay}
                disabled={loading || !selectedSpeaker}
                className="bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-full p-6 transition-all transform hover:scale-105"
              >
                {loading ? (
                  <svg
                    className="w-10 h-10 animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                ) : (
                  <svg
                    className="w-10 h-10"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M8 5v14l11-7z" />
                  </svg>
                )}
              </button>
            )}
          </div>

          {!selectedSpeaker && (
            <p className="text-center text-slate-400 mt-4 text-sm">
              Select a speaker to start playing
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
