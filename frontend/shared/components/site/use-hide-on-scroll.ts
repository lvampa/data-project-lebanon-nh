"use client"

import { useEffect, useState } from "react"

// Hides once the page has scrolled `distance` px down since the last upward scroll; any upward
// scroll shows it again. Distance, not time, so a wheel, a trackpad and a phone all feel the same.
// Always shown near the top of the page.
export function useHideOnScroll(distance = 150, topOffset = 80) {
  const [hidden, setHidden] = useState(false)

  useEffect(() => {
    // On phones the first stretch of a swipe moves the browser toolbar, which shifts the visual
    // viewport without changing window.scrollY or firing window scroll events. pageTop counts both.
    const scrollTop = () => window.visualViewport?.pageTop ?? window.scrollY
    let lastY = scrollTop()
    let downFrom = lastY

    const onScroll = () => {
      const y = scrollTop()

      if (y < lastY - 1) {
        downFrom = y
        setHidden(false)
      } else if (y > topOffset && y - downFrom >= distance) {
        setHidden(true)
      }
      if (y <= 0) setHidden(false)
      lastY = y
    }

    window.addEventListener("scroll", onScroll, { passive: true })
    window.visualViewport?.addEventListener("scroll", onScroll, { passive: true })
    return () => {
      window.removeEventListener("scroll", onScroll)
      window.visualViewport?.removeEventListener("scroll", onScroll)
    }
  }, [distance, topOffset])

  return hidden
}
