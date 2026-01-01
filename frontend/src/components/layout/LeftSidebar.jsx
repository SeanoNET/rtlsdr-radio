import * as React from "react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { getImageUrl } from "@/lib/api"
import { Radio, Waves, Trash2, Play, Pencil } from "lucide-react"

export function LeftSidebar({
  stations = [],
  fmStations: propFmStations,
  dabStations: propDabStations,
  selectedStation,
  onSelectStation,
  onPlayStation,
  onDeleteStation,
  onEditStation,
  onModeChange,
  isPlaying,
  className,
}) {
  // Use passed filtered stations or filter locally
  const fmStations = propFmStations || stations.filter((s) => s.station_type === "fm" || !s.station_type)
  const dabStations = propDabStations || stations.filter((s) => s.station_type === "dab")

  return (
    <aside
      className={cn(
        "w-[280px] border-r border-sidebar-border bg-sidebar flex flex-col",
        className
      )}
    >
      {/* Header */}
      <div className="p-4 border-b border-sidebar-border">
        <h2 className="text-lg font-semibold text-sidebar-foreground flex items-center gap-2">
          <Radio className="h-5 w-5" />
          Stations
        </h2>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="dab" onValueChange={onModeChange} className="flex-1 flex flex-col">
        <TabsList className="mx-4 mt-4 grid w-auto grid-cols-2">
          <TabsTrigger value="dab" className="gap-1.5">
            <Waves className="h-3.5 w-3.5" />
            DAB+
            {dabStations.length > 0 && (
              <span className="ml-1 text-xs text-muted-foreground">
                ({dabStations.length})
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="fm" className="gap-1.5">
            <Radio className="h-3.5 w-3.5" />
            FM
            {fmStations.length > 0 && (
              <span className="ml-1 text-xs text-muted-foreground">
                ({fmStations.length})
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        {/* DAB+ Stations */}
        <TabsContent value="dab" className="flex-1 m-0">
          <ScrollArea className="h-full">
            <div className="p-4 space-y-2">
              {dabStations.length === 0 ? (
                <EmptyState type="DAB+" />
              ) : (
                dabStations.map((station) => (
                  <StationCard
                    key={station.id}
                    station={station}
                    isSelected={selectedStation === station.id}
                    isCurrentlyPlaying={isPlaying && selectedStation === station.id}
                    onSelect={() => onSelectStation(station.id)}
                    onPlay={() => onPlayStation?.(station.id)}
                    onEdit={() => onEditStation?.(station)}
                    onDelete={() => onDeleteStation(station.id)}
                  />
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        {/* FM Stations */}
        <TabsContent value="fm" className="flex-1 m-0">
          <ScrollArea className="h-full">
            <div className="p-4 space-y-2">
              {fmStations.length === 0 ? (
                <EmptyState type="FM" />
              ) : (
                fmStations.map((station) => (
                  <StationCard
                    key={station.id}
                    station={station}
                    isSelected={selectedStation === station.id}
                    isCurrentlyPlaying={isPlaying && selectedStation === station.id}
                    onSelect={() => onSelectStation(station.id)}
                    onPlay={() => onPlayStation?.(station.id)}
                    onEdit={() => onEditStation?.(station)}
                    onDelete={() => onDeleteStation(station.id)}
                  />
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </aside>
  )
}

function StationCard({ station, isSelected, isCurrentlyPlaying, onSelect, onPlay, onEdit, onDelete }) {
  const imageUrl = station.image_url ? getImageUrl(station.image_url) : null

  return (
    <div
      onClick={onSelect}
      onDoubleClick={(e) => {
        e.preventDefault()
        onPlay?.()
      }}
      className={cn(
        "group relative flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all",
        "border border-transparent",
        isSelected
          ? "bg-primary/20 border-primary/50"
          : "bg-card/50 hover:bg-card hover:border-border"
      )}
    >
      {/* Station Logo */}
      <div className="relative w-10 h-10 rounded-md overflow-hidden bg-muted flex items-center justify-center flex-shrink-0">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={station.name}
            className="w-full h-full object-cover"
            onError={(e) => {
              e.target.style.display = "none"
            }}
          />
        ) : (
          <Radio className="h-5 w-5 text-muted-foreground" />
        )}
        {/* Subtle playing overlay on logo */}
        {isCurrentlyPlaying && (
          <div className="absolute inset-0 bg-primary/20 ring-2 ring-primary/60 ring-inset rounded-md" />
        )}
      </div>

      {/* Station Info */}
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate">{station.name}</p>
        <p className="text-xs text-muted-foreground truncate">
          {station.station_type === "dab"
            ? `${station.dab_channel}${station.dab_program ? ` • ${station.dab_program}` : ""}`
            : `${station.frequency} MHz`}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        {/* Audio bars animation when playing, play button otherwise */}
        {isCurrentlyPlaying ? (
          <div className="audio-bars mx-2">
            <div className="bar" />
            <div className="bar" />
            <div className="bar" />
            <div className="bar" />
          </div>
        ) : (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={(e) => {
              e.stopPropagation()
              onPlay?.()
            }}
            className={cn(
              "transition-opacity text-muted-foreground hover:text-primary",
              isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100"
            )}
          >
            <Play className="h-4 w-4" />
          </Button>
        )}

        {/* Edit button */}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={(e) => {
            e.stopPropagation()
            onEdit?.()
          }}
          className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
        >
          <Pencil className="h-4 w-4" />
        </Button>

        {/* Delete button */}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
          className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

function EmptyState({ type }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
        {type === "FM" ? (
          <Radio className="h-6 w-6 text-muted-foreground" />
        ) : (
          <Waves className="h-6 w-6 text-muted-foreground" />
        )}
      </div>
      <p className="text-sm text-muted-foreground">No {type} stations saved</p>
      <p className="text-xs text-muted-foreground/70 mt-1">
        Add stations from the panel on the right
      </p>
    </div>
  )
}
