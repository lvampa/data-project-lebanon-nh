import { fetchLlcs } from '@/lib/api'
import type { Llc } from '@/lib/types'

const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  in_progress: 'bg-blue-100 text-blue-800',
  complete: 'bg-green-100 text-green-800',
  error: 'bg-red-100 text-red-800',
  skipped: 'bg-gray-100 text-gray-600',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[status] ?? 'bg-gray-100'}`}
    >
      {status}
    </span>
  )
}

export default async function LlcsPage() {
  const data = await fetchLlcs()

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">LLC Ownership ({data.total})</h1>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2 pr-4">Name</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2 pr-4">Business Status</th>
              <th className="pb-2 pr-4">Principals</th>
              <th className="pb-2 pr-4">Registered Agent</th>
              <th className="pb-2 pr-4">Email / Phone</th>
              <th className="pb-2">Last Looked Up</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((llc: Llc) => (
              <tr key={llc.id} className="border-b hover:bg-muted/40">
                <td className="py-2 pr-4 font-medium">
                  {llc.nh_business_id ? (
                    <a
                      href={`https://quickstart.sos.nh.gov/online/BusinessInquire/BusinessInformation.aspx?businessID=${llc.nh_business_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-foreground"
                    >
                      {llc.name}
                    </a>
                  ) : (
                    llc.name
                  )}
                </td>
                <td className="py-2 pr-4">
                  <StatusBadge status={llc.lookup_status} />
                </td>
                <td className="py-2 pr-4 text-muted-foreground">{llc.business_status ?? '—'}</td>
                <td className="py-2 pr-4">
                  {llc.principals?.map((p) => (
                    <div key={p.name} className="text-xs">
                      <span className="font-medium">{p.name}</span>
                      <span className="text-muted-foreground"> / {p.title}</span>
                    </div>
                  )) ?? '—'}
                </td>
                <td className="py-2 pr-4 text-xs text-muted-foreground">
                  {llc.registered_agent ?? '—'}
                </td>
                <td className="py-2 pr-4 text-xs">
                  {llc.business_email && <div>{llc.business_email}</div>}
                  {llc.phone && <div className="text-muted-foreground">{llc.phone}</div>}
                  {!llc.business_email && !llc.phone && '—'}
                </td>
                <td className="py-2 text-xs text-muted-foreground">
                  {llc.last_looked_up_at
                    ? new Date(llc.last_looked_up_at).toLocaleDateString()
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
