// Tests for matching coverage display helpers.
import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import ts from 'typescript'

const sourcePath = new URL('./CoveragePage.helpers.ts', import.meta.url)
const source = await readFile(sourcePath, 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
    verbatimModuleSyntax: true,
  },
})
const outputPath = path.join(tmpdir(), 'compa-coverage-page-test.mjs')
await writeFile(outputPath, compiled.outputText)
const { clampPct, formatCount, getBatchWindow } = await import(pathToFileURL(outputPath).href)

test('getBatchWindow returns previous and next UTC six-hour batch slots', () => {
  assert.deepEqual(getBatchWindow(new Date('2026-08-19T12:39:00Z')), {
    lastBatch: '06:40 UTC',
    nextBatch: '12:40 UTC',
  })
  assert.deepEqual(getBatchWindow(new Date('2026-08-19T12:40:00Z')), {
    lastBatch: '12:40 UTC',
    nextBatch: '18:40 UTC',
  })
})

test('formatCount and clampPct format dashboard values', () => {
  assert.equal(formatCount(48213), '48,213')
  assert.equal(clampPct(-1), 0)
  assert.equal(clampPct(47.2), 47.2)
  assert.equal(clampPct(101), 100)
})
