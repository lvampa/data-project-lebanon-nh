import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { Tag } from '../tag'

export default {
  title: 'Feedback/Tag',
} satisfies StoryDefault

type TagProps = ComponentProps<typeof Tag>

export const Default: Story<TagProps> = (props) => <Tag {...props} />
Default.args = { children: 'Lebanon, NH' }

export const Removable: Story<TagProps> = (props) => <Tag {...props} />
Removable.args = { children: 'Police', onRemove: () => {} }

export const AllVariants: Story = () => (
  <div className="flex flex-wrap gap-2">
    <Tag>Fire</Tag>
    <Tag>Medical</Tag>
    <Tag onRemove={() => {}}>Traffic</Tag>
    <Tag onRemove={() => {}}>Police</Tag>
  </div>
)
