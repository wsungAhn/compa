import { useState } from 'react'

const STORAGE_KEY = 'compa-admin-secret'

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

export function useAdminSecret() {
  const [adminSecret, setAdminSecretState] = useState<string | null>(load)

  function setAdminSecret(key: string | null) {
    save(key)
    setAdminSecretState(key)
  }

  return { adminSecret, setAdminSecret }
}
