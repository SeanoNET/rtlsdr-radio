import * as React from "react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Plus, Search, Radio, Waves, Loader2, ChevronLeft, ChevronRight } from "lucide-react"

export function RightSidebar({
  dabChannels = [],
  selectedDabChannel,
  onSelectDabChannel,
  dabPrograms = [],
  scanning,
  onScan,
  onAddProgram,
  frequency,
  onFrequencyChange,
  newStation,
  onNewStationChange,
  onAddStation,
  className,
}) {
  const [isCollapsed, setIsCollapsed] = React.useState(false)

  // Collapsed state - just show a thin bar with toggle button
  if (isCollapsed) {
    return (
      <TooltipProvider>
        <aside
          className={cn(
            "w-10 border-l border-sidebar-border bg-sidebar flex flex-col items-center py-4",
            className
          )}
        >
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsCollapsed(false)}
                className="h-8 w-8"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left">
              Expand Add Stations panel
            </TooltipContent>
          </Tooltip>

          <div className="mt-4 space-y-3">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsCollapsed(false)}
                  className="h-8 w-8"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left">Add Station</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsCollapsed(false)}
                  className="h-8 w-8"
                >
                  <Radio className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left">FM Tuning</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsCollapsed(false)}
                  className="h-8 w-8"
                >
                  <Waves className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left">DAB+ Scanner</TooltipContent>
            </Tooltip>
          </div>
        </aside>
      </TooltipProvider>
    )
  }

  return (
    <aside
      className={cn(
        "w-[280px] border-l border-sidebar-border bg-sidebar flex flex-col",
        className
      )}
    >
      {/* Header with collapse button */}
      <div className="p-4 border-b border-sidebar-border flex items-center justify-between">
        <h2 className="text-lg font-semibold text-sidebar-foreground flex items-center gap-2">
          <Plus className="h-5 w-5" />
          Add Stations
        </h2>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsCollapsed(true)}
                className="h-7 w-7"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Collapse panel</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6">
          {/* Add New Station Form */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">New Station</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Station Type */}
              <div className="space-y-1.5">
                <Label htmlFor="stationType" className="text-xs">Type</Label>
                <Select
                  value={newStation?.type || "fm"}
                  onValueChange={(value) =>
                    onNewStationChange({ ...newStation, type: value })
                  }
                >
                  <SelectTrigger id="stationType" className="h-8 text-sm">
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fm">
                      <span className="flex items-center gap-2">
                        <Radio className="h-3.5 w-3.5" />
                        FM Radio
                      </span>
                    </SelectItem>
                    <SelectItem value="dab">
                      <span className="flex items-center gap-2">
                        <Waves className="h-3.5 w-3.5" />
                        DAB+
                      </span>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Station Name */}
              <div className="space-y-1.5">
                <Label htmlFor="stationName" className="text-xs">Name</Label>
                <Input
                  id="stationName"
                  placeholder="Station name"
                  value={newStation?.name || ""}
                  onChange={(e) =>
                    onNewStationChange({ ...newStation, name: e.target.value })
                  }
                  className="h-8 text-sm"
                />
              </div>

              {/* Type-specific fields */}
              {newStation?.type === "fm" || !newStation?.type ? (
                <div className="space-y-1.5">
                  <Label htmlFor="stationFreq" className="text-xs">
                    Frequency (MHz)
                  </Label>
                  <Input
                    id="stationFreq"
                    type="number"
                    step="0.1"
                    min="87.5"
                    max="108"
                    placeholder="e.g. 101.1"
                    value={newStation?.frequency || ""}
                    onChange={(e) =>
                      onNewStationChange({
                        ...newStation,
                        frequency: e.target.value,
                      })
                    }
                    className="h-8 text-sm"
                  />
                </div>
              ) : (
                <>
                  <div className="space-y-1.5">
                    <Label htmlFor="stationChannel" className="text-xs">
                      DAB Channel
                    </Label>
                    <Input
                      id="stationChannel"
                      placeholder="e.g. 9B"
                      value={newStation?.channel || ""}
                      onChange={(e) =>
                        onNewStationChange({
                          ...newStation,
                          channel: e.target.value,
                        })
                      }
                      className="h-8 text-sm"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="stationProgram" className="text-xs">
                      Program Name
                    </Label>
                    <Input
                      id="stationProgram"
                      placeholder="e.g. BBC Radio 1"
                      value={newStation?.program || ""}
                      onChange={(e) =>
                        onNewStationChange({
                          ...newStation,
                          program: e.target.value,
                        })
                      }
                      className="h-8 text-sm"
                    />
                  </div>
                </>
              )}

              <Button
                onClick={onAddStation}
                className="w-full h-8 text-sm"
                size="sm"
              >
                <Plus className="h-3.5 w-3.5 mr-1.5" />
                Add Station
              </Button>
            </CardContent>
          </Card>

          <Separator className="bg-border/50" />

          {/* FM Manual Tuning */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Radio className="h-4 w-4" />
                FM Tuning
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1.5">
                <Label htmlFor="manualFreq" className="text-xs">
                  Frequency (MHz)
                </Label>
                <div className="flex gap-2">
                  <Input
                    id="manualFreq"
                    type="number"
                    step="0.1"
                    min="87.5"
                    max="108"
                    placeholder="101.1"
                    value={frequency || ""}
                    onChange={(e) => onFrequencyChange(parseFloat(e.target.value))}
                    className="h-8 text-sm"
                  />
                  <span className="flex items-center text-sm text-muted-foreground">
                    MHz
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Separator className="bg-border/50" />

          {/* DAB+ Scanner */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Waves className="h-4 w-4" />
                DAB+ Scanner
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="dabChannel" className="text-xs">
                  Select Channel
                </Label>
                <div className="flex gap-2">
                  <Select
                    value={selectedDabChannel || ""}
                    onValueChange={onSelectDabChannel}
                  >
                    <SelectTrigger id="dabChannel" className="h-8 text-sm flex-1">
                      <SelectValue placeholder="Choose channel" />
                    </SelectTrigger>
                    <SelectContent>
                      {dabChannels.map((channel) => (
                        <SelectItem key={channel.id} value={channel.id}>
                          {channel.id} ({channel.frequency} MHz)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    onClick={onScan}
                    disabled={!selectedDabChannel || scanning}
                    size="sm"
                    className="h-8"
                  >
                    {scanning ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Search className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>
              </div>

              {/* Scan Results */}
              {dabPrograms.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">
                    Found {dabPrograms.length} program{dabPrograms.length !== 1 ? "s" : ""}
                  </Label>
                  <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
                    {dabPrograms.map((program) => (
                      <div
                        key={program.service_id}
                        className="flex items-center justify-between p-2 rounded-md bg-muted/50 text-sm"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="font-medium truncate text-xs">
                            {program.name}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {program.bitrate}kbps
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onAddProgram(program)}
                          className="h-7 px-2 text-xs"
                        >
                          <Plus className="h-3 w-3 mr-1" />
                          Add
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </ScrollArea>
    </aside>
  )
}
