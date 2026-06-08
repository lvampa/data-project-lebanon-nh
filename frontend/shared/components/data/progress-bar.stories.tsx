import type { Meta, StoryObj } from '@storybook/react-vite'
import { ProgressBar } from './progress-bar'

const meta: Meta<typeof ProgressBar> = {
  component: ProgressBar,
  title: 'Data/ProgressBar',
}
export default meta

type Story = StoryObj<typeof ProgressBar>

export const Default: Story = { args: { value: 68, label: 'SAU88 Enrollment', showValue: false } }
export const WithValue: Story = { args: { value: 343, max: 500, label: 'Incidents this quarter', showValue: true } }
export const Variants: Story = {
  render: () => (
    <div className="w-64 flex flex-col gap-4">
      <ProgressBar value={75} label="Primary" variant="primary" />
      <ProgressBar value={60} label="Success" variant="success" />
      <ProgressBar value={45} label="Warning" variant="warning" />
      <ProgressBar value={30} label="Danger" variant="danger" />
    </div>
  ),
}
export const Sizes: Story = {
  render: () => (
    <div className="w-64 flex flex-col gap-4">
      <ProgressBar value={68} label="Small" size="sm" />
      <ProgressBar value={68} label="Medium" size="md" />
    </div>
  ),
}
