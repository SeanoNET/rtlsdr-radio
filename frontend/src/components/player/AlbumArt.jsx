import * as React from "react"
import { cn } from "@/lib/utils"
import { Radio } from "lucide-react"

export function AlbumArt({
  imageUrl,
  motImage,
  motContentType,
  stationName,
  size = "lg",
  className,
}) {
  const sizeClasses = {
    sm: "w-16 h-16",
    md: "w-24 h-24",
    lg: "w-48 h-48",
    xl: "w-64 h-64",
    "2xl": "w-80 h-80",
  }

  // Priority: MOT slideshow > Station image > Placeholder
  const getImageSrc = () => {
    if (motImage) {
      return `data:${motContentType || "image/jpeg"};base64,${motImage}`
    }
    return imageUrl
  }

  const imageSrc = getImageSrc()

  return (
    <div
      className={cn(
        "relative rounded-xl overflow-hidden shadow-2xl",
        "bg-gradient-to-br from-purple-600/20 to-blue-600/20",
        "border border-white/10",
        sizeClasses[size],
        className
      )}
    >
      {imageSrc ? (
        <img
          src={imageSrc}
          alt={stationName || "Station"}
          className="w-full h-full object-cover"
          onError={(e) => {
            // Hide broken images and show placeholder
            e.target.style.display = "none"
          }}
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <Radio
            className={cn(
              "text-muted-foreground/50",
              size === "sm" && "w-6 h-6",
              size === "md" && "w-10 h-10",
              size === "lg" && "w-16 h-16",
              size === "xl" && "w-20 h-20",
              size === "2xl" && "w-24 h-24"
            )}
          />
        </div>
      )}

      {/* Overlay gradient for better text visibility */}
      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/40 to-transparent" />
    </div>
  )
}
