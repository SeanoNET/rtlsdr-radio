import * as React from "react"
import { useState, useEffect, useRef } from "react"
import { cn } from "@/lib/utils"
import { SignalQuality } from "./SignalQuality"

/**
 * Scrolling DLS (Dynamic Label Segment) text component.
 * Only scrolls if text overflows the container.
 */
function ScrollingDLS({ text }) {
  const containerRef = useRef(null)
  const textRef = useRef(null)
  const [shouldScroll, setShouldScroll] = useState(false)

  // Check if text overflows container
  useEffect(() => {
    const checkOverflow = () => {
      if (containerRef.current && textRef.current) {
        const containerWidth = containerRef.current.offsetWidth
        const textWidth = textRef.current.scrollWidth
        setShouldScroll(textWidth > containerWidth)
      }
    }

    checkOverflow()
    // Recheck on window resize
    window.addEventListener("resize", checkOverflow)
    return () => window.removeEventListener("resize", checkOverflow)
  }, [text])

  return (
    <div
      ref={containerRef}
      className={cn(
        "dls-container w-48 mx-auto overflow-hidden",
        !shouldScroll && "flex justify-center"
      )}
    >
      <p
        ref={textRef}
        className={cn(
          "text-purple-400 text-sm whitespace-nowrap inline-block",
          shouldScroll && "dls-text"
        )}
      >
        {text}
      </p>
    </div>
  )
}

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

      {/* DLS - Now Playing Text (DAB+ only) - scrolling marquee */}
      {dls && <ScrollingDLS text={dls} />}

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
