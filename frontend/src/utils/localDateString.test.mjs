import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'

const sourcePath = new URL('./localDateString.ts', import.meta.url)
const source = await readFile(sourcePath, 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
    verbatimModuleSyntax: true,
  },
})
const outputPath = path.join(tmpdir(), 'compa-localDateString-test.mjs')
await writeFile(outputPath, compiled.outputText)
const { localDateString } = await import(outputPath)

test('localDateString uses local calendar fields instead of UTC formatting', () => {
  const date = new Date('2026-07-14T15:30:00Z')
  Object.defineProperty(date, 'getFullYear', { value: () => 2026 })
  Object.defineProperty(date, 'getMonth', { value: () => 6 })
  Object.defineProperty(date, 'getDate', { value: () => 15 })

  assert.equal(localDateString(date), '2026-07-15')
  assert.equal(date.toISOString().slice(0, 10), '2026-07-14')
})
