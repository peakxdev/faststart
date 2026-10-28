# faststart

**Find and fix MP4/MOV files that start slowly on the web.** Lossless: no re-encoding, same quality, same size.

**Try it in your browser:** https://peakxdev.github.io/faststart/ (nothing is uploaded)

## The problem

A video can only start playing once the player has read its index (the `moov` atom). Many cameras, phones and export tools write that index at the **end** of the file. On a website or in an app, the player then has to download the end of the file before it can play the first frame. On a phone connection, a big file can take a long time to start, or seem to fail.

The fix is to move the index to the front. `faststart` finds the files that need it and fixes them.

## Use it

### In the browser
Open **https://peakxdev.github.io/faststart/**, drop your files in, and download the fixed copies. It runs locally and reads only the index, so even multi-GB files are fine.

### Command line
```bash
pip install git+https://github.com/peakxdev/faststart

faststart check videos/            # lists slow files, exits 1 if any (handy in CI)
faststart fix videos/ -o fixed/    # writes fixed copies (needs ffmpeg)
faststart fix clip.mp4 --in-place  # replaces the file after verifying the result
```
`check` is pure Python and reads only atom headers. `fix` uses `ffmpeg -c copy -movflags +faststart` and verifies the result before replacing anything.

### In JavaScript
[`docs/faststart.js`](docs/faststart.js) is a dependency-free ES module for browsers and Node 18+:
```js
import { check, fix } from './faststart.js'
const { status } = await check(file)       // 'ok' | 'slow' | 'fragmented' | 'invalid'
const { blob } = await fix(file)           // Blob with the index moved to the front
```

## Tips
- **Uploading to S3 / R2 / a CDN?** Run `faststart check` on your media folder or bucket mirror before upload. In CI it fails the build when a slow file sneaks in.
- **Encoding new videos with ffmpeg?** Add `-movflags +faststart` and they'll be right from the start.
- Fragmented MP4 (used for streaming) is already fine and is left alone.

## Limits
- The browser version refuses the rare file that would need 64-bit offsets after the move; use the CLI for those.
- MP4 family only (`.mp4 .m4v .mov .m4a .3gp`). WebM/MKV have their own layout and aren't covered.

## Development
```bash
python3 -m venv .venv && .venv/bin/pip install pytest -e .
.venv/bin/pytest -q          # Python tests
node tests/test_js.mjs       # browser module test (needs ffmpeg)
```

MIT licence. Made by [Peak Software](https://peaksoftware.co.za).
