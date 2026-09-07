import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { IconButton } from '../icon-button'
import { Settings, Plus, X, Download } from 'lucide-react'

export default {
  title: 'Forms/IconButton',
  argTypes: {
    variant: { control: { type: 'select' }, options: ['ghost', 'outline', 'primary'] },
    size: { control: { type: 'select' }, options: ['sm', 'md', 'lg'] },
  },
} satisfies StoryDefault<IconButtonProps>

type IconButtonProps = ComponentProps<typeof IconButton>

export const Default: Story<IconButtonProps> = (props) => <IconButton {...props} />
Default.args = { label: 'Settings', children: <Settings /> }

export const Variants: Story = () => (
  <div className="flex items-center gap-2">
    <IconButton label="Ghost" variant="ghost"><Settings /></IconButton>
    <IconButton label="Outline" variant="outline"><Settings /></IconButton>
    <IconButton label="Primary" variant="primary"><Plus /></IconButton>
  </div>
)

export const Sizes: Story = () => (
  <div className="flex items-center gap-2">
    <IconButton label="Small" size="sm"><X /></IconButton>
    <IconButton label="Medium" size="md"><X /></IconButton>
    <IconButton label="Large" size="lg"><X /></IconButton>
  </div>
)

export const Disabled: Story<IconButtonProps> = (props) => <IconButton {...props} />
Disabled.args = { label: 'Download', disabled: true, children: <Download /> }
