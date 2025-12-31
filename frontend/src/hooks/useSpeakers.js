import { useState, useEffect, useCallback } from "react"
import { speakersApi, BROWSER_SPEAKER_ID } from "@/lib/api"

export { BROWSER_SPEAKER_ID }

const SPEAKER_STORAGE_KEY = "rtlsdr-radio-selected-speaker"

// Get saved speaker from localStorage
function getSavedSpeaker() {
  try {
    return localStorage.getItem(SPEAKER_STORAGE_KEY)
  } catch {
    return null
  }
}

// Save speaker to localStorage
function saveSpeaker(speakerId) {
  try {
    if (speakerId) {
      localStorage.setItem(SPEAKER_STORAGE_KEY, speakerId)
    } else {
      localStorage.removeItem(SPEAKER_STORAGE_KEY)
    }
  } catch {
    // Ignore storage errors
  }
}

export function useSpeakers() {
  const [speakers, setSpeakers] = useState([])
  const [selectedSpeaker, setSelectedSpeaker] = useState(() => getSavedSpeaker())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Transfer dialog state
  const [showTransferDialog, setShowTransferDialog] = useState(false)
  const [pendingSpeakerChange, setPendingSpeakerChange] = useState(null)

  // Fetch speakers
  const fetchSpeakers = useCallback(async () => {
    try {
      const data = await speakersApi.list()
      setSpeakers(data)
    } catch (err) {
      setError("Failed to fetch speakers")
    }
  }, [])

  // Initial fetch
  useEffect(() => {
    fetchSpeakers()
  }, [fetchSpeakers])

  // Save speaker to localStorage when it changes
  useEffect(() => {
    saveSpeaker(selectedSpeaker)
  }, [selectedSpeaker])

  // Set volume on external speaker
  const setVolume = useCallback(async (speakerId, volume) => {
    if (speakerId && speakerId !== BROWSER_SPEAKER_ID) {
      try {
        await speakersApi.setVolume(speakerId, volume)
      } catch (err) {
        console.error("Failed to set volume")
      }
    }
  }, [])

  // Toggle speaker power
  const togglePower = useCallback(
    async (speakerId, powerOn) => {
      try {
        await speakersApi.power(speakerId, powerOn)
        await fetchSpeakers()
      } catch (err) {
        setError(err.message || "Failed to toggle power")
      }
    },
    [fetchSpeakers]
  )

  // Handle speaker selection with transfer dialog
  const selectSpeaker = useCallback(
    (speakerId, isPlaying = false) => {
      // If currently playing and selecting a different speaker, prompt for transfer
      if (isPlaying && selectedSpeaker && selectedSpeaker !== speakerId) {
        setPendingSpeakerChange(speakerId)
        setShowTransferDialog(true)
      } else {
        setSelectedSpeaker(speakerId)
      }
    },
    [selectedSpeaker]
  )

  // Confirm transfer
  const confirmTransfer = useCallback(() => {
    setShowTransferDialog(false)
    const newSpeakerId = pendingSpeakerChange
    setPendingSpeakerChange(null)
    setSelectedSpeaker(newSpeakerId)
    return newSpeakerId
  }, [pendingSpeakerChange])

  // Cancel transfer
  const cancelTransfer = useCallback(() => {
    setShowTransferDialog(false)
    setPendingSpeakerChange(null)
  }, [])

  // Switch without transfer
  const switchWithoutTransfer = useCallback(() => {
    setShowTransferDialog(false)
    setSelectedSpeaker(pendingSpeakerChange)
    setPendingSpeakerChange(null)
  }, [pendingSpeakerChange])

  // Clear error
  const clearError = useCallback(() => {
    setError(null)
  }, [])

  // Get speakers by type
  const chromecastSpeakers = speakers.filter((s) => s.type === "chromecast")
  const lmsSpeakers = speakers.filter((s) => s.type === "lms")

  // Current speaker
  const currentSpeaker = speakers.find((s) => s.id === selectedSpeaker)
  const isBrowserSelected = selectedSpeaker === BROWSER_SPEAKER_ID

  return {
    speakers,
    chromecastSpeakers,
    lmsSpeakers,
    selectedSpeaker,
    setSelectedSpeaker,
    currentSpeaker,
    isBrowserSelected,
    loading,
    error,
    fetchSpeakers,
    setVolume,
    togglePower,
    selectSpeaker,
    clearError,
    // Transfer dialog
    showTransferDialog,
    pendingSpeakerChange,
    confirmTransfer,
    cancelTransfer,
    switchWithoutTransfer,
  }
}
