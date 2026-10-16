import React from 'react'
import { Download, Layers, Map } from 'lucide-react'
import { cn } from '../../lib/utils'

interface MapFrameProps {
  title?: string
  live?: boolean
  children: React.ReactNode
  attribution?: string
  lastRefresh?: string
  onExport?: () => void
  onLayerSettings?: () => void
  className?: string
}

export function MapFrame({
  title = 'Lebanon, NH · Incidents',
  live = false,
  children,
  attribution = '© OpenStreetMap · Lebanon GIS',
  lastRefresh,
  onExport,
  onLayerSettings,
  className,
}: MapFrameProps) {
  return (
    <div
      className={cn(
        'flex flex-col overflow-hidden rounded-lg border border-border bg-card text-card-foreground',
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2.5">
        <div className="flex items-center gap-2">
          <Map size={14} />
          <span className="text-[13px] font-semibold text-foreground">{title}</span>
          {live && (
            <span className="inline-flex items-center gap-1 rounded-full border border-border/40 bg-secondary px-1.5 text-[10px] font-semibold text-secondary-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-current" />
              Live
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {onExport && (
            <button
              onClick={onExport}
              className="inline-flex h-7 items-center gap-1.5 rounded-[calc(var(--radius)-4px)] border border-border bg-transparent px-2.5 text-xs font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              <Download size={12} />
              Export
            </button>
          )}
          {onLayerSettings && (
            <button
              onClick={onLayerSettings}
              title="Layer settings"
              className="inline-flex h-7 w-7 items-center justify-center rounded-[calc(var(--radius)-4px)] border border-transparent bg-transparent text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              <Layers size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Map area */}
      <div className="flex-1 overflow-hidden">{children}</div>

      {/* Footer */}
      {(attribution || lastRefresh) && (
        <div className="flex items-center justify-between border-t border-border bg-muted px-3 py-1.5 text-[11px] text-muted-foreground">
          {attribution && <span>{attribution}</span>}
          {lastRefresh && <span>{lastRefresh}</span>}
        </div>
      )}
    </div>
  )
}
