import { useEffect, useState } from 'react'

/**
 * Subscribe to a CSS media query. Returns true while the query matches.
 * Used to flip sidebar/header layouts between mobile and desktop.
 */
export function useMediaQuery(query: string): boolean {
  const getMatch = () =>
    typeof window !== 'undefined' && window.matchMedia(query).matches

  const [matches, setMatches] = useState<boolean>(getMatch)

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const mql = window.matchMedia(query)
    const handler = (event: MediaQueryListEvent) => setMatches(event.matches)
    // Initial sync (state may have drifted between render and effect)
    setMatches(mql.matches)
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [query])

  return matches
}
