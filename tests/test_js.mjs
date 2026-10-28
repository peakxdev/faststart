// Node test for docs/faststart.js: build a slow file with ffmpeg, fix it in JS, verify it still decodes.
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import assert from 'node:assert/strict'
import { check, fix } from '../docs/faststart.js'

const dir = mkdtempSync(join(tmpdir(), 'fs-'))
const src = join(dir, 'slow.mp4'), out = join(dir, 'fixed.mp4')
execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=duration=2:size=320x180:rate=15',
  '-f', 'lavfi', '-i', 'sine=duration=2', '-pix_fmt', 'yuv420p', '-shortest', src])
const blob = new Blob([readFileSync(src)])
assert.equal((await check(blob)).status, 'slow')
const res = await fix(blob)
assert.equal(res.status, 'fixed')
writeFileSync(out, Buffer.from(await res.blob.arrayBuffer()))
assert.equal((await check(new Blob([readFileSync(out)]))).status, 'ok')
assert.equal(res.blob.size, blob.size)
// Decode every frame of the fixed file: errors mean the offsets were patched wrong.
execFileSync('ffmpeg', ['-v', 'error', '-xerror', '-i', out, '-f', 'null', '-'])
const frames = (f) => execFileSync('ffprobe', ['-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', f]).toString().trim()
assert.equal(frames(out), frames(src))
console.log('js: ok')
