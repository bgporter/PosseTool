"""
Text processing functionality for PosseTool.
"""

import re
import html
import unicodedata

import config


def clean_html_text(text):
    """
    Clean HTML text by removing HTML entities and tags with proper UTF-8 handling.

    Args:
        text (str): HTML text to clean

    Returns:
        str: Cleaned text
    """
    if not text:
        return ''

    # Normalize Unicode characters first
    text = unicodedata.normalize('NFC', text)

    # Unescape HTML entities
    cleaned = html.unescape(text)

    # Remove HTML tags
    cleaned = re.sub(r'<[^>]+>', '', cleaned)

    # Remove extra whitespace and normalize spaces
    cleaned = re.sub(r'\s+', ' ', cleaned)

    # Remove any remaining control characters except newlines and tabs
    cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)

    return cleaned.strip()


def truncate_text(text, max_length):
    """
    Truncate text to fit within max_length, preferring to break at a sentence
    boundary and falling back to a word boundary with a trailing "...".

    Args:
        text (str): Text to truncate (assumed already HTML-cleaned)
        max_length (int): Maximum character length

    Returns:
        str: Truncated text
    """
    if len(text) <= max_length:
        return text

    # Try to truncate at the last sentence boundary that still fits
    current_text = ""
    for match in re.finditer(r'[.!?]', text):
        sentence = text[:match.end()].strip()
        if len(sentence) <= max_length:
            current_text = sentence
        else:
            break

    if current_text:
        return current_text

    # No sentence fits (or no sentence boundaries exist) - truncate at a word
    # boundary and reserve space for "..."
    available_space = max_length - 3
    words = text.split()
    current_text = ""
    for word in words:
        test_text = current_text + word + " "
        if len(test_text) <= available_space:
            current_text = test_text
        else:
            break

    current_text = current_text.strip()
    if current_text:
        current_text += "..."
    return current_text


def extract_first_meaningful_paragraph(content, max_length=300):
    """
    Extract the first meaningful paragraph from content that is not a heading, image link, or admonition.

    Args:
        content (str): HTML content to extract from
        max_length (int or None): Maximum length for the extracted text, or
            None to return the full paragraph untruncated

    Returns:
        str: Extracted paragraph text, truncated to fit within max_length
    """
    if not content:
        return ''

    # Normalize Unicode characters
    content = unicodedata.normalize('NFC', content)

    # Unescape HTML entities first
    content = html.unescape(content)

    # Handle common HTML entities that might not be handled by html.unescape
    content = content.replace('&amp;', '&')
    content = content.replace('&lt;', '<')
    content = content.replace('&gt;', '>')
    content = content.replace('&quot;', '"')
    content = content.replace('&apos;', "'")
    content = content.replace('&#39;', "'")
    content = content.replace('&#34;', '"')
    content = content.replace('&#60;', '<')
    content = content.replace('&#62;', '>')

    # Remove admonition divs and their contents before processing
    # This handles the case where admonitions span multiple paragraphs
    content = re.sub(r'<div[^>]*class\s*=\s*["\'][^"\']*admonition[^"\']*["\'][^>]*>.*?</div>', '', content, flags=re.DOTALL | re.IGNORECASE)

    # Split content into paragraphs (split on double newlines or <p> tags)
    # We need to handle <p> tags more carefully to include the full paragraph
    paragraphs = []

    # First split on double newlines
    newline_paragraphs = re.split(r'\n\s*\n', content)

    for paragraph in newline_paragraphs:
        # Check if this paragraph contains <p> tags
        if '<p' in paragraph:
            # Extract individual <p> elements
            p_tags = re.findall(r'<p[^>]*>.*?</p>', paragraph, re.DOTALL | re.IGNORECASE)
            paragraphs.extend(p_tags)
        else:
            paragraphs.append(paragraph)

    # Image-only paragraphs (a bare image URL or an <img> tag and nothing else)
    image_pattern = r'^\s*(https?://[^\s]+\.(jpg|jpeg|png|gif|webp|svg)|<img[^>]*>)\s*$'

    for paragraph in paragraphs:
        # Check for headings before cleaning HTML tags
        if re.match(r'^\s*<h[1-6][^>]*>.*?</h[1-6]>\s*$', paragraph, re.IGNORECASE | re.DOTALL):
            continue

        # Skip img-caption paragraphs (these are just image captions, not meaningful content)
        if re.search(r'class\s*=\s*["\'][^"\']*img-caption[^"\']*["\']', paragraph, re.IGNORECASE):
            continue

        # Clean the paragraph - remove HTML tags
        cleaned = re.sub(r'<[^>]+>', '', paragraph)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Skip empty paragraphs, or paragraphs that are just an image reference
        if not cleaned or re.match(image_pattern, cleaned, re.IGNORECASE):
            continue

        # If we get here, we have a meaningful paragraph
        if max_length is None or len(cleaned) <= max_length:
            return cleaned
        return truncate_text(cleaned, max_length)

    # If no meaningful paragraph found, return empty string
    return ''


