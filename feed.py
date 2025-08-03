"""
Feed downloading and parsing functionality for PosseTool.
"""

import requests
import xml.etree.ElementTree as ET
import unicodedata


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
        # For Atom feeds, look for href attribute
        href = link_element.get('href')
        if href:
            return href
        
        # Fallback to text content
        return safe_text(link_element)


def extract_categories(category_elements, is_rss=False):
    """
    Extract category terms from category elements.
    
    Args:
        category_elements: List of category XML elements
        is_rss (bool): Whether this is RSS format
        
    Returns:
        list: List of category terms
    """
    categories = []
    
    for category in category_elements:
        if is_rss:
            # RSS uses text content
            term = safe_text(category)
        else:
            # Atom uses term attribute
            term = category.get('term')
            if not term:
                term = safe_text(category)
        
        if term:
            categories.append(term)
    
    return categories


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
    Load the history of processed entry IDs.
    
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
        except Exception as e:
            print(f"Warning: Could not load history file {history_file}: {e}")
    
    return processed_ids


def save_history(history_file, processed_ids):
    """
    Save the history of processed entry IDs.
    
    Args:
        history_file (str): Path to the history file
        processed_ids (set): Set of processed entry IDs
    """
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            for entry_id in sorted(processed_ids):
                f.write(f"{entry_id}\n")
    except Exception as e:
        print(f"Warning: Could not save history file {history_file}: {e}")


# Import os for file operations
import os 