import { useState } from 'react'
import type { SitePref } from '../hooks/useSitePrefs'

interface Props {
  sites: SitePref[]
  availableToAdd: SitePref[]
  onMoveUp: (id: string) => void
  onMoveDown: (id: string) => void
  onAdd: (site: SitePref) => void
  onRemove: (id: string) => void
}

export function SiteManager({ sites, availableToAdd, onMoveUp, onMoveDown, onAdd, onRemove }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1 text-xs text-ink/70 hover:text-moss transition-colors px-2 py-1 rounded-md hover:bg-linen"
      >
        사이트 설정
      </button>

      {open && (
        <div className="absolute right-0 top-8 z-30 w-72 bg-paper border border-ink/10 rounded-md p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-ink">비교 사이트 관리</span>
            <button onClick={() => setOpen(false)} className="text-ink/70 hover:text-ink text-lg leading-none">×</button>
          </div>

          <p className="text-xs text-ink/70 mb-3">첫 번째 사이트가 기준 사이트가 됩니다</p>

          {/* 현재 사이트 목록 */}
          <ul className="space-y-1 mb-4">
            {sites.map((site, idx) => (
              <li key={site.id} className="flex items-center gap-2 py-1.5 px-2 rounded-md hover:bg-linen">
                {idx === 0 && (
                  <span className="text-xs bg-moss text-paper font-medium px-1.5 py-0.5 rounded-md shrink-0">기준</span>
                )}
                <span className="text-sm flex-1">{site.flag} {site.name}</span>
                <div className="flex items-center gap-0.5">
                  <button
                    onClick={() => onMoveUp(site.id)}
                    disabled={idx === 0}
                    className="p-1 rounded text-ink/70 hover:text-ink disabled:opacity-20"
                  >▲</button>
                  <button
                    onClick={() => onMoveDown(site.id)}
                    disabled={idx === sites.length - 1}
                    className="p-1 rounded text-ink/70 hover:text-ink disabled:opacity-20"
                  >▼</button>
                  <button
                    onClick={() => onRemove(site.id)}
                    className="p-1 rounded text-ink/70 hover:text-moss ml-1"
                  >✕</button>
                </div>
              </li>
            ))}
          </ul>

          {/* 추가 가능한 사이트 */}
          {availableToAdd.length > 0 && (
            <div>
            <p className="text-xs text-ink/70 mb-2">추가 가능</p>
              <div className="flex flex-wrap gap-1.5">
                {availableToAdd.map(site => (
                  <button
                    key={site.id}
                    onClick={() => onAdd(site)}
                    className="text-xs px-2 py-1 rounded-md border border-ink/10 hover:border-moss hover:bg-linen hover:text-moss transition-colors"
                  >
                    + {site.flag} {site.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
