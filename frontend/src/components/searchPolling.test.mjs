import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'

const sourcePath = new URL('./searchPolling.ts', import.meta.url)
const source = await readFile(sourcePath, 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
    verbatimModuleSyntax: true,
  },
})
const outputPath = path.join(tmpdir(), 'compa-searchPolling-test.mjs')
await writeFile(outputPath, compiled.outputText)
const { decidePollAction } = await import(outputPath)

test('success refreshes products after celery completion', () => {
  assert.equal(decidePollAction('success'), 'refresh-results')
})

test('failure stops polling without refreshing products', () => {
  assert.equal(decidePollAction('failure'), 'stop-failed')
})

test('pending and started continue polling', () => {
  assert.equal(decidePollAction('pending'), 'continue')
  assert.equal(decidePollAction('started'), 'continue')
})
