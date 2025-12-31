import * as React from "react"
import { cn } from "@/lib/utils"
import { SignalQuality } from "./SignalQuality"

export function MetadataDisplay({
  stationName,
  frequency,
  dabChannel,
  dls,
  signal,
  audio,
  pty,
  isDAB = false,
  className,
}) {
  return (
    <div className={cn("space-y-2 text-center", className)}>
      {/* Station Name */}
      <h2 className="text-2xl font-bold text-foreground truncate">
        {stationName || "Unknown Station"}
      </h2>

      {/* Frequency or Channel */}
      <p className="text-sm text-muted-foreground">
        {isDAB ? (
          dabChannel ? (
            <>DAB+ Channel {dabChannel}</>
          ) : (
            "DAB+ Radio"
          )
        ) : frequency ? (
          <>{frequency} MHz</>
        ) : (
          "FM Radio"
        )}
      </p>

      {/* DLS - Now Playing Text (DAB+ only) */}
      {dls && (
        <p className="text-purple-400 text-sm line-clamp-2 max-w-md mx-auto">
          {dls}
        </p>
      )}

      {/* DAB+ Technical Info */}
      {isDAB && (signal || audio || pty) && (
        <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
          {/* Signal Quality */}
          {signal && <SignalQuality signal={signal} />}

          {/* Audio Mode */}
          {audio?.mode && (
            <span className="text-xs text-muted-foreground">
              {audio.mode}
              {audio.bitrate && ` • ${audio.bitrate}kbps`}
            </span>
          )}

          {/* Program Type */}
          {pty && (
            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
              {pty}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
