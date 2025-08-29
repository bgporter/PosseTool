"""
Services package for PosseTool.
"""

from .base import SyndicationService
from .bluesky import BlueskyService
from .mastodon import MastodonService


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


def get_active_trigger_tags(credentials, test_mode=False):
    """
    Get all active trigger tags from available services.
    
    Args:
        credentials (dict): Service credentials
        test_mode (bool): Whether to run in test mode
        
    Returns:
        set: Set of all active trigger tags
    """
    services = get_syndication_services(credentials, test_mode)
    trigger_tags = set()
    
    for service in services:
        trigger_tags.update(service.get_trigger_tags())
    
    return trigger_tags 