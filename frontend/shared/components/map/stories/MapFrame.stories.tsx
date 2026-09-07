import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { MapFrame } from '../MapFrame'
import { MapSurfacePlaceholder } from '../MapLoadingState'

export default {
  title: 'Map/Frame',
  decorators: [
    (Story) => (
      <div style={{ width: 600, height: 420 }}>
        <Story />
      </div>
    ),
  ],
} satisfies StoryDefault

type MapFrameProps = ComponentProps<typeof MapFrame>

const PlaceholderMap = () => (
  <MapSurfacePlaceholder style={{ width: '100%', height: '100%' }} />
)

export const Default: Story<MapFrameProps> = (props) => <MapFrame {...props} />
Default.args = {
  title: 'Lebanon, NH · Incidents',
  children: <PlaceholderMap />,
  attribution: '© OpenStreetMap · Lebanon GIS · DHMC EMS',
  lastRefresh: 'Last refresh 2 min ago',
}

export const Live: Story<MapFrameProps> = (props) => <MapFrame {...props} />
Live.args = {
  title: 'Lebanon, NH · Incidents',
  live: true,
  children: <PlaceholderMap />,
  attribution: '© OpenStreetMap · Lebanon GIS',
  lastRefresh: 'Last refresh just now',
  onExport: () => {},
  onLayerSettings: () => {},
}

export const NoFooter: Story<MapFrameProps> = (props) => <MapFrame {...props} />
NoFooter.args = {
  title: 'Lebanon, NH · Incidents',
  children: <PlaceholderMap />,
}

export const WithActions: Story<MapFrameProps> = (props) => <MapFrame {...props} />
WithActions.args = {
  title: 'Lebanon, NH · Incidents',
  live: true,
  children: <PlaceholderMap />,
  attribution: '© OpenStreetMap',
  lastRefresh: 'Updated 5 min ago',
  onExport: () => alert('Export'),
  onLayerSettings: () => alert('Settings'),
}
