import * as React from "react"
import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ExternalLink, Image, Radio, RefreshCw } from "lucide-react"
import { getImageUrl } from "@/lib/api"

export function EditStationDialog({
  station,
  open,
  onOpenChange,
  onSave,
  onRefreshLogo,
}) {
  const [name, setName] = useState("")
  const [imageUrl, setImageUrl] = useState("")
  const [previewError, setPreviewError] = useState(false)
  const [saving, setSaving] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  // Reset form when station changes
  useEffect(() => {
    if (station) {
      setName(station.name || "")
      setImageUrl(station.image_url || "")
      setPreviewError(false)
    }
  }, [station])

  const handleSave = async () => {
    if (!station) return
    setSaving(true)
    try {
      await onSave(station.id, { name, image_url: imageUrl || null })
      onOpenChange(false)
    } finally {
      setSaving(false)
    }
  }

  const handleRefreshLogo = async () => {
    if (!station || !onRefreshLogo) return
    setRefreshing(true)
    try {
      const updatedStation = await onRefreshLogo(station.id)
      if (updatedStation?.image_url) {
        setImageUrl(updatedStation.image_url)
        setPreviewError(false)
      }
    } finally {
      setRefreshing(false)
    }
  }

  const handleClearLogo = () => {
    setImageUrl("")
    setPreviewError(false)
  }

  // Build RadioBrowser search URL
  const radioBrowserSearchUrl = station
    ? `https://www.radio-browser.info/search?name=${encodeURIComponent(station.name)}`
    : "#"

  // Get preview URL
  const previewUrl = imageUrl ? getImageUrl(imageUrl) : null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Edit Station</DialogTitle>
          <DialogDescription>
            Update station details and logo. You can search RadioBrowser for the
            correct logo.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Station Name */}
          <div className="grid gap-2">
            <Label htmlFor="name">Station Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Station name"
            />
          </div>

          {/* Logo Preview */}
          <div className="grid gap-2">
            <Label>Current Logo</Label>
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-lg overflow-hidden bg-muted flex items-center justify-center flex-shrink-0 border">
                {previewUrl && !previewError ? (
                  <img
                    src={previewUrl}
                    alt={name}
                    className="w-full h-full object-cover"
                    onError={() => setPreviewError(true)}
                  />
                ) : (
                  <Radio className="h-8 w-8 text-muted-foreground" />
                )}
              </div>
              <div className="flex-1 text-sm text-muted-foreground">
                {previewUrl && !previewError
                  ? "Logo loaded successfully"
                  : previewUrl && previewError
                  ? "Failed to load logo"
                  : "No logo set"}
              </div>
            </div>
          </div>

          {/* Logo URL */}
          <div className="grid gap-2">
            <Label htmlFor="imageUrl">Logo URL</Label>
            <Input
              id="imageUrl"
              value={imageUrl}
              onChange={(e) => {
                setImageUrl(e.target.value)
                setPreviewError(false)
              }}
              placeholder="https://example.com/logo.png"
            />
            <p className="text-xs text-muted-foreground">
              Paste a direct link to the station logo image
            </p>
          </div>

          {/* RadioBrowser Link */}
          <div className="flex flex-col gap-2">
            <Label>Find Logo on RadioBrowser</Label>
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => window.open(radioBrowserSearchUrl, "_blank")}
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                Search RadioBrowser
              </Button>
              <Button
                variant="outline"
                onClick={handleRefreshLogo}
                disabled={refreshing}
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Search for your station, right-click the logo, and copy the image
              address. Paste it in the Logo URL field above.
            </p>
          </div>

          {/* Clear Logo */}
          {imageUrl && (
            <Button variant="ghost" size="sm" onClick={handleClearLogo}>
              <Image className="h-4 w-4 mr-2" />
              Remove Logo
            </Button>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || !name.trim()}>
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
