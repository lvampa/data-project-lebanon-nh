import type { Meta, StoryObj } from '@storybook/react-vite'
import { Avatar } from './avatar'

const meta: Meta<typeof Avatar> = {
  component: Avatar,
  title: 'Navigation/Avatar',
}
export default meta

type Story = StoryObj<typeof Avatar>

export const Default: Story = { args: { name: 'Benjamin Begin' } }
export const Sizes: Story = {
  render: () => (
    <div className="flex items-center gap-3">
      <Avatar name="Benjamin Begin" size={24} />
      <Avatar name="Jodi Dumayne" size={32} />
      <Avatar name="James Pike" size={40} />
      <Avatar name="Eric Blaine" size={48} />
    </div>
  ),
}
export const MultipleOfficers: Story = {
  render: () => (
    <div className="flex items-center gap-2">
      {['Benjamin Begin', 'Jodi Dumayne', 'James Pike', 'Eric Blaine', 'Abagayle Hamelin'].map((name) => (
        <Avatar key={name} name={name} size={32} />
      ))}
    </div>
  ),
}
