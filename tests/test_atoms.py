import shutil
import struct
import subprocess

import pytest

from faststart.atoms import read_layout
from faststart.cli import main


def atom(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def write(tmp_path, name, *atoms):
    p = tmp_path / name
    p.write_bytes(b"".join(atoms))
    return p


def test_moov_first_is_faststart(tmp_path):
    p = write(tmp_path, "a.mp4", atom(b"ftyp", b"isom"), atom(b"moov", b"x" * 20), atom(b"mdat", b"y" * 100))
    assert read_layout(p).is_faststart


def test_moov_last_is_slow(tmp_path):
    p = write(tmp_path, "b.mp4", atom(b"ftyp", b"isom"), atom(b"mdat", b"y" * 100), atom(b"moov", b"x" * 20))
    layout = read_layout(p)
    assert layout.has_moov and not layout.is_faststart


def test_64bit_size(tmp_path):
    big = struct.pack(">I4sQ", 1, b"mdat", 16 + 4) + b"data"
    p = write(tmp_path, "c.mp4", atom(b"ftyp"), big, atom(b"moov"))
    assert [a[0] for a in read_layout(p).atoms] == ["ftyp", "mdat", "moov"]


def test_check_exit_codes(tmp_path, capsys):
    good = write(tmp_path, "good.mp4", atom(b"ftyp"), atom(b"moov"), atom(b"mdat"))
    bad = write(tmp_path, "bad.mp4", atom(b"ftyp"), atom(b"mdat"), atom(b"moov"))
    assert main(["check", str(good)]) == 0
    assert main(["check", str(tmp_path)]) == 1
    assert "slow" in capsys.readouterr().out and bad.name


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_fix_real_file(tmp_path):
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=1:size=160x90:rate=10",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    assert not read_layout(src).is_faststart  # ffmpeg's default puts moov at the end
    assert main(["fix", "--in-place", str(src)]) == 0
    assert read_layout(src).is_faststart
