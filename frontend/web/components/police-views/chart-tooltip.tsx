'use client'
import { useEffect, useRef, useState } from 'react'

interface Tip {
  title: string | null
  lines: string[]
  x: number
  y: number
}

const GAP = 12
const EDGE = 8

// One tooltip for every chart on the page. A chart marks an element with `data-tip-title`
// and `data-tip` (lines split by "\n"), as plain text, so the log's words are never read as
// HTML. It follows a mouse, and opens on a tap on a phone, where there is no hover.
export function ChartTooltip() {
  const [tip, setTip] = useState<Tip | null>(null)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const show = (event: PointerEvent) => {
      const target = (event.target as Element | null)?.closest?.('[data-tip], [data-tip-title]')
      if (!target) return setTip(null)
      setTip({
        title: target.getAttribute('data-tip-title'),
        lines: (target.getAttribute('data-tip') ?? '').split('\n').filter(Boolean),
        x: event.clientX,
        y: event.clientY,
      })
    }
    const onMove = (event: PointerEvent) => event.pointerType === 'mouse' && show(event)
    const onDown = (event: PointerEvent) => event.pointerType !== 'mouse' && show(event)
    const hide = () => setTip(null)
    document.addEventListener('pointermove', onMove)
    document.addEventListener('pointerdown', onDown)
    window.addEventListener('scroll', hide, { passive: true })
    return () => {
      document.removeEventListener('pointermove', onMove)
      document.removeEventListener('pointerdown', onDown)
      window.removeEventListener('scroll', hide)
    }
  }, [])

  // Above the pointer, or below it when there is no room, and never past the window's edge.
  useEffect(() => {
    const node = box.current
    if (!tip || !node) return
    const { width, height } = node.getBoundingClientRect()
    const left = Math.min(Math.max(EDGE, tip.x - width / 2), window.innerWidth - width - EDGE)
    const top = tip.y - height - GAP < EDGE ? tip.y + GAP + 4 : tip.y - height - GAP
    node.style.left = `${left}px`
    node.style.top = `${top}px`
  }, [tip])

  if (!tip) return null
  return (
    <div ref={box} className="chart-tip" role="tooltip">
      {tip.title && <strong className="font-semibold">{tip.title}</strong>}
      {tip.lines.map((line, index) => (
        <div key={index}>{line}</div>
      ))}
    </div>
  )
}
