// Tests for deal feed display helpers.
import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'

const sourcePath = new URL('./DealFeedPage.helpers.ts', import.meta.url)
const source = await readFile(sourcePath, 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
    verbatimModuleSyntax: true,
  },
})
const outputPath = path.join(tmpdir(), 'compa-deal-feed-page-test.mjs')
await writeFile(outputPath, compiled.outputText)
const { formatRelativeTime, getHoursOld } = await import(outputPath)

test('formatRelativeTime formats fresh, hourly, and daily rows', () => {
  const now = new Date('2026-08-19T12:00:00Z')

  assert.equal(formatRelativeTime('2026-08-19T11:45:00Z', now), '방금 전')
  assert.equal(formatRelativeTime('2026-08-19T09:00:00Z', now), '3시간 전')
  assert.equal(formatRelativeTime('2026-08-17T11:59:00Z', now), '2일 전')
})

test('getHoursOld returns null for missing or invalid dates and never negative', () => {
  const now = new Date('2026-08-19T12:00:00Z')

  assert.equal(getHoursOld(null, now), null)
  assert.equal(getHoursOld('not-a-date', now), null)
  assert.equal(getHoursOld('2026-08-19T13:00:00Z', now), 0)
})
