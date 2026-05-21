import { useEffect, useRef, useState } from 'react'
import type { Product } from '../api/client'
import { searchProducts } from '../api/client'

interface Props {
  onSelect: (product: Product) => void
}

export function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Product[]>([])
  const [loading, setLoading] = useState(false)
  const [collecting, setCollecting] = useState(false)
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

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

  async function handleSearch(q: string) {
    setQuery(q)
    if (q.trim().length < 1) { setResults([]); setOpen(false); return }
    setLoading(true)
    try {
      const data = await searchProducts(q, false)
      setResults(data)
      if (data.length > 0) {
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
    try {
      const data = await searchProducts(query, true)
      if (data.length > 0) {
        setResults(data)
        setOpen(true)
      }
    } catch {
      // 조용히 실패
    } finally {
      setCollecting(false)
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

      {collecting && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
          <div className="px-4 py-3 text-sm text-gray-500 text-center">
            수집 중... (30초 정도 소요됩니다)
          </div>
        </div>
      )}

      {open && results.length > 0 && (
        <ul className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
          {results.map(p => (
            <li
              key={p.id}
              className="px-4 py-3 hover:bg-rose-50 cursor-pointer transition-colors"
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
