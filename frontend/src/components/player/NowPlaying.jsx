import * as React from "react"
import { cn } from "@/lib/utils"
import { getImageUrl } from "@/lib/api"
import { AlbumArt } from "./AlbumArt"
import { MetadataDisplay } from "./MetadataDisplay"
import { PlaybackControls } from "./PlaybackControls"

export function NowPlaying({
  station,
  isPlaying,
  isPaused,
  loading,
  disabled,
  // DAB+ metadata
  dabMetadata,
  // Playback handlers
  onPlay,
  onPause,
  onStop,
  onResume,
  // Optional skip controls
  onPrevious,
  onNext,
  showSkipControls = false,
  className,
}) {
  const isDAB = station?.station_type === "dab"

  // Get display values
  const stationName =
    dabMetadata?.program || station?.name || (isPlaying ? "Radio" : "Not Playing")
  const frequency = station?.frequency
  const dabChannel = station?.dab_channel || dabMetadata?.channel

  // Get image
  const imageUrl = station?.image_url ? getImageUrl(station.image_url) : null

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-6 p-8",
        className
      )}
    >
      {/* Album Art */}
      <AlbumArt
        imageUrl={imageUrl}
        motImage={dabMetadata?.mot_image}
        motContentType={dabMetadata?.mot_content_type}
        stationName={stationName}
        size="2xl"
      />

      {/* Metadata Display */}
      <MetadataDisplay
        stationName={stationName}
        frequency={frequency}
        dabChannel={dabChannel}
        dls={dabMetadata?.dls}
        signal={dabMetadata?.signal}
        audio={dabMetadata?.audio}
        pty={dabMetadata?.pty}
        isDAB={isDAB || !!dabMetadata}
      />

      {/* Playback Controls */}
      <PlaybackControls
        isPlaying={isPlaying}
        isPaused={isPaused}
        loading={loading}
        disabled={disabled}
        onPlay={onPlay}
        onPause={onPause}
        onStop={onStop}
        onResume={onResume}
        onPrevious={onPrevious}
        onNext={onNext}
        showSkipControls={showSkipControls}
      />

      {/* Helper text when stopped */}
      {!isPlaying && !isPaused && disabled && (
        <p className="text-sm text-muted-foreground">
          Select a speaker to start playing
        </p>
      )}
    </div>
  )
}
