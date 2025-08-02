#!/usr/bin/env python3
"""
PosseTool - A utility to syndicate blog posts to social media.

This script downloads and parses an atom feed from a URL provided on the command line.
It maintains a history of processed entries to avoid duplicate syndication.
"""

import sys
import os
import re
import argparse
import requests
import xml.etree.ElementTree as ET
import html
import yaml
import unicodedata
import tempfile
import urllib.parse
import io
from urllib.parse import urlparse
from pathlib import Path

# Constants
BLUESKY_CHAR_LIMIT = 300
BLUESKY_IMAGE_MAX_SIZE = 900 * 1024  # 900KB in bytes
BLUESKY_IMAGE_TARGET_WIDTH = 1200
BLUESKY_IMAGE_TARGET_HEIGHT = 630
BLUESKY_IMAGE_QUALITY_START = 95
BLUESKY_IMAGE_QUALITY_MIN = 10
BLUESKY_IMAGE_QUALITY_STEP = 5
BLUESKY_DESCRIPTION_LIMIT = 200


def download_feed(feed_url):
    """
    Download the atom feed from the provided URL with proper UTF-8 handling.
    
    Args:
        feed_url (str): The URL of the atom feed
        
    Returns:
        str: The XML content of the feed
        
    Raises:
        requests.RequestException: If the feed cannot be downloaded
    """
    try:
        response = requests.get(feed_url, timeout=30)
        response.raise_for_status()
        
        # Explicitly decode as UTF-8 to avoid encoding issues
        # This fixes the "Â" character issue where non-breaking spaces are misdecoded
        content = response.content.decode('utf-8', errors='replace')
        
        # Normalize Unicode to handle any remaining encoding inconsistencies
        content = unicodedata.normalize('NFC', content)
        
        return content
    except requests.RequestException as e:
        print(f"Error downloading feed from {feed_url}: {e}")
        return None


def safe_text(element):
    """
    Safely extract text from an XML element with proper UTF-8 handling.
    
    Args:
        element: XML element or None
        
    Returns:
        str: Text content or empty string
    """
    if element is not None and element.text is not None:
        # Ensure proper UTF-8 encoding
        text = element.text.strip()
        # Normalize Unicode characters
        text = unicodedata.normalize('NFC', text)
        return text
    return ''


def extract_url_from_link(link_element, is_rss=False):
    """
    Extract URL from a link element.
    
    Args:
        link_element: XML link element or None
        is_rss (bool): Whether this is RSS format (affects extraction method)
        
    Returns:
        str: URL or empty string
    """
    if link_element is None:
        return ''
    
    if is_rss:
        return safe_text(link_element)
    else:
        href = link_element.get('href')
        return href if href else ''


def extract_categories(category_elements, is_rss=False):
    """
    Extract category tags from category elements.
    
    Args:
        category_elements: List of XML category elements
        is_rss (bool): Whether this is RSS format (affects extraction method)
        
    Returns:
        list: List of category terms
    """
    category_tags = []
    for category in category_elements:
        if is_rss:
            term = safe_text(category)
        else:
            term = category.get('term')
        
        if term:
            category_tags.append(term)
    
    return category_tags


def create_entry_dict(entry_id, title, content, summary, url, categories):
    """
    Create a standardized entry dictionary.
    
    Args:
        entry_id: Entry ID element
        title: Title element
        content: Content element
        summary: Summary element
        url (str): URL string
        categories (list): List of category terms
        
    Returns:
        dict: Standardized entry dictionary
    """
    return {
        'id': safe_text(entry_id),
        'title': safe_text(title) if title is not None else 'Untitled',
        'content': safe_text(content),
        'summary': safe_text(summary),
        'url': url,
        'categories': categories
    }


