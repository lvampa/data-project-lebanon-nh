import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { Switch } from '../switch'

export default {
  title: 'Forms/Switch',
} satisfies StoryDefault

type SwitchProps = ComponentProps<typeof Switch>

export const Default: Story<SwitchProps> = (props) => <Switch {...props} />
Default.args = { label: 'Show incidents' }

export const WithDescription: Story<SwitchProps> = (props) => <Switch {...props} />
WithDescription.args = { label: 'Live updates', description: 'Refresh map data every 30 seconds', defaultChecked: true }

export const Sizes: Story = () => (
  <div className="flex flex-col gap-4">
    <Switch size="sm" label="Small" />
    <Switch size="md" label="Medium" defaultChecked />
  </div>
)

export const Disabled: Story<SwitchProps> = (props) => <Switch {...props} />
Disabled.args = { label: 'Disabled toggle', disabled: true, defaultChecked: true }

export const CategoryToggles: Story = () => (
  <div className="flex flex-col gap-3 w-48">
    {['Fire', 'Medical', 'Traffic', 'Utility', 'Police'].map((cat, i) => (
      <Switch key={cat} label={cat} defaultChecked={i < 3} />
    ))}
  </div>
)
