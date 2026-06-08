import type { Meta, StoryObj } from '@storybook/react-vite'
import { MapFrame } from './MapFrame'
import { MapSurfacePlaceholder } from './MapLoadingState'

const meta: Meta<typeof MapFrame> = {
  component: MapFrame,
  title: 'Map/MapFrame',
  decorators: [
    (Story) => (
      <div style={{ width: 600, height: 420 }}>
        <Story />
      </div>
    ),
  ],
}
export default meta

type Story = StoryObj<typeof MapFrame>

const PlaceholderMap = () => (
  <MapSurfacePlaceholder style={{ width: '100%', height: '100%' }} />
)

export const Default: Story = {
  args: {
    title: 'Lebanon, NH · Incidents',
    children: <PlaceholderMap />,
    attribution: '© OpenStreetMap · Lebanon GIS · DHMC EMS',
    lastRefresh: 'Last refresh 2 min ago',
  },
}

export const Live: Story = {
  args: {
    title: 'Lebanon, NH · Incidents',
    live: true,
    children: <PlaceholderMap />,
    attribution: '© OpenStreetMap · Lebanon GIS',
    lastRefresh: 'Last refresh just now',
    onExport: () => {},
    onLayerSettings: () => {},
  },
}

export const NoFooter: Story = {
  args: {
    title: 'Lebanon, NH · Incidents',
    children: <PlaceholderMap />,
  },
}

export const WithActions: Story = {
  args: {
    title: 'Lebanon, NH · Incidents',
    live: true,
    children: <PlaceholderMap />,
    attribution: '© OpenStreetMap',
    lastRefresh: 'Updated 5 min ago',
    onExport: () => alert('Export'),
    onLayerSettings: () => alert('Settings'),
  },
}
