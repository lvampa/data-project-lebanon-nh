import React from 'react'
import { Plus, Minus, Crosshair, LocateFixed, Maximize2 } from 'lucide-react'

interface MapControlsProps {
  onZoomIn?: () => void
  onZoomOut?: () => void
  onRecenter?: () => void
  onLocate?: () => void
  onFullscreen?: () => void
  locateActive?: boolean
  fullscreenActive?: boolean
  zoomInDisabled?: boolean
  zoomOutDisabled?: boolean
}

export function MapControls({
  onZoomIn,
  onZoomOut,
  onRecenter,
  onLocate,
  onFullscreen,
  locateActive = false,
  fullscreenActive = false,
  zoomInDisabled = false,
  zoomOutDisabled = false,
}: MapControlsProps) {
  return (
    <div
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        padding: 4,
        gap: 2,
        background: 'var(--card)',
        color: 'var(--card-foreground)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        boxShadow: '0 1px 2px rgba(0,0,0,0.06), 0 0 0 4px var(--background)',
      }}
    >
      <ControlButton icon={<Plus size={15} />} label="Zoom in"    onClick={onZoomIn}    disabled={zoomInDisabled} />
      <ControlButton icon={<Minus size={15} />} label="Zoom out"  onClick={onZoomOut}   disabled={zoomOutDisabled} />
      <Divider />
      <ControlButton icon={<Crosshair size={15} />}   label="Recenter"   onClick={onRecenter} />
      <ControlButton icon={<LocateFixed size={15} />} label="Locate me"  onClick={onLocate}   active={locateActive} />
      <Divider />
      <ControlButton icon={<Maximize2 size={15} />}   label="Fullscreen" onClick={onFullscreen} active={fullscreenActive} />
    </div>
  )
}

interface ControlButtonProps {
  icon: React.ReactNode
  label: string
  onClick?: () => void
  disabled?: boolean
  active?: boolean
}

function ControlButton({ icon, label, onClick, disabled = false, active = false }: ControlButtonProps) {
  return (
    <button
      title={label}
      onClick={onClick}
      disabled={disabled}
      style={{
        width: 32,
        height: 32,
        padding: 0,
        border: 'none',
        borderRadius: 'calc(var(--radius) - 4px)',
        background: active ? 'var(--primary)' : 'transparent',
        color: active ? 'var(--primary-foreground)' : disabled ? 'var(--muted-foreground)' : 'var(--foreground)',
        opacity: disabled ? 0.45 : 1,
        display: 'grid',
        placeItems: 'center',
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'background 150ms',
      }}
    >
      {icon}
    </button>
  )
}

function Divider() {
  return <div style={{ height: 1, background: 'var(--border)', margin: '2px 4px' }} />
}
