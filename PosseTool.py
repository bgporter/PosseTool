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
from urllib.parse import urlparse
from pathlib import Path


def download_feed(feed_url):
    """
    Download the atom feed from the provided URL.
    
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
        return response.text
    except requests.RequestException as e:
        print(f"Error downloading feed from {feed_url}: {e}")
        sys.exit(1)


def safe_text(element):
    """
    Safely extract text from an XML element.
    
    Args:
        element: XML element or None
        
    Returns:
        str: Text content or empty string
    """
    if element is not None and element.text is not None:
        return element.text.strip()
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
    Clean HTML text by removing HTML entities and tags.
    
    Args:
        text (str): HTML text to clean
        
    Returns:
        str: Cleaned text
    """
    if not text:
        return ''
    
    # Unescape HTML entities
    cleaned = html.unescape(text)
    
    # Remove HTML tags
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    
    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()


def write_entry_to_text(entry, output_dir='.'):
    """
    Write an entry to a text file named after the entry title.
    
    Args:
        entry (dict): Entry data containing id, title, content, summary, url, and categories
        output_dir (str): Directory to write the text file to
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Sanitize the title for filename
    filename = sanitize_filename(entry['title'])
    text_file = os.path.join(output_dir, f"{filename}.txt")
    
    # Clean the summary text
    summary = clean_html_text(entry.get('summary', ''))
    
    # Get de-duped categories
    categories = list(set(entry.get('categories', [])))
    
    # Create text content
    text_content = f"""Title: {entry['title']}

Summary:
{summary}

URL: {entry.get('url', 'No URL available')}

Categories: {', '.join(categories) if categories else 'No categories'}

Entry ID: {entry['id']}
"""
    
    try:
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_content)
        print(f"Processed entry: {entry['title']} -> {text_file}")
    except IOError as e:
        print(f"Error writing text file {text_file}: {e}")


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
    
    if verbose:
        print(f"Processing feed: {feed_url}")
        print(f"History file: {history_file}")
        print(f"Output directory: {output_dir}")
    
    # Download and parse the feed
    xml_content = download_feed(feed_url)
    
    # Temporarily print the feed content for debugging
    print("=== DOWNLOADED FEED CONTENT ===")
    print(xml_content)
    print("=== END FEED CONTENT ===")
    
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
        for entry in new_entries:
            write_entry_to_text(entry, output_dir)
        
        # Update history file
        save_history(history_file, processed_ids)
        print(f"Updated history file with {len(new_entries)} new entries.")
    else:
        print("No new entries found.")


if __name__ == "__main__":
    main() 