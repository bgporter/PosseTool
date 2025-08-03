"""
Mastodon syndication service for PosseTool.
"""

import unicodedata

from .base import SyndicationService
import config
from text_processing import clean_html_text, extract_first_meaningful_paragraph


class MastodonService(SyndicationService):
    """Mastodon syndication service using Mastodon.py."""
    
    def __init__(self, credentials, test_mode=False):
        super().__init__(credentials, test_mode)
        self.client = None
    
    def can_handle(self, trigger_tag):
        return trigger_tag == 'mastodon'
    
    def authenticate(self):
        """Authenticate with Mastodon using credentials."""
        try:
            from mastodon import Mastodon
            
            # Create app if it doesn't exist
            app_name = "PosseTool"
            app_credentials_file = "mastodon_app_credentials.txt"
            
            if not os.path.exists(app_credentials_file):
                Mastodon.create_app(
                    app_name,
                    api_base_url=self.credentials.get('api_base_url'),
                    to_file=app_credentials_file
                )
            
            # Log in
            self.client = Mastodon(
                client_id=app_credentials_file,
                api_base_url=self.credentials.get('api_base_url')
            )
            self.client.log_in(
                self.credentials.get('email'),
                self.credentials.get('password')
            )
            return True
        except Exception as e:
            print(f"Mastodon authentication failed: {e}")
            return False
    
    def _prepare_post_text(self, entry):
        """Prepare the post text for Mastodon."""
        url = entry.get('url', '')
        
        # Calculate available space for text (reserve space for URL first)
        if url:
            available_space = config.MASTODON_CHAR_LIMIT - len(url) - 2  # 2 for "\n\n" and Mastodon has 500 char limit
        else:
            available_space = config.MASTODON_CHAR_LIMIT
        
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


# Import os for file operations
import os 