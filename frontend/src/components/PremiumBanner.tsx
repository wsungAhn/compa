import { useState } from 'react'

interface Props {
  premium: boolean
  onActivated: () => void
  onKeyChange: (key: string | null) => void
}

export function PremiumBanner({ premium, onActivated, onKeyChange }: Props) {
  const [keyInput, setKeyInput] = useState('')
  const [applying, setApplying] = useState(false)

  async function handleApply() {
    if (!keyInput.trim()) return
    setApplying(true)
    try {
      onKeyChange(keyInput.trim())
      // Give the header a moment to be set before refetching
      await new Promise(resolve => setTimeout(resolve, 100))
      onActivated()
      setKeyInput('')
    } finally {
      setApplying(false)
    }
  }

  if (premium) {
    return (
      <div className='flex items-center gap-2'>
        <span className='text-xs font-semibold bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full'>
          ✨ 프리미엄 이용 중
        </span>
      </div>
    )
  }

  return (
    <div className='rounded-2xl border border-amber-200 bg-gradient-to-r from-amber-50 to-orange-50 p-5'>
      <div className='mb-4'>
        <h3 className='text-base font-semibold text-amber-900 mb-1'>프리미엄으로 더 많이 보세요</h3>
        <p className='text-sm text-amber-700'>3년치 전체 할인 이력과 소셜 인사이트를 확인하세요</p>
      </div>

      <div className='flex gap-2'>
        <input
          type='password'
          value={keyInput}
          onChange={e => setKeyInput(e.target.value)}
          onKeyPress={e => e.key === 'Enter' && handleApply()}
          placeholder='프리미엄 키 입력'
          className='flex-1 px-3 py-2 text-sm border border-amber-200 rounded-lg bg-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-amber-400'
          disabled={applying}
        />
        <button
          onClick={handleApply}
          disabled={!keyInput.trim() || applying}
          className='px-4 py-2 text-sm font-medium bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors'
        >
          {applying ? '적용 중...' : '적용'}
        </button>
      </div>
    </div>
  )
}
