// An incident type as the log wrote it, in plain words. The log's own text stays on hover.
export function plainType(type: string | null): string {
  if (!type) return 'Unknown'
  return type.charAt(0) + type.slice(1).toLowerCase()
}

export interface OutcomeLabel {
  label: string
  // What the outcome means, when the log's word needs one.
  hint: string | null
}

export function plainOutcome(disposition: string | null): OutcomeLabel {
  return { label: disposition ?? 'Not recorded', hint: null }
}
