import { useState } from 'react'

export interface SitePref {
  id: string
  name: string
  country: string
  flag: string
}

const SUPPORTED_SITES: SitePref[] = [
  { id: 'oliveyoung', name: '올리브영', country: 'KR', flag: '🇰🇷' },
  { id: 'naver', name: '네이버쇼핑', country: 'KR', flag: '🇰🇷' },
  { id: 'coupang', name: '쿠팡', country: 'KR', flag: '🇰🇷' },
  { id: 'sephora', name: 'Sephora', country: 'US', flag: '🇺🇸' },
  { id: 'amazon', name: 'Amazon US', country: 'US', flag: '🇺🇸' },
  { id: 'rakuten', name: 'Rakuten', country: 'JP', flag: '🇯🇵' },
  { id: 'cosme', name: '@cosme', country: 'JP', flag: '🇯🇵' },
  { id: 'tmall', name: 'Tmall', country: 'CN', flag: '🇨🇳' },
]

const STORAGE_KEY = 'compa-site-prefs-v1'
const DEFAULT_ACTIVE = ['oliveyoung', 'naver', 'sephora', 'amazon', 'rakuten']

function load(): SitePref[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as SitePref[]
  } catch {}
  return SUPPORTED_SITES.filter(s => DEFAULT_ACTIVE.includes(s.id))
}

function save(sites: SitePref[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sites))
}

export function useSitePrefs() {
  const [sites, setSites] = useState<SitePref[]>(load)

  const preferred = sites[0] ?? null

  function moveUp(id: string) {
    setSites(prev => {
      const idx = prev.findIndex(s => s.id === id)
      if (idx <= 0) return prev
      const next = [...prev]
      ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
      save(next)
      return next
    })
  }

  function moveDown(id: string) {
    setSites(prev => {
      const idx = prev.findIndex(s => s.id === id)
      if (idx < 0 || idx >= prev.length - 1) return prev
      const next = [...prev]
      ;[next[idx], next[idx + 1]] = [next[idx + 1], next[idx]]
      save(next)
      return next
    })
  }

  function addSite(site: SitePref) {
    setSites(prev => {
      if (prev.find(s => s.id === site.id)) return prev
      const next = [...prev, site]
      save(next)
      return next
    })
  }

  function removeSite(id: string) {
    setSites(prev => {
      const next = prev.filter(s => s.id !== id)
      save(next)
      return next
    })
  }

  const availableToAdd = SUPPORTED_SITES.filter(s => !sites.find(a => a.id === s.id))

  return { sites, preferred, moveUp, moveDown, addSite, removeSite, availableToAdd }
}
