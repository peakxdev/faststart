"""Find and fix MP4/MOV files that start slowly on the web.

A video only starts playing once the player has read its index (the ``moov``
atom). Many encoders write that index at the *end* of the file, so a browser
or phone has to fetch the end before it can play the start. ``faststart``
finds those files and moves the index to the front without re-encoding.
"""

__version__ = "0.1.0"

from .atoms import Layout, read_layout  # noqa: F401
