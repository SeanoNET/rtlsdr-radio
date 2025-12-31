import { useState, useEffect, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

// Special ID for browser playback
const BROWSER_SPEAKER_ID = "browser:local";

// Helper to wait for stream to be ready with backoff
async function waitForStreamReady(maxAttempts = 10, baseDelay = 200) {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const res = await fetch(`${API_BASE}/stream/ready`);
      const data = await res.json();
      if (data.ready) {
        return true;
      }
    } catch (err) {
      console.debug("Stream ready check failed:", err);
    }
    // Exponential backoff
    const delay = baseDelay * Math.pow(1.5, attempt);
    await new Promise((resolve) => setTimeout(resolve, delay));
  }
  return false;
}

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

  // Browser audio playback
  const [audioElement, setAudioElement] = useState(null);
  const [browserPlaying, setBrowserPlaying] = useState(false);

  // New station form
  const [newStationName, setNewStationName] = useState("");
  const [newStationFreq, setNewStationFreq] = useState("");
  const [newStationType, setNewStationType] = useState("fm");
  const [newStationChannel, setNewStationChannel] = useState("");
  const [newStationProgram, setNewStationProgram] = useState("");

  // DAB+ scan
  const [dabChannels, setDabChannels] = useState([]);
  const [selectedDabChannel, setSelectedDabChannel] = useState("");
  const [dabPrograms, setDabPrograms] = useState([]);
  const [scanning, setScanning] = useState(false);

  // Transfer playback dialog
  const [showTransferDialog, setShowTransferDialog] = useState(false);
  const [pendingSpeakerChange, setPendingSpeakerChange] = useState(null);

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

  const fetchDabChannels = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/dab/channels`);
      const data = await res.json();
      setDabChannels(data);
    } catch (err) {
      console.error("Failed to fetch DAB channels");
    }
  }, []);

  const scanDabChannel = async (channel) => {
    setScanning(true);
    setDabPrograms([]);
    try {
      const res = await fetch(`${API_BASE}/dab/programs?channel=${channel}`);
      const data = await res.json();
      setDabPrograms(data);
    } catch (err) {
      setError("Failed to scan DAB+ channel");
    } finally {
      setScanning(false);
    }
  };

  const addDabProgram = async (program) => {
    try {
      const body = {
        name: program.name.trim(),
        station_type: "dab",
        dab_channel: program.channel,
        dab_program: program.name.trim(),
        dab_service_id: program.service_id,
      };
      const res = await fetch(`${API_BASE}/stations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        await fetchStations();
      }
    } catch (err) {
      setError("Failed to add station");
    }
  };

  useEffect(() => {
    fetchSpeakers();
    fetchStations();
    fetchPlaybackStatus();
    fetchDabChannels();

    const interval = setInterval(fetchPlaybackStatus, 2000);
    return () => clearInterval(interval);
  }, [fetchSpeakers, fetchStations, fetchPlaybackStatus, fetchDabChannels]);

  // Computed playback state - defined early so handlers can use them
  const isPlaying = playbackStatus?.state === "playing" || browserPlaying;
  const isPaused = playbackStatus?.state === "paused";

  const handlePlay = async () => {
    if (!selectedSpeaker) {
      setError("Please select a speaker");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Browser playback - tune first, then play stream locally
      if (selectedSpeaker === BROWSER_SPEAKER_ID) {
        // Stop existing audio before switching channels
        if (audioElement) {
          audioElement.pause();
          audioElement.src = "";
          setAudioElement(null);
          setBrowserPlaying(false);
        }

        const station = selectedStation
          ? stations.find((s) => s.id === selectedStation)
          : null;

        // Check if this is a DAB+ station
        if (station?.station_type === "dab") {
          // DAB+ tuning
          const tuneRes = await fetch(`${API_BASE}/dab/tune`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              channel: station.dab_channel,
              program: station.dab_program,
              service_id: station.dab_service_id,
            }),
          });

          if (!tuneRes.ok) {
            const data = await tuneRes.json();
            const detail =
              typeof data.detail === "string"
                ? data.detail
                : JSON.stringify(data.detail) || "Failed to tune DAB+";
            throw new Error(detail);
          }
        } else {
          // FM tuning
          const tuneFrequency = station?.frequency || parseFloat(frequency);
          const tuneBody = { frequency: tuneFrequency, modulation: "wfm" };

          const tuneRes = await fetch(`${API_BASE}/tuner/tune`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(tuneBody),
          });

          if (!tuneRes.ok) {
            const data = await tuneRes.json();
            const detail =
              typeof data.detail === "string"
                ? data.detail
                : JSON.stringify(data.detail) || "Failed to tune";
            throw new Error(detail);
          }
        }

        // Wait for stream to be ready before connecting
        const streamReady = await waitForStreamReady();
        if (!streamReady) {
          throw new Error("Stream not ready. Please try again.");
        }

        // Create audio element and play stream
        const audio = new Audio(`${API_BASE}/stream`);
        audio.volume = volume;

        // Handle audio errors gracefully
        audio.onerror = () => {
          console.debug("Audio stream error - stream may have stopped");
          setBrowserPlaying(false);
        };

        audio.play();
        setAudioElement(audio);
        setBrowserPlaying(true);
        return;
      }

      // External speaker playback - station_id handles both FM and DAB+ automatically
      const body = {
        device_id: selectedSpeaker,
        ...(selectedStation
          ? { station_id: selectedStation }
          : { frequency: parseFloat(frequency), modulation: "wfm" }),
      };

      // If no station selected but we have DAB+ params, this is manual DAB+ tuning
      // (future enhancement - for now manual tuning is FM only)

      const res = await fetch(`${API_BASE}/playback/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json();
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail) || "Failed to start playback";
        throw new Error(detail);
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
      // Stop browser audio if playing
      if (audioElement) {
        audioElement.pause();
        audioElement.src = "";
        setAudioElement(null);
        setBrowserPlaying(false);
      }

      await fetch(`${API_BASE}/playback/stop`, { method: "POST" });
      await fetch(`${API_BASE}/tuner/stop`, { method: "POST" });
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

    // Browser audio volume
    if (audioElement) {
      audioElement.volume = newVolume;
    }

    // External speaker volume
    if (selectedSpeaker && selectedSpeaker !== BROWSER_SPEAKER_ID) {
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

    // Validate based on station type
    if (!newStationName) return;
    if (newStationType === "fm" && !newStationFreq) return;
    if (newStationType === "dab" && !newStationChannel) return;

    try {
      const body = {
        name: newStationName,
        station_type: newStationType,
      };

      if (newStationType === "dab") {
        body.dab_channel = newStationChannel;
        body.dab_program = newStationProgram || newStationName;
      } else {
        body.frequency = parseFloat(newStationFreq);
        body.modulation = "wfm";
      }

      const res = await fetch(`${API_BASE}/stations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        setNewStationName("");
        setNewStationFreq("");
        setNewStationType("fm");
        setNewStationChannel("");
        setNewStationProgram("");
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

  const handlePowerToggle = async (speakerId, powerOn) => {
    try {
      const res = await fetch(
        `${API_BASE}/speakers/${speakerId}/power?power=${powerOn}`,
        {
          method: "POST",
        },
      );
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to toggle power");
      }
      await fetchSpeakers();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSpeakerSelect = (speakerId) => {
    // If currently playing and selecting a different speaker, prompt for transfer
    if (
      (isPlaying || isPaused) &&
      selectedSpeaker &&
      selectedSpeaker !== speakerId
    ) {
      setPendingSpeakerChange(speakerId);
      setShowTransferDialog(true);
    } else {
      setSelectedSpeaker(speakerId);
    }
  };

  const handleTransferConfirm = async () => {
    setShowTransferDialog(false);
    const newSpeakerId = pendingSpeakerChange;
    setPendingSpeakerChange(null);

    // Stop current playback
    await handleStop();

    // Select new speaker
    setSelectedSpeaker(newSpeakerId);

    // If we have a frequency or station selected, start playback on new speaker
    if (frequency || selectedStation) {
      // Small delay to let state update
      setTimeout(() => {
        handlePlay();
      }, 100);
    }
  };

  const handleTransferCancel = () => {
    setShowTransferDialog(false);
    setPendingSpeakerChange(null);
  };

  const handleSwitchWithoutTransfer = () => {
    setShowTransferDialog(false);
    setSelectedSpeaker(pendingSpeakerChange);
    setPendingSpeakerChange(null);
  };

  const getSpeakerIcon = (type) => {
    return type === "chromecast" ? "📺" : "🔊";
  };

  const getSpeakerTypeLabel = (type) => {
    return type === "chromecast" ? "Chromecast" : "Squeezebox";
  };

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
          Stream FM &amp; DAB+ radio to Chromecast or Squeezebox
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
                <p className="text-sm text-slate-400">
                  Now Playing {playbackStatus.radio_mode === "dab" ? "(DAB+)" : playbackStatus.radio_mode === "fm" ? "(FM)" : ""}
                </p>
                <p className="text-2xl font-semibold">
                  {playbackStatus.radio_mode === "dab"
                    ? (playbackStatus.dab_program || playbackStatus.dab_channel || "DAB+")
                    : playbackStatus.frequency
                      ? `${playbackStatus.frequency} MHz`
                      : "Not tuned"}
                </p>
                {playbackStatus.radio_mode === "dab" && playbackStatus.dab_channel && (
                  <p className="text-sm text-slate-400">
                    Channel {playbackStatus.dab_channel}
                  </p>
                )}
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

          <div className="space-y-4">
            {/* Browser Playback Option */}
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">
                This Browser
              </p>
              <button
                onClick={() => handleSpeakerSelect(BROWSER_SPEAKER_ID)}
                className={`w-full p-4 rounded-lg text-left transition-all ${
                  selectedSpeaker === BROWSER_SPEAKER_ID
                    ? "bg-purple-600 border-purple-400"
                    : "bg-white/5 hover:bg-white/10 border-transparent"
                } border`}
              >
                <p className="font-medium">🎧 Browser Audio</p>
                <p className="text-sm text-slate-400">
                  Listen directly in this browser
                </p>
              </button>
            </div>

            {speakers.length === 0 ? (
              <p className="text-slate-400">
                No external speakers found. You can still listen in browser.
              </p>
            ) : (
              <>
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
                          onClick={() => handleSpeakerSelect(speaker.id)}
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
                            {speaker.is_available && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handlePowerToggle(speaker.id, false);
                                }}
                                className="text-xs px-2 py-1 rounded transition-all bg-red-500/20 text-red-400 hover:bg-red-500/40"
                                title="Stop casting"
                              >
                                ⏹ Stop
                              </button>
                            )}
                          </div>
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
                          onClick={() => handleSpeakerSelect(speaker.id)}
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
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePowerToggle(
                                  speaker.id,
                                  !speaker.is_available,
                                );
                              }}
                              className={`text-xs px-2 py-1 rounded transition-all ${
                                speaker.is_available
                                  ? "bg-green-500/20 text-green-400 hover:bg-green-500/40"
                                  : "bg-slate-500/20 text-slate-400 hover:bg-slate-500/40"
                              }`}
                              title={
                                speaker.is_available ? "Power off" : "Power on"
                              }
                            >
                              ⏻ {speaker.is_available ? "On" : "Standby"}
                            </button>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
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
                    if (station.station_type !== "dab" && station.frequency) {
                      setFrequency(station.frequency);
                    }
                  }}
                  className="flex-1 text-left"
                >
                  <p className="font-medium">{station.name}</p>
                  <p className="text-sm text-slate-400">
                    {station.station_type === "dab"
                      ? `DAB+ ${station.dab_channel}${station.dab_program ? ` • ${station.dab_program}` : ""}`
                      : `${station.frequency} MHz`}
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

          {/* DAB+ Scan */}
          <div className="border-t border-white/10 pt-4 mt-4">
            <p className="text-sm text-slate-400 mb-2">Scan DAB+ channels:</p>
            <div className="flex gap-2 mb-3">
              <select
                value={selectedDabChannel}
                onChange={(e) => setSelectedDabChannel(e.target.value)}
                className="flex-1 bg-white/10 rounded-lg px-3 py-2 border border-white/10 focus:border-purple-500 focus:outline-none"
              >
                <option value="">Select channel...</option>
                {dabChannels.map((ch) => (
                  <option key={ch.id} value={ch.id}>
                    {ch.id}
                  </option>
                ))}
              </select>
              <button
                onClick={() => selectedDabChannel && scanDabChannel(selectedDabChannel)}
                disabled={!selectedDabChannel || scanning}
                className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 rounded-lg px-4 py-2 font-medium"
              >
                {scanning ? "Scanning..." : "Scan"}
              </button>
            </div>
            {dabPrograms.length > 0 && (
              <div className="bg-white/5 rounded-lg p-3 space-y-2">
                <p className="text-xs text-slate-400 uppercase tracking-wide">
                  Found {dabPrograms.length} programs on {selectedDabChannel}:
                </p>
                {dabPrograms.map((prog) => (
                  <div
                    key={prog.service_id}
                    className="flex items-center justify-between p-2 bg-white/5 rounded"
                  >
                    <div>
                      <p className="font-medium">{prog.name}</p>
                      <p className="text-xs text-slate-400">
                        ID: {prog.service_id} {prog.bitrate ? `• ${prog.bitrate}kbps` : ""}
                      </p>
                    </div>
                    <button
                      onClick={() => addDabProgram(prog)}
                      className="text-purple-400 hover:text-purple-300 px-3 py-1 text-sm bg-purple-500/20 rounded"
                    >
                      + Add
                    </button>
                  </div>
                ))}
              </div>
            )}
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
            <div className="flex flex-col gap-2">
              <div className="flex gap-2">
                <select
                  value={newStationType}
                  onChange={(e) => setNewStationType(e.target.value)}
                  className="bg-white/10 rounded-lg px-3 py-2 border border-white/10 focus:border-purple-500 focus:outline-none"
                >
                  <option value="fm">FM</option>
                  <option value="dab">DAB+</option>
                </select>
                <input
                  type="text"
                  value={newStationName}
                  onChange={(e) => setNewStationName(e.target.value)}
                  className="flex-1 bg-white/10 rounded-lg px-4 py-2 border border-white/10 focus:border-purple-500 focus:outline-none"
                  placeholder="Station name"
                />
              </div>
              <div className="flex gap-2">
                {newStationType === "dab" ? (
                  <>
                    <input
                      type="text"
                      value={newStationChannel}
                      onChange={(e) => setNewStationChannel(e.target.value)}
                      className="w-24 bg-white/10 rounded-lg px-4 py-2 border border-white/10 focus:border-purple-500 focus:outline-none"
                      placeholder="9C"
                    />
                    <input
                      type="text"
                      value={newStationProgram}
                      onChange={(e) => setNewStationProgram(e.target.value)}
                      className="flex-1 bg-white/10 rounded-lg px-4 py-2 border border-white/10 focus:border-purple-500 focus:outline-none"
                      placeholder="Program name (optional)"
                    />
                  </>
                ) : (
                  <input
                    type="number"
                    step="0.1"
                    value={newStationFreq}
                    onChange={(e) => setNewStationFreq(e.target.value)}
                    className="flex-1 bg-white/10 rounded-lg px-4 py-2 border border-white/10 focus:border-purple-500 focus:outline-none"
                    placeholder="Frequency (MHz)"
                  />
                )}
                <button
                  type="submit"
                  className="bg-purple-600 hover:bg-purple-500 rounded-lg px-4 py-2 font-medium"
                >
                  Add
                </button>
              </div>
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

      {/* Transfer Playback Dialog */}
      {showTransferDialog && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-6 max-w-md mx-4 border border-white/10 shadow-2xl">
            <h3 className="text-xl font-semibold mb-4">Transfer Playback?</h3>
            <p className="text-slate-300 mb-6">
              Music is currently playing. Would you like to transfer playback to
              the new speaker?
            </p>
            <div className="flex flex-col gap-2">
              <button
                onClick={handleTransferConfirm}
                className="w-full bg-purple-600 hover:bg-purple-500 rounded-lg px-4 py-3 font-medium transition-all"
              >
                Transfer Playback
              </button>
              <button
                onClick={handleSwitchWithoutTransfer}
                className="w-full bg-white/10 hover:bg-white/20 rounded-lg px-4 py-3 font-medium transition-all"
              >
                Switch Speaker Only
              </button>
              <button
                onClick={handleTransferCancel}
                className="w-full text-slate-400 hover:text-white py-2 transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
