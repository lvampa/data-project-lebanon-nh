import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { MapLoadingState } from '../MapLoadingState'
import { MapEmptyState } from '../MapEmptyState'
import { MapErrorState } from '../MapErrorState'

export default {
  title: 'Map/States',
  decorators: [
    (Story) => (
      <div style={{ width: 520, height: 340, borderRadius: 8, overflow: 'hidden', border: '1px solid oklch(0.922 0 0)' }}>
        <Story />
      </div>
    ),
  ],
} satisfies StoryDefault

export const Loading: Story<ComponentProps<typeof MapLoadingState>> = (args) => <MapLoadingState {...args} />
Loading.args = {
  progress: '3 of 12 quadrants · ~2 s',
}

export const Empty: Story<ComponentProps<typeof MapEmptyState>> = (args) => <MapEmptyState {...args} />
Empty.args = {
  onResetFilters: () => {},
  onZoomToFit: () => {},
}

export const EmptyNoActions: Story = () => <MapEmptyState />

export const Error: Story<ComponentProps<typeof MapErrorState>> = (args) => <MapErrorState {...args} />
Error.args = {
  onRetry: () => {},
  onViewList: () => {},
  errorDetail: 'tile.lebanon-gis.org · HTTP 503 · 2 attempts',
}

export const ErrorNoActions: Story = () => <MapErrorState title="Map unavailable" message="The map service is temporarily unavailable. Incident data is still accessible in the table below." />
