import type { Meta, StoryObj } from '@storybook/react-vite'
import { MapControls } from './MapControls'

const meta: Meta<typeof MapControls> = {
  component: MapControls,
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
}
export default meta

type Story = StoryObj<typeof MapControls>

export const Default: Story = {
  args: {
    onZoomIn: () => {},
    onZoomOut: () => {},
    onRecenter: () => {},
    onLocate: () => {},
    onFullscreen: () => {},
  },
}

export const LocateActive: Story = {
  args: {
    onZoomIn: () => {},
    onZoomOut: () => {},
    onRecenter: () => {},
    onLocate: () => {},
    onFullscreen: () => {},
    locateActive: true,
  },
}

export const FullscreenActive: Story = {
  args: {
    onZoomIn: () => {},
    onZoomOut: () => {},
    onRecenter: () => {},
    onLocate: () => {},
    onFullscreen: () => {},
    fullscreenActive: true,
  },
}

export const ZoomInDisabled: Story = {
  args: {
    onZoomIn: () => {},
    onZoomOut: () => {},
    onRecenter: () => {},
    onLocate: () => {},
    onFullscreen: () => {},
    zoomInDisabled: true,
  },
}
