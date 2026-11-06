#!/bin/bash
set -euo pipefail
# Run a bounded protocol check inside an isolated container without inference.
docker run --rm --network none -i --entrypoint node "${SIFH_AGENT_IMAGE:-sifh_agent}" --input-type=module <<'JS'
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

const child = spawn('pi', ['--mode', 'rpc', '--no-session', '--no-tools',
  '--no-extensions', '--no-skills', '--no-prompt-templates', '--no-themes'],
  { stdio: ['pipe', 'pipe', 'ignore'] });
let matched = false;
let failed = false;
let bytes = 0;
const finish = (error) => {
  if (error) {
    failed = true;
    console.error(error);
  }
  child.kill('SIGKILL');
};
const timer = setTimeout(() => finish('RPC check timed out'), 15000);
child.on('error', () => finish('Could not launch pi'));
child.stdout.on('data', chunk => {
  bytes += chunk.length;
  if (bytes > 1048576) finish('RPC output limit exceeded');
});
const lines = createInterface({ input: child.stdout });
lines.on('line', line => {
  if (failed || matched) return;
  try {
    const response = JSON.parse(line);
    if (response.type !== 'response' || response.id !== 'sifh-smoke' ||
        response.command !== 'get_state' || response.success !== true ||
        !response.data || typeof response.data !== 'object' || Array.isArray(response.data)) {
      finish('Unexpected RPC response');
      return;
    }
    matched = true;
    finish();
  } catch {
    finish('Malformed RPC response');
  }
});
child.on('close', () => {
  clearTimeout(timer);
  lines.close();
  if (matched && !failed) console.log('Container pi get_state RPC check passed');
  else console.error('Container pi RPC check failed');
  process.exitCode = matched && !failed ? 0 : 1;
});
child.stdin.on('error', () => finish('RPC input closed unexpectedly'));
child.stdin.write(JSON.stringify({ id: 'sifh-smoke', type: 'get_state' }) + '\n');
JS
