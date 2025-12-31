import { useState, useEffect, useCallback } from "react"
import {
  playbackApi,
  tunerApi,
  dabApi,
  waitForStreamReady,
  getStreamUrl,
  BROWSER_SPEAKER_ID,
} from "@/lib/api"

export function usePlayback({
  selectedSpeaker,
  selectedStation,
  stations,
  frequency,
  volume,
  audioElement,
  setAudioElement,
  browserPlaying,
  setBrowserPlaying,
}) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Fetch playback status
  const fetchStatus = useCallback(async () => {
    try {
      const data = await playbackApi.status()
      setStatus(data)
    } catch (err) {
      console.error("Failed to fetch status:", err)
    }
  }, [])

  // Poll playback status every 2 seconds
  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 2000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  // Computed playback state
  const isPlaying = status?.state === "playing" || browserPlaying
  const isPaused = status?.state === "paused"
  const radioMode = status?.radio_mode

  // Get current station info for display
  const currentStation = selectedStation
    ? stations.find((s) => s.id === selectedStation)
    : null
  const isDABPlaying =
    radioMode === "dab" ||
    (browserPlaying && currentStation?.station_type === "dab")

  // Play handler
  const play = useCallback(async () => {
    if (!selectedSpeaker) {
      setError("Please select a speaker")
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Browser playback
      if (selectedSpeaker === BROWSER_SPEAKER_ID) {
        // Stop existing audio
        if (audioElement) {
          audioElement.pause()
          audioElement.src = ""
          setAudioElement(null)
          setBrowserPlaying(false)
        }

        const station = currentStation

        // Tune based on station type
        if (station?.station_type === "dab") {
          await dabApi.tune(
            station.dab_channel,
            station.dab_program,
            station.dab_service_id
          )
        } else {
          const tuneFrequency = station?.frequency || parseFloat(frequency)
          await tunerApi.tune(tuneFrequency, "wfm")
        }

        // Wait for stream
        const streamReady = await waitForStreamReady()
        if (!streamReady) {
          throw new Error("Stream not ready. Please try again.")
        }

        // Create and play audio
        const audio = new Audio(getStreamUrl())
        audio.volume = volume

        audio.onerror = () => {
          console.debug("Audio stream error - stream may have stopped")
          setBrowserPlaying(false)
        }

        audio.play()
        setAudioElement(audio)
        setBrowserPlaying(true)
        return
      }

      // External speaker playback
      const body = {
        device_id: selectedSpeaker,
        ...(selectedStation
          ? { station_id: selectedStation }
          : { frequency: parseFloat(frequency), modulation: "wfm" }),
      }

      await playbackApi.start(body)
      await fetchStatus()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [
    selectedSpeaker,
    selectedStation,
    currentStation,
    frequency,
    volume,
    audioElement,
    setAudioElement,
    setBrowserPlaying,
    fetchStatus,
  ])

  // Stop handler
  const stop = useCallback(async () => {
    setLoading(true)
    try {
      // Stop browser audio
      if (audioElement) {
        audioElement.pause()
        audioElement.src = ""
        setAudioElement(null)
        setBrowserPlaying(false)
      }

      await playbackApi.stop()
      await tunerApi.stop()
      await fetchStatus()
    } catch (err) {
      setError("Failed to stop playback")
    } finally {
      setLoading(false)
    }
  }, [audioElement, setAudioElement, setBrowserPlaying, fetchStatus])

  // Pause handler
  const pause = useCallback(async () => {
    try {
      await playbackApi.pause()
      await fetchStatus()
    } catch (err) {
      setError("Failed to pause")
    }
  }, [fetchStatus])

  // Resume handler
  const resume = useCallback(async () => {
    try {
      await playbackApi.resume()
      await fetchStatus()
    } catch (err) {
      setError("Failed to resume")
    }
  }, [fetchStatus])

  // Clear error
  const clearError = useCallback(() => {
    setError(null)
  }, [])

  return {
    status,
    loading,
    error,
    isPlaying,
    isPaused,
    radioMode,
    isDABPlaying,
    currentStation,
    play,
    stop,
    pause,
    resume,
    clearError,
    fetchStatus,
  }
}
