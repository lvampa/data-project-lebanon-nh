import type { Meta, StoryObj } from '@storybook/react-vite'
import { Checkbox } from './checkbox'

const meta: Meta<typeof Checkbox> = {
  component: Checkbox,
  title: 'UI/Checkbox',
}
export default meta

type Story = StoryObj<typeof Checkbox>

export const Default: Story = { args: { label: 'Show officer names' } }
export const Checked: Story = { args: { label: 'Verified records only', defaultChecked: true } }
export const Indeterminate: Story = { args: { label: 'Select all', indeterminate: true } }
export const WithDescription: Story = {
  args: {
    label: 'Include historical data',
    description: 'Load incidents older than 90 days',
    defaultChecked: false,
  },
}
export const Disabled: Story = { args: { label: 'Admin only', disabled: true, defaultChecked: true } }