def parse_feed(xml_content):
    """
    Parse the XML content and extract feed entries.
    
    Args:
        xml_content (str): The XML content of the feed
        
    Returns:
        list: List of dictionaries containing entry data
    """
    try:
        root = ET.fromstring(xml_content)
        
        # Handle both atom and RSS feeds
        if 'Atom' in root.tag or 'atom' in root.tag or 'http://www.w3.org/2005/Atom' in root.tag:
            # Atom feed
            entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            # Also try without namespace
            entries_no_ns = root.findall('.//entry')
            
            # Use the approach that found entries
            if len(entries) > 0:
                entries_to_process = entries
                ns_prefix = '{http://www.w3.org/2005/Atom}'
            elif len(entries_no_ns) > 0:
                entries_to_process = entries_no_ns
                ns_prefix = ''
            else:
                return []
            
            entries_data = []
            
            for entry in entries_to_process:
                entry_id = entry.find(f'{ns_prefix}id')
                title = entry.find(f'{ns_prefix}title')
                content = entry.find(f'{ns_prefix}content')
                summary = entry.find(f'{ns_prefix}summary')
                link = entry.find(f'{ns_prefix}link')
                categories = entry.findall(f'{ns_prefix}category')
                
                if entry_id is not None:
                    # Extract URL and categories using helper functions
                    url = extract_url_from_link(link, is_rss=False)
                    category_tags = extract_categories(categories, is_rss=False)
                    
                    # Create entry dictionary using helper function
                    entry_dict = create_entry_dict(entry_id, title, content, summary, url, category_tags)
                    entries_data.append(entry_dict)
        else:
            # RSS feed
            entries = root.findall('.//item')
            entries_data = []
            
            for entry in entries:
                entry_id = entry.find('guid')
                title = entry.find('title')
                content = entry.find('description')
                link = entry.find('link')
                categories = entry.findall('category')
                
                if entry_id is not None:
                    # Extract URL and categories using helper functions
                    url = extract_url_from_link(link, is_rss=True)
                    category_tags = extract_categories(categories, is_rss=True)
                    
                    # Create entry dictionary using helper function
                    # Note: For RSS, content is used as both content and summary
                    entry_dict = create_entry_dict(entry_id, title, content, content, url, category_tags)
                    entries_data.append(entry_dict)
        
        return entries_data
        
    except ET.ParseError as e:
        print(f"Error parsing XML feed: {e}")
        return []


def load_history(history_file):
    """
    Load the history of processed entry IDs from the history file.
    
    Args:
        history_file (str): Path to the history file
        
    Returns:
        set: Set of processed entry IDs
    """
    processed_ids = set()
    
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    entry_id = line.strip()
                    if entry_id:
                        processed_ids.add(entry_id)
        except IOError as e:
            print(f"Error reading history file {history_file}: {e}")
            return processed_ids
    
    return processed_ids


