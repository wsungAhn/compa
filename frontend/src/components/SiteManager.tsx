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
    <div className='relative'>
      <button
        onClick={() => setOpen(o => !o)}
        className='flex items-center gap-1 text-xs text-gray-500 hover:text-rose-500 transition-colors px-2 py-1 rounded-lg hover:bg-rose-50'
      >
        ⚙️ 사이트 설정
      </button>

      {open && (
        <div className='absolute right-0 top-8 z-30 w-72 bg-white border border-gray-200 rounded-2xl shadow-xl p-4'>
          <div className='flex items-center justify-between mb-3'>
            <span className='text-sm font-semibold text-gray-700'>비교 사이트 관리</span>
            <button onClick={() => setOpen(false)} className='text-gray-400 hover:text-gray-600 text-lg leading-none'>×</button>
          </div>

          <p className='text-xs text-gray-400 mb-3'>첫 번째 사이트가 기준 사이트가 됩니다</p>

          <ul className='space-y-1 mb-4'>
            {sites.map((site, idx) => (
              <li key={site.id} className='flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-gray-50'>
                {idx === 0 && (
                  <span className='text-xs bg-rose-100 text-rose-600 font-semibold px-1.5 py-0.5 rounded-full shrink-0'>기준</span>
                )}
                <span className='text-sm flex-1'>{site.flag} {site.name}</span>
                <div className='flex items-center gap-0.5'>
                  <button
                    onClick={() => onMoveUp(site.id)}
                    disabled={idx === 0}
                    className='p-1 rounded text-gray-400 hover:text-gray-600 disabled:opacity-20'
                  >▲</button>
                  <button
                    onClick={() => onMoveDown(site.id)}
                    disabled={idx === sites.length - 1}
                    className='p-1 rounded text-gray-400 hover:text-gray-600 disabled:opacity-20'
                  >▼</button>
                  <button
                    onClick={() => onRemove(site.id)}
                    className='p-1 rounded text-gray-400 hover:text-rose-500 ml-1'
                  >✕</button>
                </div>
              </li>
            ))}
          </ul>

          {availableToAdd.length > 0 && (
            <div>
              <p className='text-xs text-gray-400 mb-2'>추가 가능</p>
              <div className='flex flex-wrap gap-1.5'>
                {availableToAdd.map(site => (
                  <button
                    key={site.id}
                    onClick={() => onAdd(site)}
                    className='text-xs px-2 py-1 rounded-full border border-gray-200 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600 transition-colors'
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
