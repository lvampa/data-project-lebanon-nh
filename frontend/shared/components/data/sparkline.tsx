import React from 'react'

interface SparklineProps {
  values: number[]
  width?: number
  height?: number
  color?: string
  filled?: boolean
  showLast?: boolean
  className?: string
}

function buildPath(values: number[], w: number, h: number) {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const step = w / (values.length - 1)
  const pts = values.map((v, i): [number, number] => [
    i * step,
    h - 2 - ((v - min) / span) * (h - 4),
  ])
  const line = 'M ' + pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L ')
  const area = line + ` L ${w} ${h} L 0 ${h} Z`
  const last = pts[pts.length - 1]
  return { line, area, lastX: last[0], lastY: last[1] }
}

export function Sparkline({
  values,
  width = 120,
  height = 32,
  color = 'var(--foreground)',
  filled = true,
  showLast = true,
  className,
}: SparklineProps) {
  if (!values || values.length < 2) return null

  const { line, area, lastX, lastY } = buildPath(values, width, height)

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      aria-hidden
    >
      {filled && <path d={area} fill={color} fillOpacity={0.15} />}
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {showLast && <circle cx={lastX} cy={lastY} r={2.5} fill={color} />}
    </svg>
  )
}
