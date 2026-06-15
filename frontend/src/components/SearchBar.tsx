import { useEffect, useRef, useState } from 'react'
import type { Product } from '../api/client'
import { searchProducts, getJobStatus } from '../api/client'

interface Props {
  onSelect: (product: Product) => void
  onCollecting?: (collecting: boolean) => void
}

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
    }
  }, [])

  async function handleSearch(q: string) {
    setQuery(q)
    if (q.trim().length < 1) { setResults([]); setOpen(false); return }
    setLoading(true)
    try {
      const response = await searchProducts(q, false)
      setResults(response.products)
      if (response.products.length > 0) {
        setOpen(true)
      } else if (q.trim().length >= 2) {
        setOpen(true)
      }
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  async function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key !== 'Enter') return
    if (query.trim().length < 2) return

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

            if (status.status === 'done') {
              // Update results with newly collected products
              setResults(status.products)
              setCollecting(false)
              setCollectionTimeout(false)
              onCollecting?.(false)
              if (intervalRef.current) {
                clearInterval(intervalRef.current)
                intervalRef.current = null
              }
              // Auto-select single result
              if (status.products.length === 1) {
                handleSelect(status.products[0])
              } else if (status.products.length > 1) {
                setOpen(true)
              } else {
                setOpen(true)
              }
            } else if (status.status === 'failed') {
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
      <div className="flex items-center gap-2 bg-white border-2 border-rose-300 rounded-2xl px-4 py-3 shadow-sm focus-within:border-rose-500 transition-colors">
        <span className="text-gray-400 text-lg">🔍</span>
        <input
          className="flex-1 outline-none text-gray-800 placeholder-gray-400 text-base"
          placeholder="제품명을 입력하세요 (예: 설화수 윤조에센스)"
          value={query}
          onChange={e => handleSearch(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => (results.length > 0 || (query.trim().length >= 2 && results.length === 0)) && setOpen(true)}
        />
        {(loading || collecting) && <span className="text-gray-400 text-sm animate-pulse">검색 중…</span>}
      </div>

      {collecting && results.length === 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
          <div className="px-4 py-3 text-sm text-gray-500 text-center">
            수집 중...
          </div>
        </div>
      )}

      {open && results.length > 0 && (
        <ul className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
          {collecting && (
            <li className="px-4 py-2 bg-amber-50 border-b border-amber-200">
              <div className="text-xs text-amber-700">수집 중...</div>
            </li>
          )}
          {collectionTimeout && (
            <li className="px-4 py-2 bg-red-50 border-b border-red-200">
              <div className="text-xs text-red-700">수집 시간이 초과됐어요. 부분 결과만 표시됩니다.</div>
            </li>
          )}
          {results.length > 1 && !collecting && (
            <li className="px-4 py-2 bg-blue-50 border-b border-blue-200">
              <div className="text-xs text-blue-700 font-medium">{results.length}개 결과 찾았어요</div>
            </li>
          )}
          {results.map(p => (
            <li
              key={p.id}
              className="px-4 py-3 hover:bg-rose-50 cursor-pointer transition-colors border-t border-gray-100"
              onClick={() => handleSelect(p)}
            >
              <div className="text-sm font-medium text-gray-800">{p.name_kr ?? p.name_en}</div>
              {p.brand && <div className="text-xs text-gray-400">{p.brand}</div>}
            </li>
          ))}
        </ul>
      )}

      {open && results.length === 0 && !collecting && query.trim().length >= 2 && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
          <div className="px-4 py-3 text-sm text-gray-400 text-center">
            <span>Enter를 눌러 </span>
            <span className="font-semibold text-gray-600">"{query}"</span>
            <span> 검색</span>
          </div>
        </div>
      )}
    </div>
  )
}
