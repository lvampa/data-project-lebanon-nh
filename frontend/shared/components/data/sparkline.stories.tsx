import type { Meta, StoryObj } from '@storybook/react-vite'
import { Sparkline } from './sparkline'

const meta: Meta<typeof Sparkline> = {
  component: Sparkline,
  title: 'Data/Sparkline',
}
export default meta

type Story = StoryObj<typeof Sparkline>

const INCIDENT_COUNTS = [38, 44, 51, 47, 62, 55, 48, 71, 66, 59, 43, 38]

export const Default: Story = { args: { values: INCIDENT_COUNTS } }
export const NoDot: Story = { args: { values: INCIDENT_COUNTS, showLast: false } }
export const NoFill: Story = { args: { values: INCIDENT_COUNTS, filled: false } }
export const Sizes: Story = {
  render: () => (
    <div className="flex items-end gap-6">
      <Sparkline values={INCIDENT_COUNTS} width={80} height={24} />
      <Sparkline values={INCIDENT_COUNTS} width={120} height={36} />
      <Sparkline values={INCIDENT_COUNTS} width={160} height={48} />
    </div>
  ),
}
