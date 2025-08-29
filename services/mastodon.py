"""
Mastodon syndication service for PosseTool.
"""

import os
import unicodedata

from .base import SyndicationService
import config
from text_processing import clean_html_text, extract_first_meaningful_paragraph, extract_hashtags_from_categories, format_hashtags_for_post


class MastodonService(SyndicationService):
    """Mastodon syndication service using Mastodon.py."""
    
    def __init__(self, credentials, test_mode=False):
        super().__init__(credentials, test_mode)
        self.client = None
    
    def can_handle(self, trigger_tag):
        return trigger_tag == 'mastodon'
    
    def get_trigger_tags(self):
        """Get the trigger tags that this service responds to."""
        return {'mastodon'}
    
    def authenticate(self):
        """Authenticate with Mastodon using access token."""
        try:
            from mastodon import Mastodon
            
            # Debug: print available credentials (without showing sensitive data)
            print(f"DEBUG: Mastodon credentials keys: {list(self.credentials.keys())}")
            print(f"DEBUG: Mastodon api_base_url: {self.credentials.get('api_base_url')}")
            print(f"DEBUG: Mastodon access_token present: {'access_token' in self.credentials}")
            
            # Authenticate using access token directly
            self.client = Mastodon(
                api_base_url=self.credentials.get('api_base_url'),
                access_token=self.credentials.get('access_token')
            )
            return True
        except Exception as e:
            print(f"Mastodon authentication failed: {e}")
            return False
    
    def _prepare_post_text(self, entry):
        """Prepare the post text for Mastodon."""
        url = entry.get('url', '')
        categories = entry.get('categories', [])
        
        # Extract hashtags from categories, filtering out reserved trigger tags
        hashtags = extract_hashtags_from_categories(categories)
        
        # Calculate available space for text (reserve space for URL and hashtags)
        url_length = len(url) if url else 0
        hashtag_length = 0
        if hashtags:
            # Estimate hashtag length (we'll calculate exact length later)
            hashtag_length = sum(len(f"#{tag} ") for tag in hashtags) + 2  # +2 for newlines
        
        available_space = config.MASTODON_CHAR_LIMIT - url_length - hashtag_length - 2  # 2 for "\n\n"
        
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
        
        # Format hashtags for the remaining space
        hashtag_string = format_hashtags_for_post(
            hashtags, 
            config.MASTODON_CHAR_LIMIT, 
            len(post_text), 
            url_length
        )
        
        # Build the final post text
        if hashtag_string and url:
            post_text += f"\n{hashtag_string}\n\n{url}"
        elif hashtag_string:
            post_text += f"\n{hashtag_string}"
        elif url:
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