import * as React from "react"
import { cn } from "@/lib/utils"

export function SignalQuality({ signal, className }) {
  if (!signal) return null

  const quality = signal.fic_quality || 0
  const snr = signal.snr

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {/* Signal bars */}
      <div className="flex items-end gap-0.5">
        {[1, 2, 3, 4, 5].map((bar) => {
          const isActive = quality >= bar * 20
          return (
            <div
              key={bar}
              className={cn(
                "w-1 rounded-sm transition-colors",
                isActive ? "bg-green-500" : "bg-muted-foreground/30"
              )}
              style={{ height: `${bar * 3 + 4}px` }}
            />
          )
        })}
      </div>

      {/* SNR value */}
      {snr !== null && snr !== undefined && (
        <span className="text-xs text-muted-foreground">
          {snr.toFixed(1)} dB
        </span>
      )}
    </div>
  )
}
