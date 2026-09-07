import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { Badge } from '../badge'

export default {
  title: 'Feedback/Badge',
  argTypes: {
    variant: {
      control: { type: 'select' },
      options: ['default', 'secondary', 'destructive', 'outline', 'ghost', 'link'],
    },
  },
} satisfies StoryDefault<BadgeProps>

type BadgeProps = ComponentProps<typeof Badge>

export const Default: Story<BadgeProps> = (props) => <Badge {...props} />
Default.args = { children: 'Badge' }

export const Secondary: Story<BadgeProps> = (props) => <Badge {...props} />
Secondary.args = { variant: 'secondary', children: 'Secondary' }

export const Destructive: Story<BadgeProps> = (props) => <Badge {...props} />
Destructive.args = { variant: 'destructive', children: 'Error' }

export const Outline: Story<BadgeProps> = (props) => <Badge {...props} />
Outline.args = { variant: 'outline', children: 'Outline' }

export const AllVariants: Story = () => (
  <div className="flex flex-wrap gap-2">
    <Badge>Default</Badge>
    <Badge variant="secondary">Secondary</Badge>
    <Badge variant="destructive">Destructive</Badge>
    <Badge variant="outline">Outline</Badge>
    <Badge variant="ghost">Ghost</Badge>
  </div>
)
