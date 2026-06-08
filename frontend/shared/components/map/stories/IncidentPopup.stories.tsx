import type { Meta, StoryObj } from '@storybook/react-vite'
import { IncidentPopup } from './IncidentPopup'

const meta: Meta<typeof IncidentPopup> = {
  component: IncidentPopup,
  title: 'Map/Popup',
  decorators: [
    (Story) => (
      <div style={{
        background: 'radial-gradient(circle at 12px 12px, rgba(0,0,0,0.12) 1px, transparent 1.5px), oklch(0.970 0 0)',
        backgroundSize: '24px 24px',
        padding: 40,
        borderRadius: 8,
        display: 'flex',
        justifyContent: 'center',
      }}>
        <Story />
      </div>
    ),
  ],
}
export default meta

type Story = StoryObj<typeof IncidentPopup>

export const Default: Story = {
  args: {
    title: 'Structure fire',
    incidentId: 'Incident #LB-2026-0142',
    category: 1,
    fields: [
      { label: 'Reported', value: '14 Jan 2026, 03:42' },
      { label: 'Type', value: 'Residential · single-family' },
      { label: 'Address', value: '184 Mascoma Street' },
      { label: 'Response', value: 'LFD · Engine 1, Engine 2, Tower 1' },
    ],
    status: 'Resolved',
    attribution: 'Source: LFD CAD export',
    onClose: () => {},
    onViewRecord: () => {},
  },
}

export const Medical: Story = {
  args: {
    title: 'Medical emergency',
    incidentId: 'Incident #LB-2026-0201',
    category: 2,
    fields: [
      { label: 'Reported', value: '15 Jan 2026, 08:15' },
      { label: 'Type', value: 'Cardiac — Priority 1' },
      { label: 'Address', value: '42 Hanover Street' },
    ],
    attribution: 'Source: EMS CAD',
    onClose: () => {},
    onViewRecord: () => {},
  },
}

export const NoActions: Story = {
  args: {
    title: 'Traffic stop',
    incidentId: 'Incident #LB-2026-0099',
    category: 3,
    fields: [
      { label: 'Reported', value: '10 Jan 2026, 14:30' },
      { label: 'Address', value: 'Exit 18 · I-89' },
      { label: 'Officer', value: 'Sergeant Pike' },
    ],
  },
}
