# PosseTool - Modular Structure

This document describes the modular structure of PosseTool after refactoring from a monolithic script.

## Module Structure

```
PosseTool/
├── config.py              # Configuration constants
├── feed.py                # Feed downloading and parsing
├── text_processing.py     # Text cleaning and paragraph extraction
├── main.py               # Main script and CLI
├── services/             # Syndication services
│   ├── __init__.py       # Service factory
│   ├── base.py           # Base service class
│   ├── bluesky.py        # Bluesky service
│   └── mastodon.py       # Mastodon service
└── PosseTool.py          # Original monolithic script (kept for reference)
```

## Module Descriptions

### `config.py`
Contains all configuration constants:
- Bluesky character limits and image settings
- Mastodon character limits
- Default text processing limits

### `feed.py`
Handles feed-related functionality:
- `download_feed()` - Downloads and normalizes feed content
- `parse_feed()` - Parses XML and extracts entries
- `load_history()` / `save_history()` - Manages processed entry history
- Helper functions for XML parsing and text extraction

### `text_processing.py`
Text processing and content extraction:
- `clean_html_text()` - Removes HTML tags and entities
- `extract_first_meaningful_paragraph()` - Extracts meaningful content from HTML

### `services/`
Service-related modules:

#### `services/__init__.py`
- `get_syndication_services()` - Factory function to create service instances

#### `services/base.py`
- `SyndicationService` - Base class for all syndication services
- Common functionality like test mode logging

#### `services/bluesky.py`
- `BlueskyService` - Bluesky-specific implementation
- Image processing and upload
- Link facets and external embeds

#### `services/mastodon.py`
- `MastodonService` - Mastodon-specific implementation
- Simple text posting with automatic link previews

### `main.py`
Main script that ties everything together:
- Command line argument parsing
- Credential loading
- Feed processing orchestration
- Entry syndication logic

## Benefits of Modular Structure

1. **Separation of Concerns**: Each module has a specific responsibility
2. **Maintainability**: Easier to find and modify specific functionality
3. **Testability**: Individual modules can be tested in isolation
4. **Extensibility**: New services can be added by creating new modules
5. **Reusability**: Modules can be imported and used independently

## Usage

The modular version works exactly like the original:

```bash
# Basic usage
python3 PosseTool.py --feed https://example.com/feed.xml --history history.txt

# With custom credentials
python3 PosseTool.py --feed https://example.com/feed.xml --history history.txt --creds my_creds.yaml

# Test mode
python3 PosseTool.py --feed https://example.com/feed.xml --history history.txt --test

# Short form
python3 PosseTool.py -f https://example.com/feed.xml -H history.txt -c my_creds.yaml -t
```

## Migration from Monolithic Script

The original `PosseTool.py` is kept for reference. The modular version maintains all the same functionality:

- ✅ Feed downloading and parsing
- ✅ Text processing and paragraph extraction
- ✅ Bluesky syndication with image processing
- ✅ Mastodon syndication
- ✅ History management
- ✅ Test mode support
- ✅ All recent improvements (img-caption filtering, URL space reservation, etc.)

## Adding New Services

To add a new syndication service:

1. Create `services/newservice.py`
2. Inherit from `SyndicationService`
3. Implement required methods (`can_handle()`, `post()`, etc.)
4. Add to `services/__init__.py` factory function
5. Add credentials section to your `creds.yaml`

Example:
```python
# services/newservice.py
from .base import SyndicationService

class NewService(SyndicationService):
    def can_handle(self, trigger_tag):
        return trigger_tag == 'newservice'
    
    def post(self, entry):
        # Implementation here
        pass
```

## Dependencies

The modular version uses the same dependencies as the original:
- `requests` - HTTP requests
- `yaml` - Credential file parsing
- `PIL` - Image processing (Bluesky)
- `atproto` - Bluesky API
- `mastodon.py` - Mastodon API 