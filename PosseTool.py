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
from urllib.parse import urlparse
from pathlib import Path


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
        import unicodedata
        content = unicodedata.normalize('NFC', content)
        
        return content
    except requests.RequestException as e:
        print(f"Error downloading feed from {feed_url}: {e}")
        sys.exit(1)


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
        import unicodedata
        text = unicodedata.normalize('NFC', text)
        return text
    return ''


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
        
        # Debug: Print the root tag to see what we're dealing with
        print(f"DEBUG: Root tag: {root.tag}")
        
        # Handle both atom and RSS feeds
        if 'Atom' in root.tag or 'atom' in root.tag or 'http://www.w3.org/2005/Atom' in root.tag:
            print("DEBUG: Detected Atom feed")
            # Atom feed
            entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            print(f"DEBUG: Found {len(entries)} entries with namespace")
            
            # Also try without namespace
            entries_no_ns = root.findall('.//entry')
            print(f"DEBUG: Found {len(entries_no_ns)} entries without namespace")
            
            # Use the approach that found entries
            if len(entries) > 0:
                entries_to_process = entries
                ns_prefix = '{http://www.w3.org/2005/Atom}'
            elif len(entries_no_ns) > 0:
                entries_to_process = entries_no_ns
                ns_prefix = ''
            else:
                print("DEBUG: No entries found with either approach")
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
                    # Extract URL from link
                    url = ''
                    if link is not None:
                        href = link.get('href')
                        if href:
                            url = href
                    
                    # Extract category tags
                    category_tags = []
                    for category in categories:
                        term = category.get('term')
                        if term:
                            category_tags.append(term)
                    
                    entries_data.append({
                        'id': safe_text(entry_id),
                        'title': safe_text(title) if title is not None else 'Untitled',
                        'content': safe_text(content),
                        'summary': safe_text(summary),
                        'url': url,
                        'categories': category_tags
                    })
        else:
            print("DEBUG: Detected RSS feed")
            # RSS feed
            entries = root.findall('.//item')
            print(f"DEBUG: Found {len(entries)} RSS items")
            entries_data = []
            
            for entry in entries:
                entry_id = entry.find('guid')
                title = entry.find('title')
                content = entry.find('description')
                link = entry.find('link')
                categories = entry.findall('category')
                
                if entry_id is not None:
                    # Extract URL from link
                    url = ''
                    if link is not None:
                        url = safe_text(link)
                    
                    # Extract category tags
                    category_tags = []
                    for category in categories:
                        term = safe_text(category)
                        if term:
                            category_tags.append(term)
                
                    entries_data.append({
                        'id': safe_text(entry_id),
                        'title': safe_text(title) if title is not None else 'Untitled',
                        'content': safe_text(content),
                        'summary': safe_text(content),  # Use description as summary for RSS
                        'url': url,
                        'categories': category_tags
                    })
        
        print(f"DEBUG: Returning {len(entries_data)} processed entries")
        return entries_data
        
    except ET.ParseError as e:
        print(f"Error parsing XML feed: {e}")
        sys.exit(1)


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
            sys.exit(1)
    
    return processed_ids


def save_history(history_file, processed_ids):
    """
    Save the updated history of processed entry IDs to the history file.
    
    Args:
        history_file (str): Path to the history file
        processed_ids (set): Set of processed entry IDs
    """
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            for entry_id in sorted(processed_ids):
                f.write(f"{entry_id}\n")
    except IOError as e:
        print(f"Error writing history file {history_file}: {e}")
        sys.exit(1)


