import { useState, useEffect, useCallback } from "react"
import { stationsApi, dabApi } from "@/lib/api"

export function useStations() {
  const [stations, setStations] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // DAB+ scan state
  const [dabChannels, setDabChannels] = useState([])
  const [selectedDabChannel, setSelectedDabChannel] = useState("")
  const [dabPrograms, setDabPrograms] = useState([])
  const [scanning, setScanning] = useState(false)

  // Fetch all stations
  const fetchStations = useCallback(async () => {
    try {
      const data = await stationsApi.list()
      setStations(data)
    } catch (err) {
      setError("Failed to fetch stations")
    }
  }, [])

  // Fetch DAB channels
  const fetchDabChannels = useCallback(async () => {
    try {
      const data = await dabApi.channels()
      setDabChannels(data)
    } catch (err) {
      console.error("Failed to fetch DAB channels")
    }
  }, [])

  // Initial fetch
  useEffect(() => {
    fetchStations()
    fetchDabChannels()
  }, [fetchStations, fetchDabChannels])

  // Add station
  const addStation = useCallback(
    async (stationData) => {
      setLoading(true)
      try {
        await stationsApi.create(stationData)
        await fetchStations()
        return true
      } catch (err) {
        setError("Failed to add station")
        return false
      } finally {
        setLoading(false)
      }
    },
    [fetchStations]
  )

  // Delete station
  const deleteStation = useCallback(
    async (stationId) => {
      try {
        await stationsApi.delete(stationId)
        await fetchStations()
        return true
      } catch (err) {
        setError("Failed to delete station")
        return false
      }
    },
    [fetchStations]
  )

  // Scan DAB+ channel
  const scanDabChannel = useCallback(async (channel) => {
    setScanning(true)
    setDabPrograms([])
    try {
      const data = await dabApi.programs(channel)
      setDabPrograms(data)
    } catch (err) {
      setError("Failed to scan DAB+ channel")
    } finally {
      setScanning(false)
    }
  }, [])

  // Add DAB+ program as station
  const addDabProgram = useCallback(
    async (program) => {
      const stationData = {
        name: program.name.trim(),
        station_type: "dab",
        dab_channel: program.channel,
        dab_program: program.name.trim(),
        dab_service_id: program.service_id,
      }
      return addStation(stationData)
    },
    [addStation]
  )

  // Clear error
  const clearError = useCallback(() => {
    setError(null)
  }, [])

  // Get stations by type
  const fmStations = stations.filter(
    (s) => s.station_type === "fm" || !s.station_type
  )
  const dabStations = stations.filter((s) => s.station_type === "dab")

  return {
    stations,
    fmStations,
    dabStations,
    loading,
    error,
    fetchStations,
    addStation,
    deleteStation,
    clearError,
    // DAB+ scan
    dabChannels,
    selectedDabChannel,
    setSelectedDabChannel,
    dabPrograms,
    scanning,
    scanDabChannel,
    addDabProgram,
  }
}
