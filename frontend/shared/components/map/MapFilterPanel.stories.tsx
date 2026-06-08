import type { Meta, StoryObj } from '@storybook/react-vite'
import { MapFilterPanel } from './MapFilterPanel'

const meta: Meta<typeof MapFilterPanel> = {
  component: MapFilterPanel,
  title: 'Map/MapFilterPanel',
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

type Story = StoryObj<typeof MapFilterPanel>

export const Expanded: Story = {
  args: {
    defaultCollapsed: false,
    onReset: () => {},
    onApply: () => {},
  },
}

export const Collapsed: Story = {
  args: {
    defaultCollapsed: true,
  },
}

export const AllEnabled: Story = {
  args: {
    defaultCollapsed: false,
    categories: [
      { label: 'Fire',    count: 38,  enabled: true, colorVar: '--chart-1' },
      { label: 'Medical', count: 214, enabled: true, colorVar: '--chart-2' },
      { label: 'Traffic', count: 96,  enabled: true, colorVar: '--chart-3' },
      { label: 'Utility', count: 12,  enabled: true, colorVar: '--chart-4' },
      { label: 'Police',  count: 151, enabled: true, colorVar: '--chart-5' },
    ],
    onReset: () => {},
    onApply: () => {},
  },
}
