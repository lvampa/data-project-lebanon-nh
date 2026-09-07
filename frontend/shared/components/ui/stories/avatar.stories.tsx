import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { Avatar } from '../avatar'

export default {
  title: 'Navigation/Avatar',
} satisfies StoryDefault

type AvatarProps = ComponentProps<typeof Avatar>

export const Default: Story<AvatarProps> = (props) => <Avatar {...props} />
Default.args = { name: 'Benjamin Begin' }

export const Sizes: Story = () => (
  <div className="flex items-center gap-3">
    <Avatar name="Benjamin Begin" size={24} />
    <Avatar name="Jodi Dumayne" size={32} />
    <Avatar name="James Pike" size={40} />
    <Avatar name="Eric Blaine" size={48} />
  </div>
)

export const MultipleOfficers: Story = () => (
  <div className="flex items-center gap-2">
    {['Benjamin Begin', 'Jodi Dumayne', 'James Pike', 'Eric Blaine', 'Abagayle Hamelin'].map((name) => (
      <Avatar key={name} name={name} size={32} />
    ))}
  </div>
)
