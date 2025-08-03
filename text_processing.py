"""
Text processing functionality for PosseTool.
"""

import re
import html
import unicodedata


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
                        # Reserve space for "..."
                        available_space = max_length - 3
                        words = cleaned.split()
                        for word in words:
                            test_text = current_text + word + " "
                            if len(test_text) <= available_space:
                                current_text = test_text
                            else:
                                break
                        current_text = current_text.strip()
                        if current_text:
                            current_text += "..."
                    break
            
            return current_text.strip()
        
        # If no sentence boundaries found, truncate at word boundaries
        if len(cleaned) > max_length:
            # Reserve space for "..."
            available_space = max_length - 3
            words = cleaned.split()
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
    
    # If no meaningful paragraph found, return empty string
    return '' 