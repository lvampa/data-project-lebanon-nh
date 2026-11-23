import { readDataFile } from '@/lib/data'
import { PoliceViews } from '@/components/police-views/police-views'
import type { Address, StatsData } from '@/lib/types'

export default function MapPage() {
  const addresses = readDataFile<Address[]>('addresses.json')
  const stats = readDataFile<StatsData>('stats.json')

  // The map runs the full width of the window, keeping the page's side padding, instead of
  // stopping at the layout's max-w-7xl. The body clips the scrollbar overflow of w-screen.
  // The other tabs keep the layout's width.
  return (
    <div className="relative left-1/2 w-screen -translate-x-1/2 px-5 md:px-8">
      <PoliceViews addresses={addresses} stats={stats} />
    </div>
  )
}
