import { useState, useEffect, useCallback } from "react"
import { dabApi } from "@/lib/api"

export function useDABMetadata(isDABPlaying) {
  const [metadata, setMetadata] = useState(null)
  const [loading, setLoading] = useState(false)

  // Fetch DAB+ metadata
  const fetchMetadata = useCallback(async () => {
    if (!isDABPlaying) return

    setLoading(true)
    try {
      const data = await dabApi.metadata()
      setMetadata(data)
    } catch (err) {
      console.debug("Failed to fetch DAB metadata:", err)
    } finally {
      setLoading(false)
    }
  }, [isDABPlaying])

  // Poll metadata when playing DAB+
  useEffect(() => {
    if (isDABPlaying) {
      // Fetch immediately when DAB+ starts
      fetchMetadata()
      // Then poll every 5 seconds
      const metadataInterval = setInterval(fetchMetadata, 5000)
      return () => clearInterval(metadataInterval)
    } else {
      // Clear metadata when not playing DAB+
      setMetadata(null)
    }
  }, [isDABPlaying, fetchMetadata])

  // Clear metadata manually
  const clearMetadata = useCallback(() => {
    setMetadata(null)
  }, [])

  return {
    metadata,
    loading,
    fetchMetadata,
    clearMetadata,
    // Convenience accessors
    dls: metadata?.dls,
    program: metadata?.program,
    motImage: metadata?.mot_image,
    motContentType: metadata?.mot_content_type,
    signal: metadata?.signal,
    audio: metadata?.audio,
    pty: metadata?.pty,
    isPlaying: metadata?.is_playing,
  }
}
