import type { Meta, StoryObj } from '@storybook/react-vite'
import { MapLegend } from './MapLegend'

const meta: Meta<typeof MapLegend> = {
  component: MapLegend,
  title: 'Map/Legend',
  decorators: [
    (Story) => (
      <div style={{
        background: 'radial-gradient(circle at 12px 12px, rgba(0,0,0,0.12) 1px, transparent 1.5px), oklch(0.970 0 0)',
        backgroundSize: '24px 24px',
        padding: 24,
        borderRadius: 8,
        display: 'inline-flex',
      }}>
        <Story />
      </div>
    ),
  ],
}
export default meta

type Story = StoryObj<typeof MapLegend>

export const Stacked: Story = {
  args: {
    variant: 'stacked',
    total: 511,
    status: 'Verified',
    lastUpdated: 'Updated 2 min ago',
  },
}

export const Inline: Story = {
  args: {
    variant: 'inline',
  },
  decorators: [
    (Story) => (
      <div style={{
        background: 'radial-gradient(circle at 12px 12px, rgba(0,0,0,0.12) 1px, transparent 1.5px), oklch(0.970 0 0)',
        backgroundSize: '24px 24px',
        padding: 24,
        borderRadius: 8,
      }}>
        <Story />
      </div>
    ),
  ],
}

export const CustomCategories: Story = {
  args: {
    variant: 'stacked',
    total: 843,
    categories: [
      { label: 'Assault',   count: 28,  colorVar: '--chart-1' },
      { label: 'Theft',     count: 156, colorVar: '--chart-2' },
      { label: 'Vandalism', count: 44,  colorVar: '--chart-3' },
      { label: 'Other',     count: 615, colorVar: '--chart-4' },
    ],
    status: 'Provisional',
    lastUpdated: 'Updated 1 hr ago',
  },
}
