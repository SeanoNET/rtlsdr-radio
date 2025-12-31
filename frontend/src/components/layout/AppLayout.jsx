import * as React from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Menu, Radio, Plus } from "lucide-react"

export function AppLayout({
  children,
  leftSidebar,
  rightSidebar,
  bottomBar,
  error,
  onDismissError,
  className,
}) {
  const [leftOpen, setLeftOpen] = React.useState(false)
  const [rightOpen, setRightOpen] = React.useState(false)

  return (
    <div className={cn("flex h-screen flex-col bg-background", className)}>
      {/* Error banner */}
      {error && (
        <div className="flex items-center justify-between bg-destructive/20 border-b border-destructive/30 px-4 py-2 text-sm text-destructive-foreground">
          <span>{error}</span>
          <button
            onClick={onDismissError}
            className="ml-4 text-destructive-foreground/70 hover:text-destructive-foreground transition-colors"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Mobile header with menu buttons */}
      <div className="flex lg:hidden items-center justify-between px-4 py-2 border-b border-border bg-card/50">
        <Sheet open={leftOpen} onOpenChange={setLeftOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Open stations">
              <Radio className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-[280px]">
            {leftSidebar}
          </SheetContent>
        </Sheet>

        <span className="font-semibold text-sm">RTL-SDR Radio</span>

        <Sheet open={rightOpen} onOpenChange={setRightOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Add stations">
              <Plus className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="p-0 w-[280px]">
            {rightSidebar}
          </SheetContent>
        </Sheet>
      </div>

      {/* Main three-column layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar - Stations (hidden on mobile, shown in sheet) */}
        <div className="hidden lg:flex h-full">
          {leftSidebar}
        </div>

        {/* Center panel - Now Playing */}
        <main className="flex-1 overflow-auto">
          <div className="mx-auto max-w-2xl h-full flex flex-col justify-center">
            {children}
          </div>
        </main>

        {/* Right sidebar - Config (hidden on mobile, shown in sheet) */}
        <div className="hidden lg:flex h-full">
          {rightSidebar}
        </div>
      </div>

      {/* Bottom bar - Speaker & Volume */}
      {bottomBar}
    </div>
  )
}
