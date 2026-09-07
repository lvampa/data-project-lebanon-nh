import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { ProgressBar } from '../progress-bar'

export default {
  title: 'Data/ProgressBar',
} satisfies StoryDefault

type ProgressBarProps = ComponentProps<typeof ProgressBar>

export const Default: Story<ProgressBarProps> = (props) => <ProgressBar {...props} />
Default.args = { value: 68, label: 'SAU88 Enrollment', showValue: false }

export const WithValue: Story<ProgressBarProps> = (props) => <ProgressBar {...props} />
WithValue.args = { value: 343, max: 500, label: 'Incidents this quarter', showValue: true }

export const Variants: Story = () => (
  <div className="w-64 flex flex-col gap-4">
    <ProgressBar value={75} label="Primary" variant="primary" />
    <ProgressBar value={60} label="Success" variant="success" />
    <ProgressBar value={45} label="Warning" variant="warning" />
    <ProgressBar value={30} label="Danger" variant="danger" />
  </div>
)

export const Sizes: Story = () => (
  <div className="w-64 flex flex-col gap-4">
    <ProgressBar value={68} label="Small" size="sm" />
    <ProgressBar value={68} label="Medium" size="md" />
  </div>
)
