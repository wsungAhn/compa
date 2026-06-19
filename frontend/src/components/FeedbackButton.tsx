import { useEffect, useRef, useState } from 'react'
import { postFeedback } from '../api/client'

export function FeedbackButton() {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [contact, setContact] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState(false)
  const modalRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  function handleOpen() {
    setOpen(true)
    setError(null)
  }

  function handleClose() {
    setOpen(false)
    setMessage('')
    setContact('')
    setError(null)
  }

  async function handleSubmit() {
    if (!message.trim()) {
      setError('내용을 입력해 주세요.')
      return
    }
    if (message.length > 2000) {
      setError('2000자 이하로 입력해 주세요.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await postFeedback(
        message.trim(),
        contact.trim() || undefined,
        typeof window !== 'undefined' ? window.location.pathname : undefined
      )
      setOpen(false)
      setMessage('')
      setContact('')
      setToast(true)
      setTimeout(() => setToast(false), 2000)
    } catch {
      setError('전송에 실패했습니다. 잠시 후 다시 시도해 주세요.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={handleOpen}
        title="피드백 보내기"
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
      >
        <span className="text-base leading-none">💬</span>
        <span className="hidden sm:inline">피드백</span>
      </button>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-gray-800 text-white text-sm px-4 py-2 rounded-lg shadow-lg pointer-events-none">
          피드백을 보냈어요 감사합니다
        </div>
      )}

      {/* Modal overlay */}
      {open && (
        <div className="fixed inset-0 z-40 flex items-end sm:items-center justify-center bg-black/30 px-4">
          <div
            ref={modalRef}
            className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6 flex flex-col gap-4"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-800">피드백 보내기</h2>
              <button
                onClick={handleClose}
                className="text-gray-400 hover:text-gray-600 transition-colors text-xl leading-none"
                aria-label="닫기"
              >
                ×
              </button>
            </div>

            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="개선 사항, 버그 제보, 기능 요청 등 자유롭게 작성해 주세요."
              rows={5}
              maxLength={2000}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 placeholder-gray-400"
            />
            <div className="text-xs text-gray-400 text-right -mt-2">{message.length} / 2000</div>

            <input
              type="email"
              value={contact}
              onChange={e => setContact(e.target.value)}
              placeholder="이메일 (선택 — 답변 원하시면 입력)"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400 placeholder-gray-400"
            />

            {error && (
              <p className="text-sm text-red-500">{error}</p>
            )}

            <div className="flex gap-2 justify-end">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting || !message.trim()}
                className="px-5 py-2 text-sm font-medium bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {submitting ? '전송 중...' : '전송'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
