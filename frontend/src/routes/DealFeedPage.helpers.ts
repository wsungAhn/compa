// Deal feed display helpers shared by the page and tests.
const MS_PER_HOUR = 60 * 60 * 1000

export function getHoursOld(postedAt: string | null, now: Date = new Date()): number | null {
  if (!postedAt) return null
  const postedTime = new Date(postedAt).getTime()
  if (Number.isNaN(postedTime)) return null
  return Math.max(0, Math.floor((now.getTime() - postedTime) / MS_PER_HOUR))
}

export function formatRelativeTime(postedAt: string | null, now: Date = new Date()): string | null {
  const hoursOld = getHoursOld(postedAt, now)
  if (hoursOld === null) return null
  if (hoursOld < 1) return '방금 전'
  if (hoursOld < 24) return `${hoursOld}시간 전`
  return `${Math.floor(hoursOld / 24)}일 전`
}
