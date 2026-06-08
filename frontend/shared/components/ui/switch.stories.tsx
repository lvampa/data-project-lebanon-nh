import type { Meta, StoryObj } from '@storybook/react-vite'
import { Switch } from './switch'

const meta: Meta<typeof Switch> = {
  component: Switch,
  title: 'Forms/Switch',
}
export default meta

type Story = StoryObj<typeof Switch>

export const Default: Story = { args: { label: 'Show incidents' } }
export const WithDescription: Story = {
  args: { label: 'Live updates', description: 'Refresh map data every 30 seconds', defaultChecked: true },
}
export const Sizes: Story = {
  render: () => (
    <div className="flex flex-col gap-4">
      <Switch size="sm" label="Small" />
      <Switch size="md" label="Medium" defaultChecked />
    </div>
  ),
}
export const Disabled: Story = { args: { label: 'Disabled toggle', disabled: true, defaultChecked: true } }
export const CategoryToggles: Story = {
  render: () => (
    <div className="flex flex-col gap-3 w-48">
      {['Fire', 'Medical', 'Traffic', 'Utility', 'Police'].map((cat, i) => (
        <Switch key={cat} label={cat} defaultChecked={i < 3} />
      ))}
    </div>
  ),
}
