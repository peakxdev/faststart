// faststart.js: check and fix MP4/MOV "faststart" in the browser (or Node 18+).
// Works on Blob/File slices, so the media itself is never loaded into memory:
// only atom headers and the moov atom (the index, usually a few hundred KB) are read.

const CONTAINERS = new Set(['moov', 'trak', 'mdia', 'minf', 'stbl', 'edts', 'dinf', 'udta'])

async function bytes(blob, start, end) {
  return new DataView(await blob.slice(start, end).arrayBuffer())
}

const fourcc = (dv, at) => String.fromCharCode(dv.getUint8(at), dv.getUint8(at + 1), dv.getUint8(at + 2), dv.getUint8(at + 3))

/** Top-level atoms as [{type, offset, size}], reading 16 bytes per atom. */
export async function readLayout(blob) {
  const atoms = []
  let pos = 0
  while (pos + 8 <= blob.size) {
    const dv = await bytes(blob, pos, Math.min(pos + 16, blob.size))
    let size = dv.getUint32(0)
    const type = fourcc(dv, 4)
    if (size === 1) size = Number(dv.getBigUint64(8))
    else if (size === 0) size = blob.size - pos
    if (size < 8) throw new Error(`corrupt atom at offset ${pos}`)
    atoms.push({ type, offset: pos, size })
    pos += size
  }
  return atoms
}

/** 'ok' | 'slow' | 'fragmented' | 'invalid', plus the layout. */
export async function check(blob) {
  const atoms = await readLayout(blob)
  const moov = atoms.find((a) => a.type === 'moov')
  const mdat = atoms.find((a) => a.type === 'mdat')
  if (!moov) return { status: 'invalid', atoms }
  if (atoms.some((a) => a.type === 'moof')) return { status: 'fragmented', atoms }
  return { status: !mdat || moov.offset < mdat.offset ? 'ok' : 'slow', atoms }
}

/** Shift every chunk offset (stco/co64) in a moov buffer by `shift(offset)`. */
function patchOffsets(dv, start, end, shift) {
  let pos = start
  while (pos + 8 <= end) {
    let size = dv.getUint32(pos)
    const type = fourcc(dv, pos + 4)
    let header = 8
    if (size === 1) { size = Number(dv.getBigUint64(pos + 8)); header = 16 }
    if (size < header || pos + size > end) throw new Error(`corrupt ${type} atom inside moov`)
    if (CONTAINERS.has(type)) {
      patchOffsets(dv, pos + header, pos + size, shift)
    } else if (type === 'stco') {
      const n = dv.getUint32(pos + header + 4)
      for (let i = 0, at = pos + header + 8; i < n; i++, at += 4) {
        const next = shift(dv.getUint32(at))
        if (next > 0xffffffff) throw new Error('file needs 64-bit offsets after the move; use the command-line tool')
        dv.setUint32(at, next)
      }
    } else if (type === 'co64') {
      const n = dv.getUint32(pos + header + 4)
      for (let i = 0, at = pos + header + 8; i < n; i++, at += 8) {
        dv.setBigUint64(at, BigInt(shift(Number(dv.getBigUint64(at)))))
      }
    }
    pos += size
  }
}

/** Return a new Blob with the moov atom moved in front of the media data. Lossless. */
export async function fix(blob, type = 'video/mp4') {
  const { status, atoms } = await check(blob)
  if (status !== 'slow') return { status, blob }
  const moov = atoms.find((a) => a.type === 'moov')
  const firstMdat = atoms.find((a) => a.type === 'mdat')
  const buf = await blob.slice(moov.offset, moov.offset + moov.size).arrayBuffer()
  const dv = new DataView(buf)
  // Data between the first mdat and the old moov moves forward by moov.size; data after the old moov stays put.
  patchOffsets(dv, 8, moov.size, (o) => (o >= firstMdat.offset && o < moov.offset ? o + moov.size : o))
  const parts = []
  for (const a of atoms) {
    if (a === firstMdat) parts.push(buf)
    if (a !== moov) parts.push(blob.slice(a.offset, a.offset + a.size))
  }
  return { status: 'fixed', blob: new Blob(parts, { type }) }
}
