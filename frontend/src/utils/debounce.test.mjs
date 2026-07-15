import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'

const sourcePath = new URL('./debounce.ts', import.meta.url)
const source = await readFile(sourcePath, 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
    verbatimModuleSyntax: true,
  },
})
const outputPath = path.join(tmpdir(), 'compa-debounce-test.mjs')
await writeFile(outputPath, compiled.outputText)
const { debounce } = await import(outputPath)

test('debounce runs only the last call after delay', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const calls = []
  const debounced = debounce((value) => calls.push(value), 300)

  debounced('s')
  debounced('su')
  debounced('sul')
  t.mock.timers.tick(299)
  assert.deepEqual(calls, [])

  t.mock.timers.tick(1)
  assert.deepEqual(calls, ['sul'])
})

test('debounce cancel prevents pending call', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const calls = []
  const debounced = debounce((value) => calls.push(value), 300)

  debounced('sulwhasoo')
  debounced.cancel()
  t.mock.timers.tick(300)

  assert.deepEqual(calls, [])
})