def save_history(history_file, processed_ids):
    """
    Save the updated history of processed entry IDs to the history file.
    
    Args:
        history_file (str): Path to the history file
        processed_ids (set): Set of processed entry IDs
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            for entry_id in sorted(processed_ids):
                f.write(f"{entry_id}\n")
        return True
    except IOError as e:
        print(f"Error writing history file {history_file}: {e}")
        return False





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


def extract_first_meaningful_paragraph(content, max_length=300):
    """
    Extract the first meaningful paragraph from content that is not a heading, image link, or admonition.
    
    Args:
        content (str): HTML content to extract from
        max_length (int): Maximum length for the extracted text
        
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
    
    # Split content into paragraphs (split on double newlines or <p> tags)
    paragraphs = re.split(r'\n\s*\n|<p[^>]*>', content)
    
    for paragraph in paragraphs:
        # Check for headings before cleaning HTML tags
        if re.match(r'^\s*<h[1-6][^>]*>.*?</h[1-6]>\s*$', paragraph, re.IGNORECASE | re.DOTALL):
            continue
        
        # Clean the paragraph - remove HTML tags
        cleaned = re.sub(r'<[^>]+>', '', paragraph)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Skip empty paragraphs
        if not cleaned:
            continue
        
        # Skip image links (lines that are just image URLs or img tags)
        if re.match(r'^\s*(https?://[^\s]+\.(jpg|jpeg|png|gif|webp|svg))\s*$', cleaned, re.IGNORECASE):
            continue
        if re.match(r'^\s*<img[^>]*>\s*$', cleaned):
            continue
        
        # Skip paragraphs that contain only image-related content
        # Check if the paragraph contains only image URLs or HTML images
        image_patterns = [
            r'^\s*(https?://[^\s]+\.(jpg|jpeg|png|gif|webp|svg))\s*$',
            r'^\s*<img[^>]*>\s*$'
        ]
        
        # If the paragraph matches any image pattern exactly, skip it
        if any(re.match(pattern, cleaned, re.IGNORECASE) for pattern in image_patterns):
            continue
        
        # Also check if the paragraph contains only image-related content (multiple images)
        # Remove all image patterns and see if anything is left
        temp_cleaned = cleaned
        for pattern in image_patterns:
            temp_cleaned = re.sub(pattern, '', temp_cleaned, flags=re.IGNORECASE)
        
        # If nothing is left after removing all image patterns, skip this paragraph
        if not temp_cleaned.strip():
            continue
        
        # If we get here, we have a meaningful paragraph
        # Truncate to fit within max_length
        if len(cleaned) <= max_length:
            return cleaned
        else:
            # Try to truncate at sentence boundaries
            # Find sentence boundaries while preserving original punctuation
            sentence_endings = re.finditer(r'[.!?]', cleaned)
            current_text = ""
            
            for match in sentence_endings:
                end_pos = match.end()
                sentence = cleaned[:end_pos].strip()
                
                if len(sentence) <= max_length:
                    current_text = sentence
                else:
                    # If even the first sentence is too long, truncate at word boundaries
                    if not current_text:
                        words = cleaned.split()
                        for word in words:
                            test_text = current_text + word + " "
                            if len(test_text) <= max_length:
                                current_text = test_text
                            else:
                                break
                        current_text = current_text.strip()
                        if current_text and not current_text.endswith('.'):
                            current_text += "..."
                    break
            
            return current_text.strip()
        
        # If no sentence boundaries found, truncate at word boundaries
        if len(cleaned) > max_length:
            words = cleaned.split()
            current_text = ""
            for word in words:
                test_text = current_text + word + " "
                if len(test_text) <= max_length:
                    current_text = test_text
                else:
                    break
            current_text = current_text.strip()
            if current_text and not current_text.endswith('.'):
                current_text += "..."
            return current_text
    
    # If no meaningful paragraph found, return empty string
    return ''


