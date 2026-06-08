import type { Meta, StoryObj } from '@storybook/react-vite'
import { TooltipTrigger } from './tooltip'
import { IconButton } from './icon-button'
import { Info } from 'lucide-react'

const meta: Meta = {
  title: 'UI/Tooltip',
  parameters: { layout: 'padded' },
}
export default meta

export const Default: StoryObj = {
  render: () => (
    <div className="flex gap-8 p-12 justify-center">
      <TooltipTrigger content="Verified · Updated quarterly from SAU88" side="top">
        <IconButton label="Info" variant="outline"><Info /></IconButton>
      </TooltipTrigger>
      <TooltipTrigger content="Export as CSV" side="right">
        <IconButton label="Info" variant="outline"><Info /></IconButton>
      </TooltipTrigger>
      <TooltipTrigger content="Download report" side="bottom">
        <IconButton label="Info" variant="outline"><Info /></IconButton>
      </TooltipTrigger>
    </div>
  ),
}
