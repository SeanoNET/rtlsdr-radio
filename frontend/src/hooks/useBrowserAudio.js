import { useState, useCallback, useEffect } from "react"

export function useBrowserAudio() {
  const [audioElement, setAudioElement] = useState(null)
  const [browserPlaying, setBrowserPlaying] = useState(false)

  // Create and play audio element
  const createAudio = useCallback((streamUrl, volume = 0.5) => {
    const audio = new Audio(streamUrl)
    audio.volume = volume

    // Handle audio errors gracefully
    audio.onerror = () => {
      console.debug("Audio stream error - stream may have stopped")
      setBrowserPlaying(false)
    }

    return audio
  }, [])

  // Play stream
  const play = useCallback(
    (streamUrl, volume = 0.5) => {
      // Stop existing audio first
      if (audioElement) {
        audioElement.pause()
        audioElement.src = ""
      }

      const audio = createAudio(streamUrl, volume)
      audio.play()
      setAudioElement(audio)
      setBrowserPlaying(true)
    },
    [audioElement, createAudio]
  )

  // Stop browser audio
  const stop = useCallback(() => {
    if (audioElement) {
      audioElement.pause()
      audioElement.src = ""
      setAudioElement(null)
      setBrowserPlaying(false)
    }
  }, [audioElement])

  // Set volume
  const setVolume = useCallback(
    (volume) => {
      if (audioElement) {
        audioElement.volume = volume
      }
    },
    [audioElement]
  )

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (audioElement) {
        audioElement.pause()
        audioElement.src = ""
      }
    }
  }, [audioElement])

  return {
    audioElement,
    browserPlaying,
    play,
    stop,
    setVolume,
    setAudioElement,
    setBrowserPlaying,
  }
}
