# PosseTool 

A utility to syndicate blog posts to social media platforms.

Written in Python 3.x

## Overview

This script downloads and parses an Atom/RSS feed from a URL provided on the command line. It maintains a history of processed entries to avoid duplicate syndication, ensuring each entry is only posted once.

The script supports multiple social media platforms and can automatically extract images from blog posts to create rich link cards.

## Features

- **Feed Processing**: Supports both Atom and RSS feeds
- **Image Extraction**: Automatically extracts images from HTML content
- **Rich Link Cards**: Creates unfurled link previews with images
- **Multiple Platforms**: Supports Bluesky and Mastodon
- **UTF-8 Handling**: Proper Unicode normalization and encoding
- **Test Mode**: Dry-run mode for testing without posting
- **History Tracking**: Prevents duplicate posts across runs

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### Credentials File

Create a `creds.yaml` file with your service credentials:

```yaml
bsky:
  identifier: "your-handle.bsky.social"
  password: "your-password"

mastodon:
  access_token: "your-access-token"
  api_base_url: "https://your.instance.com"
```

### Feed Categories

Add trigger tags to your feed entries to control syndication:

```xml
<!-- Post to specific services -->
<category term="bsky" />
<category term="mastodon" />

<!-- Post to all services -->
<category term="posse" />
```

## Usage

### Basic Usage

```bash
python PosseTool.py --feed https://example.com/feed.xml --history history.txt
```

### With Credentials

```bash
python PosseTool.py -f https://example.com/feed.xml -H history.txt -c creds.yaml
```

### Test Mode

```bash
python PosseTool.py -f https://example.com/feed.xml -H history.txt -c creds.yaml -t
```

### Verbose Output

```bash
python PosseTool.py -f https://example.com/feed.xml -H history.txt -c creds.yaml -v
```

## Command Line Arguments

- `--feed, -f`: URL of the Atom/RSS feed to process (required)
- `--history, -H`: Path to history file for tracking processed entries (required)
- `--creds, -c`: Path to YAML credentials file for social media services
- `--test, -t`: Test mode - simulate syndication without actually posting
- `--verbose, -v`: Enable verbose output with debug information

## Supported Platforms

### Bluesky

- **Library**: atproto
- **Features**: 
  - Clickable links in text
  - Rich external embeds with images
  - Automatic image processing (resize to 1200x630, compress to <900KB)
  - 300 character limit
- **Trigger Tag**: `bsky`

### Mastodon

- **Library**: mastodon.py
- **Features**:
  - Automatic link card generation
  - Rich link previews with images
  - 500 character limit
  - Public visibility posts
- **Trigger Tag**: `mastodon`

## Image Processing

The script automatically:

1. **Extracts images** from HTML content in feed entries
2. **Downloads images** from URLs
3. **Processes images** for platform requirements:
   - Resizes to 1200x630 (Bluesky)
   - Compresses to under 900KB
   - Converts to JPEG format
   - Handles transparency with white backgrounds
4. **Uploads images** to create rich link cards

## Trigger Tags

### Individual Services
- `bsky`: Post to Bluesky only
- `mastodon`: Post to Mastodon only

### Universal Publishing
- `posse`: Post to all configured services

### Examples

```xml
<!-- Post to specific services -->
<category term="bsky" />
<category term="mastodon" />

<!-- Post to all services -->
<category term="posse" />

<!-- Mixed (posse takes precedence) -->
<category term="posse" />
<category term="bsky" />
<!-- Result: Posts to both Bluesky and Mastodon -->
```

## Error Handling

- **Graceful failures**: Individual service failures don't stop other services
- **UTF-8 normalization**: Handles encoding issues automatically
- **Image fallbacks**: Continues without images if processing fails
- **Authentication errors**: Clear error messages for credential issues

## Development

The script is designed with a modular architecture:

- **Base class**: `SyndicationService` for common functionality
- **Platform services**: `BlueskyService`, `MastodonService`
- **Helper functions**: Image processing, text cleaning, feed parsing
- **Constants**: Configurable limits and settings

## Requirements

- Python 3.x
- requests>=2.25.0
- pyyaml>=6.0
- atproto>=0.0.40
- Pillow>=10.0.0
- mastodon.py>=1.8.0

