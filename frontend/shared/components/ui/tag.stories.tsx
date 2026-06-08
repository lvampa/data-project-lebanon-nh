import type { Meta, StoryObj } from '@storybook/react-vite'
import { Tag } from './tag'

const meta: Meta<typeof Tag> = {
  component: Tag,
  title: 'UI/Tag',
}
export default meta

type Story = StoryObj<typeof Tag>

export const Default: Story = { args: { children: 'Lebanon, NH' } }
export const Removable: Story = { args: { children: 'Police', onRemove: () => {} } }
export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <Tag>Fire</Tag>
      <Tag>Medical</Tag>
      <Tag onRemove={() => {}}>Traffic</Tag>
      <Tag onRemove={() => {}}>Police</Tag>
    </div>
  ),
}
