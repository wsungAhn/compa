import { useEffect, useRef, useState } from 'react'
import type { Product } from '../api/client'
import { searchProducts, getJobStatus } from '../api/client'
import { decidePollAction } from './searchPolling'
import { debounce, type DebouncedFunction } from '../utils/debounce'

interface Props {
  onSelect: (product: Product) => void
  onCollecting?: (collecting: boolean) => void
}

const SEARCH_DEBOUNCE_MS = 300

export function SearchBar({ onSelect, onCollecting }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Product[]>([])
  const [loading, setLoading] = useState(false)
  const [collecting, setCollecting] = useState(false)
  const [collectionTimeout, setCollectionTimeout] = useState(false)
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollCountRef = useRef(0)
  const searchSequenceRef = useRef(0)
  const debouncedSearchRef = useRef<DebouncedFunction<[string, number]> | null>(null)

  if (!debouncedSearchRef.current) {
    debouncedSearchRef.current = debounce((q: string, sequence: number) => {
      void runSearch(q, sequence)
    }, SEARCH_DEBOUNCE_MS)
  }

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open])

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
      debouncedSearchRef.current?.cancel()
    }
  }, [])

  async function runSearch(q: string, sequence: number) {
    try {
      const response = await searchProducts(q, false)
      if (sequence !== searchSequenceRef.current) return
      setResults(response.products)
      if (response.products.length > 0) {
        setOpen(true)
      } else if (q.trim().length >= 2) {
        setOpen(true)
      }
    } catch {
      if (sequence !== searchSequenceRef.current) return
      setResults([])
    } finally {
      if (sequence === searchSequenceRef.current) {
        setLoading(false)
      }
    }
  }

  function handleSearch(q: string) {
    setQuery(q)
    const sequence = searchSequenceRef.current + 1
    searchSequenceRef.current = sequence

    if (q.trim().length < 1) {
      debouncedSearchRef.current?.cancel()
      setResults([])
      setOpen(false)
      setLoading(false)
      return
    }

    setLoading(true)
    debouncedSearchRef.current?.(q, sequence)
  }

  async function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key !== 'Enter') return
    if (query.trim().length < 2) return

    debouncedSearchRef.current?.cancel()
    searchSequenceRef.current += 1
    setOpen(false)
    setCollecting(true)
    setCollectionTimeout(false)
    onCollecting?.(true)

    // Clear any existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    pollCountRef.current = 0

    try {
      const response = await searchProducts(query, true)

      // Display existing results immediately if available
      if (response.products.length > 0) {
        setResults(response.products)
        setOpen(true)
      }

      // If job_id exists, start polling for completion
      if (response.job_id) {
        const jobId = response.job_id

        intervalRef.current = setInterval(async () => {
          pollCountRef.current += 1

          // Stop polling after 30 attempts (60 seconds)
          if (pollCountRef.current > 30) {
            if (intervalRef.current) {
              clearInterval(intervalRef.current)
              intervalRef.current = null
            }
            setCollecting(false)
            setCollectionTimeout(true)
            onCollecting?.(false)
            return
          }

          try {
            const status = await getJobStatus(jobId)

            const action = decidePollAction(status.status)

            if (action === 'refresh-results') {
              const refreshed = await searchProducts(query, false)
              setResults(refreshed.products)
              setCollecting(false)
              setCollectionTimeout(false)
              onCollecting?.(false)
              if (intervalRef.current) {
                clearInterval(intervalRef.current)
                intervalRef.current = null
              }
              // Auto-select single result
              if (refreshed.products.length === 1) {
                handleSelect(refreshed.products[0])
              } else if (refreshed.products.length > 1) {
                setOpen(true)
              } else {
                setOpen(true)
              }
            } else if (action === 'stop-failed') {
              // Keep existing results, stop collecting
              setCollecting(false)
              setCollectionTimeout(false)
              onCollecting?.(false)
              if (intervalRef.current) {
                clearInterval(intervalRef.current)
                intervalRef.current = null
              }
            }
            // For 'pending' and 'started', continue polling
          } catch {
            // On error, stop collecting but keep existing results
            setCollecting(false)
            setCollectionTimeout(false)
            onCollecting?.(false)
            if (intervalRef.current) {
              clearInterval(intervalRef.current)
              intervalRef.current = null
            }
          }
        }, 2000) // Poll every 2 seconds
      } else {
        // No job_id means no collection was started
        setCollecting(false)
        onCollecting?.(false)
      }
    } catch {
      // On search error, stop collecting
      setCollecting(false)
      onCollecting?.(false)
    }
  }

  function handleSelect(p: Product) {
    setQuery(p.name_kr ?? p.name_en ?? '')
    setOpen(false)
    onSelect(p)
  }

  return (
    <div ref={containerRef} className="relative w-full max-w-xl">
      <div className="flex items-center gap-2 bg-paper border border-ink/20 rounded-md px-4 py-3 focus-within:border-moss transition-colors">
        <input
          className="flex-1 outline-none text-ink placeholder-ink/70 text-base"
          placeholder="제품명을 입력하세요 (예: 설화수 윤조에센스)"
          value={query}
          onChange={e => handleSearch(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => (results.length > 0 || (query.trim().length >= 2 && results.length === 0)) && setOpen(true)}
        />
        {(loading || collecting) && <span className="text-ink/70 text-sm animate-pulse">검색 중…</span>}
      </div>

      {collecting && results.length === 0 && (
        <div className="absolute z-10 w-full mt-1 bg-paper border border-ink/10 rounded-md overflow-hidden">
          <div className="px-4 py-3 text-sm text-ink/70 text-center">
            수집 중...
          </div>
        </div>
      )}

      {open && results.length > 0 && (
        <ul className="absolute z-10 w-full mt-1 bg-paper border border-ink/10 rounded-md overflow-hidden">
          {collecting && (
            <li className="px-4 py-2 bg-linen border-b border-ink/10">
              <div className="text-xs text-ink/70">수집 중...</div>
            </li>
          )}
          {collectionTimeout && (
            <li className="px-4 py-2 bg-linen border-b border-ink/10">
              <div className="text-xs text-ink">수집 시간이 초과됐어요. 부분 결과만 표시됩니다.</div>
            </li>
          )}
          {results.length > 1 && !collecting && (
            <li className="px-4 py-2 bg-linen border-b border-ink/10">
              <div className="text-xs text-ink font-medium">{results.length}개 결과 찾았어요</div>
            </li>
          )}
          {results.map(p => (
            <li
              key={p.id}
              className="px-4 py-3 hover:bg-linen cursor-pointer transition-colors border-t border-ink/10"
              onClick={() => handleSelect(p)}
            >
              <div className="text-sm font-medium text-ink">{p.name_kr ?? p.name_en}</div>
              {p.brand && <div className="text-xs text-ink/70">{p.brand}</div>}
            </li>
          ))}
        </ul>
      )}

      {open && results.length === 0 && !collecting && query.trim().length >= 2 && (
        <div className="absolute z-10 w-full mt-1 bg-paper border border-ink/10 rounded-md overflow-hidden">
          <div className="px-4 py-3 text-sm text-ink/70 text-center">
            <span>Enter를 눌러 </span>
            <span className="font-medium text-ink">"{query}"</span>
            <span> 검색</span>
          </div>
        </div>
      )}
    </div>
  )
}
