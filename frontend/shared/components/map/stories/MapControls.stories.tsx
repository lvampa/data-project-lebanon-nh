import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { MapControls } from '../MapControls'

export default {
  title: 'Map/Controls',
  decorators: [
    (Story) => (
      <div style={{
        background: 'radial-gradient(circle at 12px 12px, rgba(0,0,0,0.12) 1px, transparent 1.5px), oklch(0.970 0 0)',
        backgroundSize: '24px 24px',
        padding: 32,
        borderRadius: 8,
        display: 'inline-flex',
      }}>
        <Story />
      </div>
    ),
  ],
} satisfies StoryDefault

type MapControlsProps = ComponentProps<typeof MapControls>

export const Default: Story<MapControlsProps> = (props) => <MapControls {...props} />
Default.args = {
  onZoomIn: () => {},
  onZoomOut: () => {},
  onRecenter: () => {},
  onLocate: () => {},
  onFullscreen: () => {},
}

export const LocateActive: Story<MapControlsProps> = (props) => <MapControls {...props} />
LocateActive.args = {
  onZoomIn: () => {},
  onZoomOut: () => {},
  onRecenter: () => {},
  onLocate: () => {},
  onFullscreen: () => {},
  locateActive: true,
}

export const FullscreenActive: Story<MapControlsProps> = (props) => <MapControls {...props} />
FullscreenActive.args = {
  onZoomIn: () => {},
  onZoomOut: () => {},
  onRecenter: () => {},
  onLocate: () => {},
  onFullscreen: () => {},
  fullscreenActive: true,
}

export const ZoomInDisabled: Story<MapControlsProps> = (props) => <MapControls {...props} />
ZoomInDisabled.args = {
  onZoomIn: () => {},
  onZoomOut: () => {},
  onRecenter: () => {},
  onLocate: () => {},
  onFullscreen: () => {},
  zoomInDisabled: true,
}