class SyndicationService:
    """Base class for social media syndication services."""
    
    def __init__(self, credentials, test_mode=False):
        self.credentials = credentials
        self.test_mode = test_mode
    
    def can_handle(self, trigger_tag):
        """Check if this service can handle the given trigger tag."""
        return False
    
    def post(self, entry):
        """Post an entry to the service. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def _log_test_post(self, service_name, entry_title, post_content):
        """Log what would be posted in test mode."""
        if self.test_mode:
            print(f"[TEST MODE] Would post to {service_name}: {entry_title}")
            print(f"[TEST MODE] Post content ({len(post_content)} chars):")
            print(f"---")
            print(post_content)
            print(f"---")
    
    def _log_test_error(self, service_name, error):
        """Log what error would occur in test mode."""
        if self.test_mode:
            print(f"[TEST MODE] Would fail to post to {service_name}: {error}")


class BlueskyService(SyndicationService):
    """Bluesky syndication service using atproto."""
    
    def __init__(self, credentials, test_mode=False):
        super().__init__(credentials, test_mode)
        self.client = None
    
    def can_handle(self, trigger_tag):
        return trigger_tag == 'bsky'
    
    def authenticate(self):
        """Authenticate with Bluesky using credentials."""
        try:
            from atproto import Client
            self.client = Client()
            self.client.login(
                self.credentials.get('identifier'),
                self.credentials.get('password')
            )
            return True
        except Exception as e:
            print(f"Bluesky authentication failed: {e}")
            return False
    
    def _prepare_post_text(self, entry):
        """Prepare the post text and facets."""
        url = entry.get('url', '')
        
        # Calculate available space for text (reserve space for URL first)
        if url:
            available_space = BLUESKY_CHAR_LIMIT - len(url) - 2  # 2 for "\n\n"
        else:
            available_space = BLUESKY_CHAR_LIMIT
        
        # Extract first meaningful paragraph from content with the available space
        content = entry.get('content', '')
        post_text = extract_first_meaningful_paragraph(content, available_space)
        
        # If no meaningful paragraph found, fall back to summary
        if not post_text:
            summary = clean_html_text(entry.get('summary', ''))
            post_text = unicodedata.normalize('NFC', summary)
            # Truncate summary if needed
            if len(post_text) > available_space:
                post_text = post_text[:available_space-3] + "..."
        
        # Add URL if available
        facets = []
        if url:
            post_text += f"\n\n{url}"
            facets.append(self._create_link_facet(post_text, url))
        
        return post_text, facets
    
    def _create_link_facet(self, post_text, url):
        """Create a link facet for the given URL."""
        link_start = len(post_text) - len(url)
        link_end = len(post_text)
        return {
            "index": {
                "byteStart": link_start,
                "byteEnd": link_end
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#link",
                "uri": url
            }]
        }
    
    def _extract_image_from_content(self, content):
        """Extract the first image URL from HTML content."""
        if not content:
            return None
        
        # Unescape HTML entities
        unescaped_content = html.unescape(content)
        
        # Find the first <img> tag
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', unescaped_content)
        if img_match:
            return img_match.group(1)
        return None
    
    def _process_image(self, image_url):
        """Download, process, and upload an image to Bluesky."""
        if not image_url:
            return None
        
        temp_image_path = None
        try:
            # Download the image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Determine file extension
            extension = self._get_image_extension(image_url, response.headers)
            
            # Create temporary file
            temp_fd, temp_image_path = tempfile.mkstemp(suffix=extension)
            os.close(temp_fd)
            
            # Process and save image
            self._resize_and_compress_image(response.content, temp_image_path)
            
            # Upload to Bluesky
            with open(temp_image_path, 'rb') as f:
                img_data = f.read()
            upload_response = self.client.upload_blob(img_data)
            return upload_response.blob
            
        except Exception as e:
            print(f"Warning: Failed to upload image {image_url}: {e}")
            return None
        finally:
            # Clean up temporary file
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.unlink(temp_image_path)
                except Exception as e:
                    print(f"Warning: Failed to delete temporary image {temp_image_path}: {e}")
    
    def _get_image_extension(self, image_url, headers):
        """Determine the file extension from URL or content type."""
        # Try to get extension from URL
        parsed_url = urllib.parse.urlparse(image_url)
        url_path = Path(parsed_url.path)
        extension = url_path.suffix
        
        # If no extension in URL, try to get from content type
        if not extension:
            content_type = headers.get('content-type', '')
            if 'png' in content_type:
                extension = '.png'
            elif 'gif' in content_type:
                extension = '.gif'
            elif 'webp' in content_type:
                extension = '.webp'
            else:
                extension = '.jpg'  # Default fallback
        
        return extension
    
    def _resize_and_compress_image(self, image_data, output_path):
        """Resize and compress image to meet Bluesky requirements."""
        from PIL import Image
        
        # Open the image
        img = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Calculate new size maintaining aspect ratio
        target_width, target_height = BLUESKY_IMAGE_TARGET_WIDTH, BLUESKY_IMAGE_TARGET_HEIGHT
        img_width, img_height = img.size
        
        scale_x = target_width / img_width
        scale_y = target_height / img_height
        scale = min(scale_x, scale_y)
        
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        # Resize the image
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create final image with target size and white background
        final_img = Image.new('RGB', (target_width, target_height), (255, 255, 255))
        
        # Center the resized image
        x_offset = (target_width - new_width) // 2
        y_offset = (target_height - new_height) // 2
        final_img.paste(img, (x_offset, y_offset))
        
        # Save with compression to meet size requirements
        output_buffer = io.BytesIO()
        quality = BLUESKY_IMAGE_QUALITY_START
        
        while quality > BLUESKY_IMAGE_QUALITY_MIN:
            output_buffer.seek(0)
            output_buffer.truncate()
            final_img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
            
            if output_buffer.tell() <= BLUESKY_IMAGE_MAX_SIZE:
                break
            quality -= BLUESKY_IMAGE_QUALITY_STEP
        
        # Save the processed image
        with open(output_path, 'wb') as f:
            f.write(output_buffer.getvalue())
    
    def _create_external_embed(self, url, entry, summary, image_blob_ref):
        """Create an external embed for the URL."""
        from atproto import models
        
        external_link = models.AppBskyEmbedExternal.External(
            uri=url,
            title=entry.get('title', ''),
            description=summary[:BLUESKY_DESCRIPTION_LIMIT] if summary else '',
            thumb=image_blob_ref
        )
        
        return models.AppBskyEmbedExternal.Main(external=external_link)
    
    def post(self, entry):
        """Post a skeet to Bluesky."""
        if not self.client and not self.test_mode:
            if not self.authenticate():
                return False
        
        try:
            # Prepare post text and facets
            post_text, facets = self._prepare_post_text(entry)
            
            if self.test_mode:
                self._log_test_post("Bluesky", entry['title'], post_text)
                return True
            
            # Handle posting with or without embed
            url = entry.get('url', '')
            if url:
                # Extract and process image
                content = entry.get('content', '')
                image_url = self._extract_image_from_content(content)
                image_blob_ref = self._process_image(image_url) if image_url else None
                
                # Create embed and post
                embed = self._create_external_embed(url, entry, post_text, image_blob_ref)
                self.client.send_post(text=post_text, facets=facets, embed=embed)
            else:
                # Post without embed
                self.client.send_post(text=post_text, facets=facets)
            
            print(f"Posted to Bluesky: {entry['title']}")
            return True
            
        except Exception as e:
            if self.test_mode:
                self._log_test_error("Bluesky", e)
                return False
            else:
                print(f"Failed to post to Bluesky: {e}")
                return False


def load_credentials(creds_file):
    """
    Load credentials from YAML file.
    
    Args:
        creds_file (str): Path to YAML credentials file
        
    Returns:
        dict: Credentials for each service
    """
    if not creds_file or not os.path.exists(creds_file):
        return {}
    
    try:
        with open(creds_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading credentials file {creds_file}: {e}")
        return {}


def get_syndication_services(credentials, test_mode=False):
    """
    Get available syndication services based on credentials.
    
    Args:
        credentials (dict): Service credentials
        test_mode (bool): Whether to run in test mode
        
    Returns:
        list: List of SyndicationService instances
    """
    services = []
    
    # Add Bluesky service if credentials are available
    if 'bsky' in credentials:
        services.append(BlueskyService(credentials['bsky'], test_mode))
    
    # Add Mastodon service if credentials are available
    if 'mastodon' in credentials:
        services.append(MastodonService(credentials['mastodon'], test_mode))
    
    return services


class MastodonService(SyndicationService):
    """Mastodon syndication service using mastodon.py."""
    
    def __init__(self, credentials, test_mode=False):
        super().__init__(credentials, test_mode)
        self.client = None
    
    def can_handle(self, trigger_tag):
        return trigger_tag == 'mastodon'
    
    def authenticate(self):
        """Authenticate with Mastodon using credentials."""
        try:
            from mastodon import Mastodon
            
            # Create the client
            self.client = Mastodon(
                access_token=self.credentials.get('access_token'),
                api_base_url=self.credentials.get('api_base_url')
            )
            
            # Test the connection by getting account info
            try:
                account = self.client.account_verify_credentials()
                print(f"DEBUG: Successfully authenticated with Mastodon as @{account['username']}")
                return True
            except Exception as e:
                print(f"DEBUG: Authentication test failed: {e}")
                return False
                
        except Exception as e:
            print(f"Mastodon authentication failed: {e}")
            return False
    
    def _prepare_post_text(self, entry):
        """Prepare the post text for Mastodon."""
        url = entry.get('url', '')
        
        # Calculate available space for text (reserve space for URL first)
        if url:
            available_space = 500 - len(url) - 2  # 2 for "\n\n" and Mastodon has 500 char limit
        else:
            available_space = 500
        
        # Extract first meaningful paragraph from content with the available space
        content = entry.get('content', '')
        post_text = extract_first_meaningful_paragraph(content, available_space)
        
        # If no meaningful paragraph found, fall back to summary
        if not post_text:
            summary = clean_html_text(entry.get('summary', ''))
            post_text = unicodedata.normalize('NFC', summary)
            # Truncate summary if needed
            if len(post_text) > available_space:
                post_text = post_text[:available_space-3] + "..."
        
        # Add URL if available
        if url:
            post_text += f"\n\n{url}"
        
        return post_text
    

    
    def post(self, entry):
        """Post a toot to Mastodon."""
        if not self.client and not self.test_mode:
            if not self.authenticate():
                return False
        
        try:
            # Prepare post text
            post_text = self._prepare_post_text(entry)
            
            if self.test_mode:
                self._log_test_post("Mastodon", entry['title'], post_text)
                return True
            
            # Post the toot (Mastodon handles link previews automatically)
            print(f"DEBUG: Posting to Mastodon with text length: {len(post_text)}")
            
            self.client.status_post(
                post_text,
                visibility='public'  # Explicitly set visibility
            )
            
            print(f"Posted to Mastodon: {entry['title']}")
            return True
            
        except Exception as e:
            if self.test_mode:
                self._log_test_error("Mastodon", e)
                return False
            else:
                print(f"Failed to post to Mastodon: {e}")
                return False


def process_syndication(entry, services):
    """
    Process syndication for an entry based on its categories.
    
    Args:
        entry (dict): Entry data
        services (list): List of SyndicationService instances
        
    Returns:
        bool: True if at least one service processed the entry
    """
    categories = entry.get('categories', [])
    processed = False
    
    print(f"DEBUG: Processing entry '{entry.get('title', 'Unknown')}' with categories: {categories}")
    print(f"DEBUG: Available services: {[service.__class__.__name__ for service in services]}")
    
    # Check if "posse" category is present - if so, all services should publish
    should_publish_all = 'posse' in categories
    
    for service in services:
        service_processed = False
        
        if should_publish_all:
            # If "posse" is present, all services should publish
            print(f"DEBUG: 'posse' category found - {service.__class__.__name__} will handle all entries")
            if service.post(entry):
                processed = True
                service_processed = True
                print(f"DEBUG: {service.__class__.__name__} successfully posted (posse)")
            else:
                print(f"DEBUG: {service.__class__.__name__} failed to post (posse)")
        else:
            # Normal category-based processing
            for category in categories:
                print(f"DEBUG: Checking if {service.__class__.__name__} can handle '{category}'")
                if service.can_handle(category):
                    print(f"DEBUG: {service.__class__.__name__} will handle '{category}'")
                    if service.post(entry):
                        processed = True
                        service_processed = True
                        print(f"DEBUG: {service.__class__.__name__} successfully posted")
                    else:
                        print(f"DEBUG: {service.__class__.__name__} failed to post")
                    break  # Only process once per service, but continue to next service
        
        if service_processed:
            print(f"DEBUG: {service.__class__.__name__} processed this entry") 
    
    return processed


def parse_arguments():
    """
    Parse command line arguments using argparse.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="PosseTool - A utility to syndicate blog posts to social media",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python PosseTool.py --feed https://example.com/feed.xml --history /path/to/history.txt
  python PosseTool.py -f https://example.com/feed.xml -H /path/to/history.txt
  python PosseTool.py -f https://example.com/feed.xml -H /path/to/history.txt -c /path/to/creds.yaml
  python PosseTool.py -f https://example.com/feed.xml -H /path/to/history.txt -c /path/to/creds.yaml -t
        """
    )
    
    parser.add_argument(
        '--feed', '-f',
        required=True,
        help='URL of the atom/RSS feed to process'
    )
    
    parser.add_argument(
        '--history', '-H',
        required=True,
        help='Path to the history file for tracking processed entries'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        default='.',
        help='Directory to write XML files (default: current directory)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--creds', '-c',
        help='Path to YAML credentials file for social media services'
    )
    
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Test mode: simulate syndication without actually posting'
    )
    
    return parser.parse_args()


def main():
    """
    Main function to process the feed and handle syndication.
    """
    args = parse_arguments()
    
    feed_url = args.feed
    history_file = args.history
    output_dir = args.output_dir
    verbose = args.verbose
    creds_file = args.creds
    test_mode = args.test
    
    if verbose:
        print(f"Processing feed: {feed_url}")
        print(f"History file: {history_file}")
        print(f"Output directory: {output_dir}")
        if creds_file:
            print(f"Credentials file: {creds_file}")
    
    # Load credentials and initialize syndication services
    credentials = load_credentials(creds_file)
    services = get_syndication_services(credentials, test_mode)
    
    if verbose and services:
        print(f"Loaded {len(services)} syndication service(s)")
        for service in services:
            print(f"  - {service.__class__.__name__}")
    
    if test_mode:
        print("[TEST MODE] Running in test mode - no actual posts will be made")
    
    # Download and parse the feed
    xml_content = download_feed(feed_url)
    if xml_content is None:
        print(f"Failed to download feed from {feed_url}")
        return
    
    entries = parse_feed(xml_content)
    
    if verbose:
        print(f"Found {len(entries)} entries in feed")
    else:
        print(f"Found {len(entries)} entries in feed")
    
    # Load existing history
    processed_ids = load_history(history_file)
    
    # Check if this is the first run (history file doesn't exist)
    is_first_run = not os.path.exists(history_file)
    
    if is_first_run:
        print("First run detected. Adding all entries to history without processing.")
        # Add all entry IDs to history
        for entry in entries:
            processed_ids.add(entry['id'])
        save_history(history_file, processed_ids)
        print(f"Added {len(entries)} entries to history file.")
        return
    
    # Process new entries
    new_entries = []
    for entry in entries:
        if entry['id'] not in processed_ids:
            new_entries.append(entry)
            processed_ids.add(entry['id'])
    
    if new_entries:
        print(f"Found {len(new_entries)} new entries to process:")
        syndicated_count = 0
        
        for entry in new_entries:
            if process_syndication(entry, services):
                syndicated_count += 1
        
        # Update history file
        if save_history(history_file, processed_ids):
            print(f"Updated history file with {len(new_entries)} new entries.")
        else:
            print("Warning: Failed to save history file")
        if test_mode:
            print(f"[TEST MODE] Would have syndicated {syndicated_count} entries.")
        else:
            print(f"Successfully syndicated {syndicated_count} entries.")
    else:
        print("No new entries found.")


if __name__ == "__main__":
    main() 