def extract_hashtags_from_categories(categories, reserved_tags=None):
    """
    Extract hashtags from categories, filtering out reserved trigger tags.

    Args:
        categories (list): List of category terms from the feed entry
        reserved_tags (set): Set of reserved trigger tags to filter out.
            Defaults to config.RESERVED_TRIGGER_TAGS.

    Returns:
        set: Set of hashtag strings (without the # symbol)
    """
    if not categories:
        return set()

    if reserved_tags is None:
        reserved_tags = config.RESERVED_TRIGGER_TAGS

    # Convert categories to lowercase and filter out reserved tags
    hashtags = set()
    for category in categories:
        if category and category.lower() not in reserved_tags:
            # Clean the category term and add to hashtags
            cleaned = clean_html_text(category).strip()
            if cleaned:
                hashtags.add(cleaned.lower())

    return hashtags


def format_hashtags_for_post(hashtags, available_space):
    """
    Format hashtags to fit within available_space characters.

    Args:
        hashtags (set): Set of hashtag strings (without the # symbol)
        available_space (int): Character budget available for the hashtag line

    Returns:
        str: Formatted hashtag string (e.g. "#foo #bar"), or "" if none fit
    """
    if not hashtags or available_space <= 0:
        return ""

    # Sort hashtags for consistent ordering, add hashtags until space runs out
    hashtag_string = ""
    for hashtag in sorted(hashtags):
        hashtag_with_space = f"#{hashtag} "
        if len(hashtag_string + hashtag_with_space) <= available_space:
            hashtag_string += hashtag_with_space
        else:
            break

    return hashtag_string.strip()


def format_content_tags_for_card(categories, reserved_tags=None):
    """
    Format an entry's content tags as a plain-text line for a link-card
    description (e.g. "Tagged: music, weirdness").

    Args:
        categories (list): List of category terms from the feed entry
        reserved_tags (set): Set of reserved trigger tags to filter out

    Returns:
        str: Formatted tag line, or "" if there are no content tags
    """
    tags = extract_hashtags_from_categories(categories, reserved_tags)
    if not tags:
        return ""
    return "Tagged: " + ", ".join(sorted(tags))


def _is_authored_summary(cleaned_summary, cleaned_content):
    """
    Decide whether a feed entry's cleaned <summary> is an author-written
    teaser rather than the blog engine's auto-truncated fallback.

    Pelican (this project's blog engine) writes an explicit `Summary:`
    front-matter value into the feed verbatim; when no `Summary:` is set, it
    auto-generates one by truncating the raw content and appending
    config.SUMMARY_TRUNCATION_SUFFIX. We also refuse to trust a summary that's
    identical to the content, which happens for RSS feeds where no distinct
    summary is ever produced.
    """
    if not cleaned_summary:
        return False
    if cleaned_summary.endswith(config.SUMMARY_TRUNCATION_SUFFIX):
        return False
    if cleaned_summary == cleaned_content:
        return False
    return True


def compose_post_text(content, summary, categories, url, max_length, reserved_tags=None):
    """
    Compose the body text for a syndicated post.

    Prefers an author-written Summary over a paragraph extracted from the raw
    content, since a summary written specifically as a teaser reads far better
    standalone than whatever happens to be the first substantive paragraph of
    the article. Falls back to lede extraction when there's no usable authored
    summary.

    Fills any remaining space with content-tag hashtags, then the URL. If the
    body text alone doesn't fit within max_length, hashtags are dropped first
    and the body text is truncated only as a last resort.

    Args:
        content (str): The entry's full HTML content
        summary (str): The entry's feed <summary>
        categories (list): The entry's category terms
        url (str): The entry's URL, or "" to omit it
        max_length (int): Character limit for the whole post
        reserved_tags (set): Trigger tags to exclude from content tags

    Returns:
        str: Composed post text
    """
    cleaned_summary = clean_html_text(summary) if summary else ''
    cleaned_content = clean_html_text(content) if content else ''

    if _is_authored_summary(cleaned_summary, cleaned_content):
        body_text = cleaned_summary
    else:
        body_text = extract_first_meaningful_paragraph(content, max_length=None) if content else ''
        if not body_text:
            body_text = cleaned_summary

    url_suffix = f"\n\n{url}" if url else ''
    available_for_body_and_tags = max_length - len(url_suffix)

    if len(body_text) > available_for_body_and_tags:
        return truncate_text(body_text, available_for_body_and_tags) + url_suffix

    hashtags = extract_hashtags_from_categories(categories, reserved_tags)
    available_for_hashtags = available_for_body_and_tags - len(body_text) - 1  # 1 for the separating newline
    hashtag_string = format_hashtags_for_post(hashtags, available_for_hashtags)

    if hashtag_string:
        return f"{body_text}\n{hashtag_string}{url_suffix}"
    return f"{body_text}{url_suffix}"
