import { useState, useEffect, useCallback } from "react"
import { AppLayout, LeftSidebar, RightSidebar, BottomBar } from "@/components/layout"
import { NowPlaying } from "@/components/player"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import {
  usePlayback,
  useStations,
  useSpeakers,
  useDABMetadata,
  useBrowserAudio,
  useBackendStatus,
  BROWSER_SPEAKER_ID,
} from "@/hooks"
import {
  tunerApi,
  dabApi,
  waitForStreamReady,
  getStreamUrl,
} from "@/lib/api"

export default function RadioApp() {
  // Core state
  const [selectedStation, setSelectedStation] = useState(null)
  const [selectedMode, setSelectedMode] = useState("dab") // "dab" or "fm"
  const [frequency, setFrequency] = useState(101.1)
  const [volume, setVolume] = useState(0.5)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  // New station form state
  const [newStation, setNewStation] = useState({ type: "fm" })

  // Browser audio
  const browserAudio = useBrowserAudio()

  // Backend connection status
  const backendStatus = useBackendStatus()

  // Speakers
  const speakers = useSpeakers()

  // Stations
  const stationsHook = useStations()

  // Playback state management
  const playback = usePlayback({
    selectedSpeaker: speakers.selectedSpeaker,
    selectedStation,
    stations: stationsHook.stations,
    frequency,
    volume,
    audioElement: browserAudio.audioElement,
    setAudioElement: browserAudio.setAudioElement,
    browserPlaying: browserAudio.browserPlaying,
    setBrowserPlaying: browserAudio.setBrowserPlaying,
  })

  // Get current station
  const currentStation = selectedStation
    ? stationsHook.stations.find((s) => s.id === selectedStation)
    : null

  // Determine if playing DAB+
  const isDABPlaying =
    playback.radioMode === "dab" ||
    (browserAudio.browserPlaying && currentStation?.station_type === "dab")

  // DAB+ metadata (only fetch when playing DAB+)
  const dabMetadata = useDABMetadata(isDABPlaying)

  // Combined play handler - accepts optional station to avoid stale closure issues
  const handlePlay = useCallback(async (stationOverride = null) => {
    if (!speakers.selectedSpeaker) {
      setError("Please select a speaker")
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Browser playback
      if (speakers.selectedSpeaker === BROWSER_SPEAKER_ID) {
        // Stop existing audio
        browserAudio.stop()

        // Use override station if provided, otherwise use currentStation
        const station = stationOverride || currentStation

        // Tune based on station type or selected mode
        if (station?.station_type === "dab") {
          await dabApi.tune(
            station.dab_channel,
            station.dab_program,
            station.dab_service_id
          )
        } else if (station) {
          // FM station selected
          const tuneFrequency = station.frequency || parseFloat(frequency)
          await tunerApi.tune(tuneFrequency, "wfm")
        } else if (selectedMode === "fm") {
          // No station selected, but FM mode - use manual frequency
          await tunerApi.tune(parseFloat(frequency), "wfm")
        } else {
          // DAB mode with no station selected
          throw new Error("Please select a DAB+ station to play")
        }

        // Wait for stream
        const streamReady = await waitForStreamReady()
        if (!streamReady) {
          throw new Error("Stream not ready. Please try again.")
        }

        // Play stream
        browserAudio.play(getStreamUrl(), volume)
        return
      }

      // External speaker playback handled by usePlayback hook
      await playback.play()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [
    speakers.selectedSpeaker,
    currentStation,
    selectedMode,
    frequency,
    volume,
    browserAudio,
    playback,
  ])

  // Combined stop handler
  const handleStop = useCallback(async () => {
    setLoading(true)
    try {
      browserAudio.stop()
      await playback.stop()
    } catch (err) {
      setError("Failed to stop playback")
    } finally {
      setLoading(false)
    }
  }, [browserAudio, playback])

  // Volume change handler
  const handleVolumeChange = useCallback(
    async (newVolume) => {
      setVolume(newVolume)
      browserAudio.setVolume(newVolume)
      await speakers.setVolume(speakers.selectedSpeaker, newVolume)
    },
    [browserAudio, speakers]
  )

  // Speaker selection with transfer dialog support
  const handleSpeakerSelect = useCallback(
    (speakerId) => {
      const isCurrentlyPlaying = playback.isPlaying || playback.isPaused
      speakers.selectSpeaker(speakerId, isCurrentlyPlaying)
    },
    [speakers, playback.isPlaying, playback.isPaused]
  )

  // Handle transfer confirm
  const handleTransferConfirm = useCallback(async () => {
    await handleStop()
    const newSpeakerId = speakers.confirmTransfer()
    // Start playback on new speaker after state update
    setTimeout(() => {
      if (frequency || selectedStation) {
        handlePlay()
      }
    }, 100)
  }, [handleStop, speakers, frequency, selectedStation, handlePlay])

  // Station selection
  const handleStationSelect = useCallback(
    (stationId) => {
      setSelectedStation(stationId)
      const station = stationsHook.stations.find((s) => s.id === stationId)
      if (station?.station_type !== "dab" && station?.frequency) {
        setFrequency(station.frequency)
      }
    },
    [stationsHook.stations]
  )

  // Station play (select and play)
  const handleStationPlay = useCallback(
    (stationId) => {
      handleStationSelect(stationId)
      // Find the station and pass it directly to avoid stale closure issues
      const station = stationsHook.stations.find((s) => s.id === stationId)
      if (station) {
        handlePlay(station)
      }
    },
    [handleStationSelect, handlePlay, stationsHook.stations]
  )

  // Delete station
  const handleDeleteStation = useCallback(
    async (stationId) => {
      await stationsHook.deleteStation(stationId)
      if (selectedStation === stationId) {
        setSelectedStation(null)
      }
    },
    [stationsHook, selectedStation]
  )

  // Add new station
  const handleAddStation = useCallback(async () => {
    if (!newStation.name) return

    const stationData = {
      name: newStation.name,
      station_type: newStation.type || "fm",
    }

    if (newStation.type === "dab") {
      if (!newStation.channel) return
      stationData.dab_channel = newStation.channel
      stationData.dab_program = newStation.program || newStation.name
    } else {
      if (!newStation.frequency) return
      stationData.frequency = parseFloat(newStation.frequency)
      stationData.modulation = "wfm"
    }

    const success = await stationsHook.addStation(stationData)
    if (success) {
      setNewStation({ type: "fm" })
    }
  }, [newStation, stationsHook])

  // Frequency change
  const handleFrequencyChange = useCallback((freq) => {
    setFrequency(freq)
    setSelectedStation(null)
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ignore if typing in input
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return

      switch (e.key) {
        case " ": // Space - toggle play/pause
          e.preventDefault()
          if (playback.isPlaying || browserAudio.browserPlaying) {
            handleStop()
          } else {
            handlePlay()
          }
          break
        case "m": // M - toggle mute
        case "M":
          handleVolumeChange(volume > 0 ? 0 : 0.5)
          break
        case "ArrowUp": // Volume up
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault()
            handleVolumeChange(Math.min(1, volume + 0.1))
          }
          break
        case "ArrowDown": // Volume down
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault()
            handleVolumeChange(Math.max(0, volume - 0.1))
          }
          break
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [playback.isPlaying, browserAudio.browserPlaying, volume, handleStop, handlePlay, handleVolumeChange])

  // Is playing state (browser or external)
  const isPlaying = playback.isPlaying || browserAudio.browserPlaying
  const isPaused = playback.isPaused

  // Update document title based on playing station/song
  useEffect(() => {
    const baseTitle = "RTL-SDR Radio"

    if (!isPlaying) {
      document.title = baseTitle
      return
    }

    // Check for DAB+ DLS metadata first (artist - song info)
    if (isDABPlaying && dabMetadata.metadata?.dls) {
      document.title = `${dabMetadata.metadata.dls} | ${baseTitle}`
      return
    }

    // Fall back to station name
    if (currentStation?.name) {
      document.title = `${currentStation.name} | ${baseTitle}`
      return
    }

    document.title = baseTitle
  }, [isPlaying, isDABPlaying, dabMetadata.metadata?.dls, currentStation?.name])

  // Combine errors
  useEffect(() => {
    const combinedError =
      error || playback.error || stationsHook.error || speakers.error
    if (combinedError) {
      setError(combinedError)
    }
  }, [playback.error, stationsHook.error, speakers.error])

  // Clear error handler
  const handleClearError = useCallback(() => {
    setError(null)
    playback.clearError()
    stationsHook.clearError()
    speakers.clearError()
  }, [playback, stationsHook, speakers])

  return (
    <>
      <AppLayout
        error={error}
        onDismissError={handleClearError}
        leftSidebar={
          <LeftSidebar
            stations={stationsHook.stations}
            fmStations={stationsHook.fmStations}
            dabStations={stationsHook.dabStations}
            selectedStation={selectedStation}
            onSelectStation={handleStationSelect}
            onPlayStation={handleStationPlay}
            onDeleteStation={handleDeleteStation}
            onModeChange={setSelectedMode}
            isPlaying={isPlaying}
          />
        }
        rightSidebar={
          <RightSidebar
            dabChannels={stationsHook.dabChannels}
            selectedDabChannel={stationsHook.selectedDabChannel}
            onSelectDabChannel={stationsHook.setSelectedDabChannel}
            dabPrograms={stationsHook.dabPrograms}
            scanning={stationsHook.scanning}
            onScan={() => stationsHook.scanDabChannel(stationsHook.selectedDabChannel)}
            onAddProgram={stationsHook.addDabProgram}
            frequency={frequency}
            onFrequencyChange={handleFrequencyChange}
            newStation={newStation}
            onNewStationChange={setNewStation}
            onAddStation={handleAddStation}
          />
        }
        bottomBar={
          <BottomBar
            speakers={speakers.speakers}
            selectedSpeaker={speakers.selectedSpeaker}
            onSelectSpeaker={handleSpeakerSelect}
            volume={volume}
            onVolumeChange={handleVolumeChange}
            isPlaying={isPlaying}
            isPaused={isPaused}
            backendStatus={backendStatus}
          />
        }
      >
        {/* Center Content - Now Playing */}
        <NowPlaying
          station={currentStation}
          isPlaying={isPlaying}
          isPaused={isPaused}
          loading={loading || playback.loading}
          disabled={!speakers.selectedSpeaker}
          dabMetadata={isDABPlaying ? dabMetadata.metadata : null}
          onPlay={handlePlay}
          onPause={playback.pause}
          onStop={handleStop}
          onResume={playback.resume}
        />
      </AppLayout>

      {/* Transfer Playback Dialog */}
      <Dialog
        open={speakers.showTransferDialog}
        onOpenChange={(open) => !open && speakers.cancelTransfer()}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Transfer Playback?</DialogTitle>
            <DialogDescription>
              Music is currently playing. Would you like to transfer playback to
              the new speaker?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col gap-2 sm:flex-col">
            <Button onClick={handleTransferConfirm} className="w-full">
              Transfer Playback
            </Button>
            <Button
              variant="secondary"
              onClick={speakers.switchWithoutTransfer}
              className="w-full"
            >
              Switch Speaker Only
            </Button>
            <Button
              variant="ghost"
              onClick={speakers.cancelTransfer}
              className="w-full"
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
