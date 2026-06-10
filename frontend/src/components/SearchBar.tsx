import { useState, useRef, useEffect } from 'react'
import type { Product } from '../api/client'
import { searchProducts } from '../api/client'

interface Props {
  onSelect: (product: Product) => void
}

export function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Product[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [collecting, setCollecting] = useState(false)
  const [pollAttempts, setPollAttempts] = useState(0)
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const lastQueryRef = useRef('')

  // Cleanup polling timer on unmount or when query changes
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [])

  async function startPolling(q: string) {
    // Clear any existing poll timer
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }

    let attempt = 0
    const maxAttempts = 15
    const pollInterval = 4000 // 4 seconds

    lastQueryRef.current = q

    const poll = async () => {
      // Stop if query changed
      if (lastQueryRef.current !== q) {
        if (pollTimerRef.current) clearInterval(pollTimerRef.current)
        return
      }

      attempt++
      setPollAttempts(attempt)

      try {
        const data = await searchProducts(q)

        // Check again if query changed
        if (lastQueryRef.current !== q) return

        if (data.products.length > 0) {
          // Got results, stop polling
          setResults(data.products)
          setCollecting(false)
          if (pollTimerRef.current) clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
        } else if (attempt >= maxAttempts) {
          // Exhausted attempts
          setCollecting(false)
          if (pollTimerRef.current) clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
        }
      } catch {
        if (attempt >= maxAttempts) {
          setCollecting(false)
          if (pollTimerRef.current) clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
        }
      }
    }

    // First poll immediately
    await poll()

    // If still collecting and not max attempts, set interval for subsequent polls
    if (collecting && attempt < maxAttempts) {
      pollTimerRef.current = setInterval(poll, pollInterval)
    }
  }

  async function handleSearch(q: string) {
    setQuery(q)
    lastQueryRef.current = q

    // Clear polling on input change
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }

    if (q.trim().length < 1) {
      setResults([])
      setOpen(false)
      setCollecting(false)
      setPollAttempts(0)
      return
    }

    setLoading(true)
    setCollecting(false)
    setPollAttempts(0)

    try {
      const data = await searchProducts(q)

      // Check if query changed while fetching
      if (lastQueryRef.current !== q) return

      if (data.products.length > 0) {
        // Got results immediately
        setResults(data.products)
        setOpen(true)
      } else if (data.collecting) {
        // No products yet, but backend is collecting — start polling
        setResults([])
        setOpen(true)
        setCollecting(true)
        setPollAttempts(1)
        // Start polling from next interval
        if (pollTimerRef.current) clearInterval(pollTimerRef.current)
        pollTimerRef.current = setInterval(() => startPolling(q), 4000)
      } else {
        // No products and not collecting
        setResults([])
      }
    } catch {
      setResults([])
      setCollecting(false)
    } finally {
      setLoading(false)
    }
  }

  function handleSelect(p: Product) {
    setQuery(p.name_kr ?? p.name_en ?? '')
    setOpen(false)
    setCollecting(false)
    if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    onSelect(p)
  }

  return (
    <div className="relative w-full max-w-xl">
      <div className="flex items-center gap-2 bg-white border-2 border-rose-300 rounded-2xl px-4 py-3 shadow-sm focus-within:border-rose-500 transition-colors">
        <span className="text-gray-400 text-lg">🔍</span>
        <input
          className="flex-1 outline-none text-gray-800 placeholder-gray-400 text-base"
          placeholder="제품명을 입력하세요 (예: 설화수 윤조에센스)"
          value={query}
          onChange={e => handleSearch(e.target.value)}
          onFocus={() => (results.length > 0 || collecting) && setOpen(true)}
        />
        {(loading || collecting) && (
          <span className="text-gray-400 text-sm animate-pulse">
            {loading ? '검색 중…' : '수집 중…'}
          </span>
        )}
      </div>

      {open && (results.length > 0 || collecting) && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
          {collecting && results.length === 0 ? (
            <div className="px-4 py-6">
              <div className="flex flex-col items-center gap-2">
                <span className="text-2xl animate-spin">⌛</span>
                <p className="text-sm font-medium text-gray-700">처음 검색하는 제품이에요</p>
                <p className="text-xs text-gray-500 text-center">
                  4개국 가격을 수집하고 있어요…
                  <br />
                  (최대 1분)
                </p>
              </div>
            </div>
          ) : pollAttempts >= 15 && results.length === 0 ? (
            <div className="px-4 py-6">
              <div className="flex flex-col items-center gap-2">
                <span className="text-2xl">⏱️</span>
                <p className="text-sm font-medium text-gray-700">
                  수집이 오래 걸리고 있어요
                </p>
                <p className="text-xs text-gray-500 text-center">
                  잠시 후 다시 검색해주세요
                </p>
              </div>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {results.map(p => (
                <li
                  key={p.id}
                  className="px-4 py-3 hover:bg-rose-50 cursor-pointer transition-colors"
                  onClick={() => handleSelect(p)}
                >
                  <div className="text-sm font-medium text-gray-800">
                    {p.name_kr ?? p.name_en}
                  </div>
                  {p.brand && <div className="text-xs text-gray-400">{p.brand}</div>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
