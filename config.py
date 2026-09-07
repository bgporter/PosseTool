"""
Configuration constants for PosseTool.
"""

# Bluesky configuration
BLUESKY_CHAR_LIMIT = 300
BLUESKY_IMAGE_MAX_SIZE = 900 * 1024  # 900KB in bytes
BLUESKY_IMAGE_TARGET_WIDTH = 1200
BLUESKY_IMAGE_TARGET_HEIGHT = 630
BLUESKY_IMAGE_QUALITY_START = 95
BLUESKY_IMAGE_QUALITY_MIN = 10
BLUESKY_IMAGE_QUALITY_STEP = 5
BLUESKY_DESCRIPTION_LIMIT = 200

# Mastodon configuration
MASTODON_CHAR_LIMIT = 500

# Text processing configuration
DEFAULT_MAX_LENGTH = 300

# Marks a feed <summary> as the blog engine's auto-truncated fallback rather
# than an author-written teaser. See docs/adr/0001-detect-authored-summary-by-truncation-suffix.md
SUMMARY_TRUNCATION_SUFFIX = '…'

# Feed category terms that control syndication routing rather than being
# genuine content tags.
RESERVED_TRIGGER_TAGS = {'posse', 'bsky', 'mastodon'} 