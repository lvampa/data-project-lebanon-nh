"use client"

import { useEffect, useState } from "react"

// Hides after `delay` ms of continuous downward scrolling; any upward scroll shows it again.
// A pause longer than 250ms restarts the count. Always shown near the top of the page.
export function useHideOnScroll(delay = 1000, topOffset = 80) {
  const [hidden, setHidden] = useState(false)

  useEffect(() => {
    let lastY = window.scrollY
    let lastT = 0
    let downSince: number | null = null

    const onScroll = () => {
      const y = window.scrollY
      const now = performance.now()
      if (now - lastT > 250) downSince = null
      lastT = now

      if (y > lastY + 1) {
        if (downSince === null) downSince = now
        if (y > topOffset && now - downSince >= delay) setHidden(true)
      } else if (y < lastY - 1) {
        downSince = null
        setHidden(false)
      }
      if (y <= 0) setHidden(false)
      lastY = y
    }

    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [delay, topOffset])

  return hidden
}
