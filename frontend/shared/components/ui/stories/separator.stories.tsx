import type { Story, StoryDefault } from '@ladle/react'
import { Separator } from '../separator'

export default {
  title: 'Surfaces/Separator',
} satisfies StoryDefault

export const Horizontal: Story = () => (
  <div className="w-64 flex flex-col gap-4">
    <span className="text-sm">Above</span>
    <Separator />
    <span className="text-sm">Below</span>
  </div>
)

export const Vertical: Story = () => (
  <div className="flex h-8 items-center gap-4">
    <span className="text-sm">Left</span>
    <Separator orientation="vertical" />
    <span className="text-sm">Right</span>
  </div>
)
