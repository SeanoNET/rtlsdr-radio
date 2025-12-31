import * as React from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Play, Square, Loader2, SkipBack, SkipForward } from "lucide-react"

export function PlaybackControls({
  isPlaying,
  isPaused,
  loading,
  disabled,
  onPlay,
  onStop,
  onResume,
  onPrevious,
  onNext,
  showSkipControls = false,
  className,
}) {
  // Simplified: either playing/paused (show stop) or stopped (show play)
  const isActive = isPlaying || isPaused

  return (
    <TooltipProvider>
      <div className={cn("flex items-center justify-center gap-4", className)}>
        {/* Previous (optional) */}
        {showSkipControls && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onPrevious}
                disabled={loading || disabled}
                className="text-muted-foreground hover:text-foreground"
              >
                <SkipBack className="h-5 w-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Previous station</TooltipContent>
          </Tooltip>
        )}

        {/* Single Play/Stop toggle */}
        {isActive ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="secondary"
                size="icon"
                onClick={onStop}
                disabled={loading}
                className="h-16 w-16 rounded-full bg-red-600 hover:bg-red-500 text-white transition-transform hover:scale-105"
              >
                <Square className="h-6 w-6" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Stop</TooltipContent>
          </Tooltip>
        ) : (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="secondary"
                size="icon"
                onClick={onPlay}
                disabled={loading || disabled}
                className="h-16 w-16 rounded-full bg-green-600 hover:bg-green-500 text-white transition-transform hover:scale-105"
              >
                {loading ? (
                  <Loader2 className="h-8 w-8 animate-spin" />
                ) : (
                  <Play className="h-8 w-8 ml-1" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {disabled ? "Select a speaker first" : "Play"}
            </TooltipContent>
          </Tooltip>
        )}

        {/* Next (optional) */}
        {showSkipControls && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onNext}
                disabled={loading || disabled}
                className="text-muted-foreground hover:text-foreground"
              >
                <SkipForward className="h-5 w-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Next station</TooltipContent>
          </Tooltip>
        )}
      </div>
    </TooltipProvider>
  )
}
