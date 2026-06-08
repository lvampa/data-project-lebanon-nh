import type { Meta, StoryObj } from '@storybook/react-vite'
import { MapLoadingState } from './MapLoadingState'
import { MapEmptyState } from './MapEmptyState'
import { MapErrorState } from './MapErrorState'

const meta: Meta = {
  title: 'Map/States',
  decorators: [
    (Story) => (
      <div style={{ width: 520, height: 340, borderRadius: 8, overflow: 'hidden', border: '1px solid oklch(0.922 0 0)' }}>
        <Story />
      </div>
    ),
  ],
}
export default meta

export const Loading: StoryObj<typeof MapLoadingState> = {
  render: (args) => <MapLoadingState {...args} />,
  args: {
    progress: '3 of 12 quadrants · ~2 s',
  },
}

export const Empty: StoryObj<typeof MapEmptyState> = {
  render: (args) => <MapEmptyState {...args} />,
  args: {
    onResetFilters: () => {},
    onZoomToFit: () => {},
  },
}

export const EmptyNoActions: StoryObj<typeof MapEmptyState> = {
  render: () => <MapEmptyState />,
}

export const Error: StoryObj<typeof MapErrorState> = {
  render: (args) => <MapErrorState {...args} />,
  args: {
    onRetry: () => {},
    onViewList: () => {},
    errorDetail: 'tile.lebanon-gis.org · HTTP 503 · 2 attempts',
  },
}

export const ErrorNoActions: StoryObj<typeof MapErrorState> = {
  render: () => <MapErrorState title="Map unavailable" message="The map service is temporarily unavailable. Incident data is still accessible in the table below." />,
}
