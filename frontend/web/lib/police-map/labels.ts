// Dispatch codes in plain words. The log's own text stays on hover, so a reader can check.
const PLAIN_TYPES: Record<string, string> = {
  'BUSINESS CHECK - CLOSED': 'Business check, after hours',
  'BUSINESS CHECK - OPEN': 'Business check, open hours',
  'FD Alarm Work/Test': 'Fire alarm test or repair',
  'Supervisory Alarm': 'Fire system fault signal',
  'Directed Patrol': 'Directed patrol',
  'FOOT PATROL': 'Foot patrol',
  'Motor Vehicle Stop': 'Traffic stop',
  'MV Complaint': 'Complaint about a driver',
  '911 Hang-Ups/Abandoned Calls': '911 hang-up',
  'Paperwork Service Subpoena': 'Serving a subpoena',
  'Detail Special Outside': 'Paid police detail',
  'Suspicious Incident': 'Something suspicious',
  Arrest: 'Arrest',
  'Welfare Check': 'Welfare check',
  'Assist Motorist': 'Helping a driver',
  'Suspicious Motor Vehicle': 'Suspicious vehicle',
  'Unwanted Subject': 'Unwanted person',
  'Request Info All Others': 'Request for information',
}

// [what to show, what it means]
const PLAIN_OUTCOMES: Record<string, [string, string]> = {
  'Log Information': ['Logged, no action', 'Recorded for the log, no action needed'],
  'Gone on Arrival': ['Gone when police arrived', 'Nobody there by the time police came'],
  'Services Rendered': ['Help given', 'Police gave help or assistance'],
  Investigated: ['Investigated', 'Police looked into it'],
  'Warning Issued': ['Warning given', 'A warning, no ticket or arrest'],
  'Arrest(s) Made': ['Arrest', 'One or more arrests'],
  'Incident Report Taken': ['Report filed', 'A formal report was filed'],
  'Report Taken': ['Report filed', 'A formal report was filed'],
  'Summons Issued': ['Court summons', 'Ordered to appear in court'],
  'False Alarm': ['False alarm', 'The alarm was not real'],
  'Transported/Relayed': ['Transported', 'Someone was taken somewhere, or the call was passed on'],
  'Taken/Referred to Other Agency': ['Passed to another agency', 'Handed to another agency'],
}

function lookup<T>(table: Record<string, T>, key: string): T | undefined {
  const wanted = key.toLowerCase()
  const found = Object.keys(table).find((k) => k.toLowerCase() === wanted)
  return found === undefined ? undefined : table[found]
}

// An incident type in plain words. One with no plain label is the log's own text, with only
// the first letter capitalized instead of the whole thing.
export function plainType(type: string | null): string {
  if (!type) return 'Unknown'
  return lookup(PLAIN_TYPES, type) ?? type.charAt(0) + type.slice(1).toLowerCase()
}

export interface OutcomeLabel {
  label: string
  // What the outcome means, when the log's word needs one.
  hint: string | null
}

export function plainOutcome(disposition: string | null): OutcomeLabel {
  if (!disposition) return { label: 'Not recorded', hint: null }
  const plain = lookup(PLAIN_OUTCOMES, disposition)
  return plain ? { label: plain[0], hint: plain[1] } : { label: disposition, hint: null }
}
