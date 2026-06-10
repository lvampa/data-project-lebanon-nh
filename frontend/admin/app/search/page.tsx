'use client'

import { useState } from 'react'
import { Search } from 'lucide-react'
import { fetchSearch } from '@/lib/api'
import type { SearchResponse, SearchResult } from '@/lib/types'

const ENTITY_LABELS: Record<string, string> = {
  properties: 'Properties',
  incidents: 'Incidents',
  planning_meetings: 'Planning Meetings',
  planning_documents: 'Planning Documents',
  city_staff: 'City Staff',
  officers: 'Officers',
  llcs: 'LLCs',
  budget_line_items: 'Budget Line Items',
  budget_capital_projects: 'Capital Projects',
}

function ResultCard({ result }: { result: SearchResult }) {
  const d = result.data
  const primary =
    (d.location as string) ||
    (d.owner as string) ||
    (d.name as string) ||
    (d.file_name as string) ||
    (d.project_name as string) ||
    (d.description as string) ||
    `ID ${result.id}`

  const secondary =
    (d.incident_type as string) ||
    (d.title as string) ||
    (d.department as string) ||
    (d.fund_name as string) ||
    null

  return (
    <div className="rounded-md border border-border bg-card px-4 py-3">
      <div className="text-[13px] font-medium text-foreground">{primary}</div>
      {secondary && (
        <div className="mt-0.5 text-[12px] text-muted-foreground">{secondary}</div>
      )}
      <div className="mt-1 text-[11px] text-muted-foreground/60">
        score {result.score.toFixed(2)}
      </div>
    </div>
  )
}

function ResultSection({ label, results }: { label: string; results: SearchResult[] }) {
  if (results.length === 0) return null
  return (
    <div>
      <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        {label} ({results.length})
      </h2>
      <div className="flex flex-col gap-2">
        {results.map((r) => (
          <ResultCard key={`${r.entity_type}-${r.id}`} result={r} />
        ))}
      </div>
    </div>
  )
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setSubmittedQuery(query.trim())
    setLoading(true)
    setError(null)
    try {
      const data = await fetchSearch(query.trim())
      setResponse(data)
    } catch (err) {
      console.error(err)
      setError('Search failed. Is the API running?')
    } finally {
      setLoading(false)
    }
  }

  const hasResults = response && Object.values(response.results).some((r) => r.length > 0)

  return (
    <div className="max-w-2xl">
      <h1 className="mb-4 text-2xl font-bold">Search</h1>

      <form onSubmit={handleSubmit} className="mb-6 flex gap-2">
        <div className="relative flex-1">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search"
            placeholder="Search address, person, or keyword…"
            className="w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-[13px] placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="rounded-md bg-foreground px-4 py-2 text-[13px] font-medium text-background disabled:opacity-50"
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {response?.normalized_query && response.normalized_query !== submittedQuery && (
        <p className="mb-4 text-[12px] text-muted-foreground">
          Showing results for <span className="font-medium">{response.normalized_query}</span>
        </p>
      )}

      {error && (
        <p className="mb-4 text-[13px] text-destructive">{error}</p>
      )}

      {response && !hasResults && (
        <p className="text-[13px] text-muted-foreground">No results found for &ldquo;{response.query}&rdquo;.</p>
      )}

      {response && hasResults && (
        <div className="flex flex-col gap-6">
          {Object.entries(ENTITY_LABELS).map(([key, label]) => (
            <ResultSection
              key={key}
              label={label}
              results={response.results[key] ?? []}
            />
          ))}
        </div>
      )}
    </div>
  )
}
