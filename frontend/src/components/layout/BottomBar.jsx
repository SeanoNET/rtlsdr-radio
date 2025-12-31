import * as React from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Speaker,
  Volume2,
  VolumeX,
  Tv,
  Monitor,
  Music2,
  Loader2,
  Wifi,
  WifiOff,
} from "lucide-react"
import { BROWSER_SPEAKER_ID } from "@/lib/api"

export function BottomBar({
  speakers = [],
  selectedSpeaker,
  onSelectSpeaker,
  volume = 0.75,
  onVolumeChange,
  isPlaying,
  isPaused,
  backendStatus,
  className,
}) {
  const [isMuted, setIsMuted] = React.useState(false)
  const [prevVolume, setPrevVolume] = React.useState(volume)

  const handleMuteToggle = () => {
    if (isMuted) {
      onVolumeChange(prevVolume)
      setIsMuted(false)
    } else {
      setPrevVolume(volume)
      onVolumeChange(0)
      setIsMuted(true)
    }
  }

  const handleVolumeChange = (value) => {
    const newVolume = value[0]
    onVolumeChange(newVolume)
    if (newVolume > 0 && isMuted) {
      setIsMuted(false)
    }
  }

  // Get speaker icon based on type
  const getSpeakerIcon = (speaker) => {
    if (!speaker) return Speaker
    if (speaker.id === BROWSER_SPEAKER_ID) return Monitor
    if (speaker.type === "chromecast") return Tv
    if (speaker.type === "lms") return Music2
    return Speaker
  }

  // Get selected speaker object
  const currentSpeaker = speakers.find((s) => s.id === selectedSpeaker)
  const SpeakerIcon = getSpeakerIcon(currentSpeaker)

  // Status indicator color
  const statusColor = isPlaying
    ? "bg-green-500"
    : isPaused
    ? "bg-yellow-500"
    : "bg-muted"

  return (
    <TooltipProvider>
      <div
        className={cn(
          "h-16 border-t border-border bg-card/80 backdrop-blur-sm",
          "flex items-center justify-between px-4 gap-6",
          className
        )}
      >
        {/* Left section - Speaker selector */}
        <div className="flex items-center gap-3 min-w-[200px]">
          {/* Playing indicator - audio bars or status dot */}
          <Tooltip>
            <TooltipTrigger asChild>
              {isPlaying ? (
                <div className="audio-bars flex-shrink-0">
                  <div className="bar" />
                  <div className="bar" />
                  <div className="bar" />
                  <div className="bar" />
                </div>
              ) : (
                <div
                  className={cn(
                    "w-2.5 h-2.5 rounded-full flex-shrink-0",
                    statusColor
                  )}
                />
              )}
            </TooltipTrigger>
            <TooltipContent>
              {isPlaying ? "Playing" : isPaused ? "Paused" : "Stopped"}
            </TooltipContent>
          </Tooltip>

          {/* Speaker selector */}
          <Select value={selectedSpeaker || ""} onValueChange={onSelectSpeaker}>
            <SelectTrigger className="w-[180px] h-9 bg-background/50">
              <div className="flex items-center gap-2">
                <SpeakerIcon className="h-4 w-4 text-muted-foreground" />
                <SelectValue placeholder="Select speaker" />
              </div>
            </SelectTrigger>
            <SelectContent>
              {/* Browser audio option */}
              <SelectItem value={BROWSER_SPEAKER_ID}>
                <div className="flex items-center gap-2">
                  <Monitor className="h-4 w-4" />
                  <span>Browser Audio</span>
                </div>
              </SelectItem>

              {/* Chromecast speakers */}
              {speakers
                .filter((s) => s.type === "chromecast")
                .map((speaker) => (
                  <SelectItem key={speaker.id} value={speaker.id}>
                    <div className="flex items-center gap-2">
                      <Tv className="h-4 w-4" />
                      <span className="truncate">{speaker.name}</span>
                    </div>
                  </SelectItem>
                ))}

              {/* LMS speakers */}
              {speakers
                .filter((s) => s.type === "lms")
                .map((speaker) => (
                  <SelectItem key={speaker.id} value={speaker.id}>
                    <div className="flex items-center gap-2">
                      <Music2 className="h-4 w-4" />
                      <span className="truncate">{speaker.name}</span>
                    </div>
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>

        {/* Center section - empty, for balance */}
        <div className="flex-1" />

        {/* Backend connection status */}
        {backendStatus && (
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                className={cn(
                  "flex items-center gap-1.5 px-2 py-1 rounded-md text-xs",
                  backendStatus.isConnected
                    ? "text-green-500"
                    : "text-red-500 bg-red-500/10"
                )}
              >
                {backendStatus.isConnected ? (
                  <Wifi className="h-3.5 w-3.5" />
                ) : (
                  <WifiOff className="h-3.5 w-3.5" />
                )}
                {!backendStatus.isConnected && (
                  <span className="hidden sm:inline">Disconnected</span>
                )}
              </div>
            </TooltipTrigger>
            <TooltipContent>
              {backendStatus.isConnected
                ? `Connected${backendStatus.latency ? ` (${backendStatus.latency}ms)` : ""}`
                : "Backend disconnected - check server status"}
            </TooltipContent>
          </Tooltip>
        )}

        {/* Right section - Volume control */}
        <div className="flex items-center gap-3 min-w-[200px] justify-end">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={handleMuteToggle}
                className="text-muted-foreground hover:text-foreground"
              >
                {isMuted || volume === 0 ? (
                  <VolumeX className="h-4 w-4" />
                ) : (
                  <Volume2 className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {isMuted ? "Unmute" : "Mute"}
            </TooltipContent>
          </Tooltip>

          <Slider
            value={[isMuted ? 0 : volume]}
            onValueChange={handleVolumeChange}
            max={1}
            step={0.01}
            className="w-[120px]"
            aria-label="Volume"
          />

          <span className="text-xs text-muted-foreground w-8 text-right tabular-nums">
            {Math.round((isMuted ? 0 : volume) * 100)}%
          </span>
        </div>
      </div>
    </TooltipProvider>
  )
}
