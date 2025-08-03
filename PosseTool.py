#!/usr/bin/env python3
"""
PosseTool - A utility to syndicate blog posts to social media.

This script downloads and parses an atom feed from a URL provided on the command line.
It maintains a history of processed entries to avoid duplicate syndication.
"""

import sys
import os
import argparse
import yaml

import config
import feed
import text_processing
from services import get_syndication_services


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
                    break  # Service handled this category, no need to check others
                else:
                    print(f"DEBUG: {service.__class__.__name__} cannot handle '{category}'")
        
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
    
    # Load credentials
    credentials = load_credentials(creds_file)
    if not credentials:
        print("Error: No credentials found. Please check your credentials file.")
        sys.exit(1)
    
    # Get available services
    services = get_syndication_services(credentials, test_mode)
    if not services:
        print("Error: No syndication services available. Please check your credentials.")
        sys.exit(1)
    
    print(f"Available services: {[service.__class__.__name__ for service in services]}")
    
    # Download and parse feed
    print(f"Downloading feed from {feed_url}")
    xml_content = feed.download_feed(feed_url)
    if not xml_content:
        print("Error: Failed to download feed")
        sys.exit(1)
    
    entries = feed.parse_feed(xml_content)
    if not entries:
        print("Error: No entries found in feed")
        sys.exit(1)
    
    print(f"Found {len(entries)} entries in feed")
    
    # Load history
    processed_ids = feed.load_history(history_file)
    print(f"Loaded {len(processed_ids)} previously processed entries")
    
    # Process new entries
    new_entries = [entry for entry in entries if entry['id'] not in processed_ids]
    print(f"Found {len(new_entries)} new entries to process")
    
    if not new_entries:
        print("No new entries to process")
        return
    
    # Process each new entry
    processed_count = 0
    for entry in new_entries:
        print(f"\nProcessing: {entry['title']}")
        
        if process_syndication(entry, services):
            processed_ids.add(entry['id'])
            processed_count += 1
            print(f"Successfully processed: {entry['title']}")
        else:
            print(f"Failed to process: {entry['title']}")
    
    # Save updated history
    feed.save_history(history_file, processed_ids)
    print(f"\nProcessed {processed_count} new entries")
    print(f"Updated history file: {history_file}")


if __name__ == '__main__':
    main() 