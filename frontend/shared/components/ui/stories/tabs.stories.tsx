import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { Tabs } from '../tabs'

const ITEMS = [
  { id: 'overview', label: 'Overview', count: 511 },
  { id: 'fire', label: 'Fire', count: 38 },
  { id: 'medical', label: 'Medical', count: 214 },
  { id: 'police', label: 'Police', count: 151 },
]

export default {
  title: 'Navigation/Tabs',
  argTypes: {
    variant: { control: { type: 'select' }, options: ['underline', 'pill'] },
  },
} satisfies StoryDefault<TabsProps>

type TabsProps = ComponentProps<typeof Tabs>

export const Underline: Story<TabsProps> = (props) => <Tabs {...props} />
Underline.args = { items: ITEMS, defaultValue: 'overview', variant: 'underline' }

export const Pill: Story<TabsProps> = (props) => <Tabs {...props} />
Pill.args = { items: ITEMS, defaultValue: 'overview', variant: 'pill' }

export const Simple: Story<TabsProps> = (props) => <Tabs {...props} />
Simple.args = {
  items: [
    { id: 'incidents', label: 'Incidents' },
    { id: 'properties', label: 'Properties' },
    { id: 'staff', label: 'City Staff' },
  ],
  defaultValue: 'incidents',
}
