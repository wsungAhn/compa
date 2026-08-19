// Helpers for displaying the matching coverage schedule.
const BATCH_HOURS_UTC = [0, 6, 12, 18]
const BATCH_MINUTE_UTC = 40

function atBatchTime(day: Date, hour: number): Date {
  return new Date(Date.UTC(
    day.getUTCFullYear(),
    day.getUTCMonth(),
    day.getUTCDate(),
    hour,
    BATCH_MINUTE_UTC,
    0,
    0
  ))
}

function formatUtcTime(date: Date): string {
  return new Intl.DateTimeFormat('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  }).format(date)
}

export function getBatchWindow(now = new Date()): { lastBatch: string; nextBatch: string } {
  const todayBatches = BATCH_HOURS_UTC.map(hour => atBatchTime(now, hour))
  const lastToday = [...todayBatches].reverse().find(batch => batch <= now)
  const nextToday = todayBatches.find(batch => batch > now)

  const yesterday = new Date(now)
  yesterday.setUTCDate(yesterday.getUTCDate() - 1)
  const tomorrow = new Date(now)
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1)

  const lastBatch = lastToday ?? atBatchTime(yesterday, BATCH_HOURS_UTC[BATCH_HOURS_UTC.length - 1])
  const nextBatch = nextToday ?? atBatchTime(tomorrow, BATCH_HOURS_UTC[0])

  return {
    lastBatch: `${formatUtcTime(lastBatch)} UTC`,
    nextBatch: `${formatUtcTime(nextBatch)} UTC`,
  }
}

export function formatCount(value: number): string {
  return value.toLocaleString('ko-KR')
}

export function clampPct(value: number): number {
  return Math.min(Math.max(value, 0), 100)
}