def sanitize_filename(title):
    """
    Sanitize the title to create a valid filename.
    
    Args:
        title (str): The entry title
        
    Returns:
        str: Sanitized filename
    """
    # Debug: Print the original title and its characters
    print(f"DEBUG: Original title: '{title}'")
    print(f"DEBUG: Title characters: {[c for c in title]}")
    
    # Normalize Unicode characters (NFD -> NFC)
    import unicodedata
    normalized = unicodedata.normalize('NFC', title)
    
    # Replace problematic characters with safe alternatives
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '–': '-',  # en dash
        '—': '-',  # em dash
        '…': '...',  # ellipsis
        '™': '(TM)',  # trademark
        '®': '(R)',  # registered trademark
        '©': '(C)',  # copyright
        '°': 'deg',  # degree
        '±': 'plusminus',  # plus-minus
        '×': 'x',  # multiplication
        '÷': 'div',  # division
        '≤': 'le',  # less than or equal
        '≥': 'ge',  # greater than or equal
        '≠': 'ne',  # not equal
        '≈': 'approx',  # approximately
        '∞': 'infinity',  # infinity
        '√': 'sqrt',  # square root
        '²': '2',  # superscript 2
        '³': '3',  # superscript 3
        '¼': '1/4',  # one quarter
        '½': '1/2',  # one half
        '¾': '3/4',  # three quarters
        'α': 'alpha',  # Greek alpha
        'β': 'beta',  # Greek beta
        'γ': 'gamma',  # Greek gamma
        'δ': 'delta',  # Greek delta
        'ε': 'epsilon',  # Greek epsilon
        'θ': 'theta',  # Greek theta
        'λ': 'lambda',  # Greek lambda
        'μ': 'mu',  # Greek mu
        'π': 'pi',  # Greek pi
        'σ': 'sigma',  # Greek sigma
        'τ': 'tau',  # Greek tau
        'φ': 'phi',  # Greek phi
        'ω': 'omega',  # Greek omega
    }
    
    # Apply replacements
    for unicode_char, ascii_replacement in replacements.items():
        normalized = normalized.replace(unicode_char, ascii_replacement)
    
    # Remove or replace other non-ASCII characters
    # Keep only ASCII letters, digits, hyphens, underscores, and periods
    sanitized = re.sub(r'[^a-zA-Z0-9\-_.]', '_', normalized)
    
    # Remove multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Ensure the filename is not empty
    if not sanitized:
        sanitized = 'untitled'
    
    print(f"DEBUG: Sanitized filename: '{sanitized}'")
    return sanitized


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
    import unicodedata
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
    
    def post(self, entry):
        """Post a skeet to Bluesky."""
        if not self.client and not self.test_mode:
            if not self.authenticate():
                return False
        
        try:
            # Clean the summary text with proper encoding
            summary = clean_html_text(entry.get('summary', ''))
            url = entry.get('url', '')
            
            # Ensure the text is properly encoded for Bluesky
            import unicodedata
            post_text = unicodedata.normalize('NFC', summary)
            
            # Add URL if available and there's room
            facets = []
            if url:
                # Bluesky has a 300 character limit
                if len(post_text) + len(url) + 2 <= 300:
                    post_text += f"\n\n{url}"
                    # Create a facet for the link
                    link_start = len(post_text) - len(url)
                    link_end = len(post_text)
                    facets.append({
                        "index": {
                            "byteStart": link_start,
                            "byteEnd": link_end
                        },
                        "features": [{
                            "$type": "app.bsky.richtext.facet#link",
                            "uri": url
                        }]
                    })
                else:
                    # Truncate summary to make room for URL
                    available_space = 300 - len(url) - 3  # 3 for "\n\n"
                    if available_space > 10:  # Ensure we have some meaningful text
                        post_text = post_text[:available_space] + "...\n\n" + url
                        # Create a facet for the link
                        link_start = len(post_text) - len(url)
                        link_end = len(post_text)
                        facets.append({
                            "index": {
                                "byteStart": link_start,
                                "byteEnd": link_end
                            },
                            "features": [{
                                "$type": "app.bsky.richtext.facet#link",
                                "uri": url
                            }]
                        })
            
            if self.test_mode:
                self._log_test_post("Bluesky", entry['title'], post_text)
                return True
            else:
                # Post the skeet with embed for link unfurling
                if url:
                    # Create an external embed for the URL using proper atproto models
                    from atproto import models
                    
                    # Try to extract image from HTML content
                    image_url = None
                    content = entry.get('content', '')
                    if content:
                        # Unescape HTML entities
                        unescaped_content = html.unescape(content)
                        
                        # Find the first <img> tag
                        import re
                        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', unescaped_content)
                        if img_match:
                            image_url = img_match.group(1)
                            print(f"DEBUG: Found image URL in content: {image_url}")
                    
                    # Download and upload image if available
                    image_blob_ref = None
                    temp_image_path = None
                    if image_url:
                        try:
                            import requests
                            import tempfile
                            import os
                            
                            # Download the image to a temporary file
                            response = requests.get(image_url, timeout=10)
                            response.raise_for_status()
                            
                            # Determine the file extension from URL or content type
                            import urllib.parse
                            from pathlib import Path
                            
                            # Try to get extension from URL
                            parsed_url = urllib.parse.urlparse(image_url)
                            url_path = Path(parsed_url.path)
                            extension = url_path.suffix
                            
                            # If no extension in URL, try to get from content type
                            if not extension:
                                content_type = response.headers.get('content-type', '')
                                if 'png' in content_type:
                                    extension = '.png'
                                elif 'gif' in content_type:
                                    extension = '.gif'
                                elif 'webp' in content_type:
                                    extension = '.webp'
                                else:
                                    extension = '.jpg'  # Default fallback
                            
                            # Create a temporary file with the correct extension
                            temp_fd, temp_image_path = tempfile.mkstemp(suffix=extension)
                            os.close(temp_fd)
                            
                            # Process the image to resize and compress
                            from PIL import Image
                            import io
                            
                            # Open the image
                            img = Image.open(io.BytesIO(response.content))
                            
                            # Convert to RGB if necessary (for JPEG compression)
                            if img.mode in ('RGBA', 'LA', 'P'):
                                # Create a white background for transparent images
                                background = Image.new('RGB', img.size, (255, 255, 255))
                                if img.mode == 'P':
                                    img = img.convert('RGBA')
                                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                                img = background
                            elif img.mode != 'RGB':
                                img = img.convert('RGB')
                            
                            # Calculate new size maintaining aspect ratio
                            target_width, target_height = 1200, 630
                            img_width, img_height = img.size
                            
                            # Calculate scaling factor to fit within 1200x630
                            scale_x = target_width / img_width
                            scale_y = target_height / img_height
                            scale = min(scale_x, scale_y)
                            
                            # Calculate new dimensions
                            new_width = int(img_width * scale)
                            new_height = int(img_height * scale)
                            
                            # Resize the image
                            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            
                            # Create a new image with target size and white background
                            final_img = Image.new('RGB', (target_width, target_height), (255, 255, 255))
                            
                            # Center the resized image
                            x_offset = (target_width - new_width) // 2
                            y_offset = (target_height - new_height) // 2
                            final_img.paste(img, (x_offset, y_offset))
                            
                            # Save with compression to meet size requirements
                            output_buffer = io.BytesIO()
                            quality = 95
                            
                            # Try different quality levels to get under 900KB
                            while quality > 10:
                                output_buffer.seek(0)
                                output_buffer.truncate()
                                final_img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
                                
                                if output_buffer.tell() <= 900 * 1024:  # 900KB in bytes
                                    break
                                quality -= 5
                            
                            # Save the processed image
                            with open(temp_image_path, 'wb') as f:
                                f.write(output_buffer.getvalue())
                            
                            # Upload to Bluesky
                            with open(temp_image_path, 'rb') as f:
                                img_data = f.read()
                            upload_response = self.client.upload_blob(img_data)
                            image_blob_ref = upload_response.blob
                            
                        except Exception as e:
                            print(f"Warning: Failed to upload image {image_url}: {e}")
                            image_blob_ref = None
                        finally:
                            # Clean up temporary file
                            if temp_image_path and os.path.exists(temp_image_path):
                                try:
                                    os.unlink(temp_image_path)
                                except Exception as e:
                                    print(f"Warning: Failed to delete temporary image {temp_image_path}: {e}")
                    
                    # Define the external link details
                    external_link = models.AppBskyEmbedExternal.External(
                        uri=url,
                        title=entry.get('title', ''),
                        description=summary[:200] if summary else '',  # Limit description
                        thumb=image_blob_ref  # Add the uploaded image blob reference
                    )
                    
                    # Create the embed object
                    embed = models.AppBskyEmbedExternal.Main(external=external_link)
                    
                    self.client.send_post(text=post_text, facets=facets, embed=embed)
                else:
                    # Post without embed if no URL
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
    
    return services


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
    
    for service in services:
        for category in categories:
            if service.can_handle(category):
                if service.post(entry):
                    processed = True
                break  # Only process once per service
    
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
    
    if test_mode:
        print("[TEST MODE] Running in test mode - no actual posts will be made")
    
    # Download and parse the feed
    xml_content = download_feed(feed_url)
    
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
        save_history(history_file, processed_ids)
        print(f"Updated history file with {len(new_entries)} new entries.")
        if test_mode:
            print(f"[TEST MODE] Would have syndicated {syndicated_count} entries.")
        else:
            print(f"Successfully syndicated {syndicated_count} entries.")
    else:
        print("No new entries found.")


if __name__ == "__main__":
    main() 