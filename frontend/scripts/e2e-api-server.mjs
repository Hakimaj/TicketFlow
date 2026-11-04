#!/usr/bin/env node
/**
 * Cross-platform launcher for the API-mode Playwright backend.
 *
 * Playwright's webServer command runs through cmd.exe on Windows and /bin/sh
 * elsewhere, so the old `bash -c "cd ../backend && ..."` string only worked on
 * machines with Git Bash on PATH. This wrapper resolves the backend directory
 * and virtualenv explicitly, prepares the isolated `*_e2e` database, and then
 * starts uvicorn with the same environment.
 */

import { spawn, spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const backendDir = path.resolve(scriptDir, '../../backend')
const isWindows = process.platform === 'win32'

function resolvePython() {
  const configured = process.env.E2E_PYTHON?.trim()
  if (configured) {
    // A path is relative to backend/ (where uvicorn runs). A bare command such
    // as `python` (used by CI) is left on PATH.
    if (!configured.includes('/') && !configured.includes('\\')) {
      return configured
    }
    return path.isAbsolute(configured)
      ? configured
      : path.resolve(backendDir, configured)
  }
  return path.join(
    backendDir,
    '.venv',
    isWindows ? 'Scripts/python.exe' : 'bin/python',
  )
}

const python = resolvePython()
const port = process.env.E2E_API_PORT ?? '8010'
const env = {
  ...process.env,
  DATABASE_URL:
    process.env.E2E_DATABASE_URL ??
    'postgresql+psycopg://ticketflow:ticketflow_local_dev_only@127.0.0.1:5432/ticketflow_e2e',
  APP_ENV: process.env.APP_ENV ?? 'development',
  JWT_SECRET:
    process.env.JWT_SECRET ??
    'e2e-only-jwt-secret-not-for-production-0000',
}

const prepare = spawnSync(python, ['-m', 'scripts.e2e_prepare'], {
  cwd: backendDir,
  env,
  stdio: 'inherit',
})
if (prepare.error) {
  console.error(`Could not start ${python}: ${prepare.error.message}`)
  process.exit(1)
}
if (prepare.status !== 0) {
  process.exit(prepare.status ?? 1)
}

const server = spawn(
  python,
  [
    '-m',
    'uvicorn',
    'app.main:app',
    '--host',
    '127.0.0.1',
    '--port',
    port,
  ],
  { cwd: backendDir, env, stdio: 'inherit' },
)

server.on('error', (error) => {
  console.error(`Could not start the API: ${error.message}`)
  process.exit(1)
})
server.on('exit', (code) => process.exit(code ?? 0))

function shutdown() {
  if (!server.killed) server.kill()
  // Do not hang if a platform does not forward the signal to the child.
  setTimeout(() => process.exit(0), 3_000).unref()
}

process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
