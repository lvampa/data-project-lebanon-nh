import type { Meta, StoryObj } from '@storybook/react-vite'
import { StatCard } from './stat-card'

const meta: Meta<typeof StatCard> = {
  component: StatCard,
  title: 'Data/StatCard',
}
export default meta

type Story = StoryObj<typeof StatCard>

const TREND = [38, 44, 51, 47, 62, 55, 48, 71, 66, 59, 43, 38]

export const Default: Story = {
  args: {
    label: 'Total incidents',
    value: '511',
    delta: 4.2,
    deltaLabel: 'vs. last quarter',
    sparkline: TREND,
    footnote: 'Provisional · Updated daily from LPD CAD',
  },
}

export const Negative: Story = {
  args: {
    label: 'Avg. response time',
    value: '4.8',
    unit: 'min',
    delta: -2.1,
    deltaLabel: 'vs. last year',
    invertDeltaPolarity: true,
  },
}

export const Grid: Story = {
  render: () => (
    <div className="grid grid-cols-3 gap-4 w-[700px]">
      <StatCard label="Total incidents" value="511" delta={4.2} deltaLabel="vs. last quarter" sparkline={TREND} />
      <StatCard label="Operating budget" value="$61.4M" delta={4.2} deltaLabel="FY24 vs FY23" />
      <StatCard label="SAU88 enrollment" value="3,402" delta={-1.8} deltaLabel="vs. last year" sparkline={[3502, 3480, 3450, 3421, 3402]} />
    </div>
  ),
}
