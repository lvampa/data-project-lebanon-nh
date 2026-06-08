import type { Meta, StoryObj } from '@storybook/react-vite'
import { Tabs } from './tabs'

const ITEMS = [
  { id: 'overview', label: 'Overview', count: 511 },
  { id: 'fire', label: 'Fire', count: 38 },
  { id: 'medical', label: 'Medical', count: 214 },
  { id: 'police', label: 'Police', count: 151 },
]

const meta: Meta<typeof Tabs> = {
  component: Tabs,
  title: 'UI/Tabs',
  argTypes: {
    variant: { control: 'select', options: ['underline', 'pill'] },
  },
}
export default meta

type Story = StoryObj<typeof Tabs>

export const Underline: Story = { args: { items: ITEMS, defaultValue: 'overview', variant: 'underline' } }
export const Pill: Story = { args: { items: ITEMS, defaultValue: 'overview', variant: 'pill' } }
export const Simple: Story = {
  args: {
    items: [
      { id: 'incidents', label: 'Incidents' },
      { id: 'properties', label: 'Properties' },
      { id: 'staff', label: 'City Staff' },
    ],
    defaultValue: 'incidents',
  },
}
