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
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-ink/70 hover:text-ink hover:bg-linen rounded-md transition-colors"
      >
        <span>피드백</span>
      </button>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-ink text-paper text-sm px-4 py-2 rounded-md pointer-events-none">
          피드백을 보냈어요 감사합니다
        </div>
      )}

      {/* Modal overlay */}
      {open && (
        <div className="fixed inset-0 z-40 flex items-end sm:items-center justify-center bg-black/30 px-4">
          <div
            ref={modalRef}
            className="w-full max-w-md bg-paper border border-ink/10 rounded-md p-6 flex flex-col gap-4"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-base font-medium text-ink">피드백 보내기</h2>
              <button
                onClick={handleClose}
                className="text-ink/70 hover:text-ink transition-colors text-xl leading-none"
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
              className="w-full px-3 py-2 text-sm border border-ink/10 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-moss/40 placeholder-ink/70"
            />
            <div className="text-xs text-ink/70 text-right -mt-2">{message.length} / 2000</div>

            <input
              type="email"
              value={contact}
              onChange={e => setContact(e.target.value)}
              placeholder="이메일 (선택 — 답변 원하시면 입력)"
              className="w-full px-3 py-2 text-sm border border-ink/10 rounded-md focus:outline-none focus:ring-2 focus:ring-moss/40 placeholder-ink/70"
            />

            {error && (
              <p className="text-sm text-ink">{error}</p>
            )}

            <div className="flex gap-2 justify-end">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-sm text-ink/70 hover:text-ink transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting || !message.trim()}
                className="px-5 py-2 text-sm font-medium bg-moss text-paper rounded-md hover:bg-moss/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
