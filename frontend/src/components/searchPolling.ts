export type JobState = 'pending' | 'started' | 'success' | 'failure'

export type PollDecision = 'continue' | 'refresh-results' | 'stop-failed'

export function decidePollAction(status: JobState): PollDecision {
  if (status === 'success') return 'refresh-results'
  if (status === 'failure') return 'stop-failed'
  return 'continue'
}
