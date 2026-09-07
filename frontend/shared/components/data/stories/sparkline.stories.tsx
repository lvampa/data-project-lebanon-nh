import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { Sparkline } from '../sparkline'

export default {
  title: 'Data/Sparkline',
} satisfies StoryDefault

type SparklineProps = ComponentProps<typeof Sparkline>

const INCIDENT_COUNTS = [38, 44, 51, 47, 62, 55, 48, 71, 66, 59, 43, 38]

export const Default: Story<SparklineProps> = (props) => <Sparkline {...props} />
Default.args = { values: INCIDENT_COUNTS }

export const NoDot: Story<SparklineProps> = (props) => <Sparkline {...props} />
NoDot.args = { values: INCIDENT_COUNTS, showLast: false }

export const NoFill: Story<SparklineProps> = (props) => <Sparkline {...props} />
NoFill.args = { values: INCIDENT_COUNTS, filled: false }

export const Sizes: Story = () => (
  <div className="flex items-end gap-6">
    <Sparkline values={INCIDENT_COUNTS} width={80} height={24} />
    <Sparkline values={INCIDENT_COUNTS} width={120} height={36} />
    <Sparkline values={INCIDENT_COUNTS} width={160} height={48} />
  </div>
)
