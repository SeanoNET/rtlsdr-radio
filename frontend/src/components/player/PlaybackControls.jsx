import * as React from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Play, Pause, Square, Loader2, SkipBack, SkipForward } from "lucide-react"

export function PlaybackControls({
  isPlaying,
  isPaused,
  loading,
  disabled,
  onPlay,
  onPause,
  onStop,
  onResume,
  onPrevious,
  onNext,
  showSkipControls = false,
  className,
}) {
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

        {/* Main Play/Pause/Resume button */}
        {isPlaying ? (
          <>
            {/* Pause */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="secondary"
                  size="icon"
                  onClick={onPause}
                  disabled={loading}
                  className="h-12 w-12 rounded-full bg-yellow-600 hover:bg-yellow-500 text-white"
                >
                  <Pause className="h-6 w-6" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Pause</TooltipContent>
            </Tooltip>

            {/* Stop */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="secondary"
                  size="icon"
                  onClick={onStop}
                  disabled={loading}
                  className="h-12 w-12 rounded-full bg-red-600 hover:bg-red-500 text-white"
                >
                  <Square className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Stop</TooltipContent>
            </Tooltip>
          </>
        ) : isPaused ? (
          <>
            {/* Resume */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="secondary"
                  size="icon"
                  onClick={onResume}
                  disabled={loading}
                  className="h-14 w-14 rounded-full bg-green-600 hover:bg-green-500 text-white"
                >
                  <Play className="h-7 w-7 ml-0.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Resume</TooltipContent>
            </Tooltip>

            {/* Stop */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="secondary"
                  size="icon"
                  onClick={onStop}
                  disabled={loading}
                  className="h-12 w-12 rounded-full bg-red-600 hover:bg-red-500 text-white"
                >
                  <Square className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Stop</TooltipContent>
            </Tooltip>
          </>
        ) : (
          /* Play */
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
