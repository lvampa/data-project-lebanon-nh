import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { Button } from '../button'

export default {
  title: 'Forms/Button',
  argTypes: {
    variant: {
      control: { type: 'select' },
      options: ['default', 'outline', 'secondary', 'ghost', 'destructive', 'link'],
    },
    size: {
      control: { type: 'select' },
      options: ['default', 'xs', 'sm', 'lg', 'icon', 'icon-xs', 'icon-sm', 'icon-lg'],
    },
  },
} satisfies StoryDefault<ButtonProps>

type ButtonProps = ComponentProps<typeof Button>

export const Default: Story<ButtonProps> = (props) => <Button {...props} />
Default.args = { children: 'Button' }

export const Outline: Story<ButtonProps> = (props) => <Button {...props} />
Outline.args = { variant: 'outline', children: 'Outline' }

export const Secondary: Story<ButtonProps> = (props) => <Button {...props} />
Secondary.args = { variant: 'secondary', children: 'Secondary' }

export const Ghost: Story<ButtonProps> = (props) => <Button {...props} />
Ghost.args = { variant: 'ghost', children: 'Ghost' }

export const Destructive: Story<ButtonProps> = (props) => <Button {...props} />
Destructive.args = { variant: 'destructive', children: 'Delete' }

export const Sizes: Story = () => (
  <div className="flex items-center gap-2">
    <Button size="xs">XS</Button>
    <Button size="sm">SM</Button>
    <Button size="default">Default</Button>
    <Button size="lg">LG</Button>
  </div>
)

export const Disabled: Story<ButtonProps> = (props) => <Button {...props} />
Disabled.args = { children: 'Disabled', disabled: true }
