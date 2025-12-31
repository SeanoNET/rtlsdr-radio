import { useState, useEffect, useCallback } from "react"
import { API_BASE } from "@/lib/api"

/**
 * Hook to monitor backend connection status
 * Polls the backend periodically to check connectivity
 */
export function useBackendStatus(pollInterval = 10000) {
  const [isConnected, setIsConnected] = useState(true)
  const [lastChecked, setLastChecked] = useState(null)
  const [latency, setLatency] = useState(null)

  const checkConnection = useCallback(async () => {
    const startTime = performance.now()
    try {
      // Use stream/ready endpoint as a lightweight health check
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000)

      const res = await fetch(`${API_BASE}/stream/ready`, {
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      const endTime = performance.now()
      setLatency(Math.round(endTime - startTime))
      setIsConnected(res.ok)
      setLastChecked(new Date())
    } catch (err) {
      setIsConnected(false)
      setLatency(null)
      setLastChecked(new Date())
    }
  }, [])

  // Initial check on mount
  useEffect(() => {
    checkConnection()
  }, [checkConnection])

  // Periodic polling
  useEffect(() => {
    const interval = setInterval(checkConnection, pollInterval)
    return () => clearInterval(interval)
  }, [checkConnection, pollInterval])

  // Also check on window focus (user coming back to tab)
  useEffect(() => {
    const handleFocus = () => {
      checkConnection()
    }
    window.addEventListener("focus", handleFocus)
    return () => window.removeEventListener("focus", handleFocus)
  }, [checkConnection])

  return {
    isConnected,
    lastChecked,
    latency,
    checkNow: checkConnection,
  }
}
