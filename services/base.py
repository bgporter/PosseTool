"""
Base syndication service class.
"""


class SyndicationService:
    """Base class for social media syndication services."""
    
    def __init__(self, credentials, test_mode=False):
        self.credentials = credentials
        self.test_mode = test_mode
    
    def can_handle(self, trigger_tag):
        """Check if this service can handle the given trigger tag."""
        return False
    
    def get_trigger_tags(self):
        """Get the trigger tags that this service responds to."""
        return set()
    
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