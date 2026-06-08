import type { Meta, StoryObj } from '@storybook/react-vite'
import { IconButton } from './icon-button'
import { Settings, Plus, X, Download } from 'lucide-react'

const meta: Meta<typeof IconButton> = {
  component: IconButton,
  title: 'Forms/IconButton',
  argTypes: {
    variant: { control: 'select', options: ['ghost', 'outline', 'primary'] },
    size: { control: 'select', options: ['sm', 'md', 'lg'] },
  },
}
export default meta

type Story = StoryObj<typeof IconButton>

export const Default: Story = { args: { label: 'Settings', children: <Settings /> } }
export const Variants: Story = {
  render: () => (
    <div className="flex items-center gap-2">
      <IconButton label="Ghost" variant="ghost"><Settings /></IconButton>
      <IconButton label="Outline" variant="outline"><Settings /></IconButton>
      <IconButton label="Primary" variant="primary"><Plus /></IconButton>
    </div>
  ),
}
export const Sizes: Story = {
  render: () => (
    <div className="flex items-center gap-2">
      <IconButton label="Small" size="sm"><X /></IconButton>
      <IconButton label="Medium" size="md"><X /></IconButton>
      <IconButton label="Large" size="lg"><X /></IconButton>
    </div>
  ),
}
export const Disabled: Story = { args: { label: 'Download', disabled: true, children: <Download /> } }
