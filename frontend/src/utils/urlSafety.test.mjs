import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'

const sourcePath = new URL('./urlSafety.ts', import.meta.url)
const source = await readFile(sourcePath, 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
    verbatimModuleSyntax: true,
  },
})
const outputPath = path.join(tmpdir(), 'compa-urlSafety-test.mjs')
await writeFile(outputPath, compiled.outputText)
const { safeUrl } = await import(outputPath)

test('safeUrl allows http and https URLs', () => {
  assert.equal(safeUrl('https://example.com/product'), 'https://example.com/product')
  assert.equal(safeUrl('http://example.com/product'), 'http://example.com/product')
})

test('safeUrl rejects unsafe schemes', () => {
  assert.equal(safeUrl('javascript:alert(1)'), null)
  assert.equal(safeUrl('data:text/html,<script>alert(1)</script>'), null)
})

test('safeUrl rejects missing and relative URLs', () => {
  assert.equal(safeUrl(null), null)
  assert.equal(safeUrl(''), null)
  assert.equal(safeUrl('/relative/path'), null)
})
