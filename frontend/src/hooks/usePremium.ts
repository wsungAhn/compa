import { useState } from 'react'

const STORAGE_KEY = 'compa-premium-key'

function load(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    // localStorage access failed (private browsing, etc)
  }
  return null
}

function save(key: string | null) {
  try {
    if (key === null) {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, key)
    }
  } catch {
    // localStorage write failed
  }
}

export function usePremium() {
  const [premiumKey, setPremiumKeyState] = useState<string | null>(load)

  function setPremiumKey(key: string | null) {
    save(key)
    setPremiumKeyState(key)
  }

  return { premiumKey, setPremiumKey }
}
