#!/usr/bin/env python3
"""
PosseTool - A utility to syndicate blog posts to social media.

This script downloads and parses an atom feed from a URL provided on the command line.
It maintains a history of processed entries to avoid duplicate syndication.

MIT License

Copyright (c) 2025 Brett g Porter

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import sys
import os
import argparse
import yaml
from datetime import datetime

import config
import feed
import text_processing
from services import get_syndication_services


def log(message):
    """
    Log a message with a timestamp.
    
    Args:
        message (str): Message to log
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def debug_log(message, verbose=False):
    """
    Log a debug message with a timestamp only if verbose mode is enabled.
    
    Args:
        message (str): Debug message to log
        verbose (bool): Whether verbose mode is enabled
    """
    if verbose:
        log(message)


def load_credentials(creds_file, verbose=False):
    """
    Load credentials from YAML file.
    
    Args:
        creds_file (str): Path to YAML credentials file
        verbose (bool): Whether to enable verbose logging
        
    Returns:
        dict: Credentials for each service
    """
    if not creds_file or not os.path.exists(creds_file):
        return {}
    
    try:
        with open(creds_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        log(f"Error loading credentials file {creds_file}: {e}")
        return {}


def process_syndication(entry, services, verbose=False):
    """
    Process syndication for an entry based on its categories.
    
    Args:
        entry (dict): Entry data
        services (list): List of SyndicationService instances
        verbose (bool): Whether to enable verbose logging
        
    Returns:
        bool: True if at least one service processed the entry
    """
    categories = entry.get('categories', [])
    processed = False
    title = entry.get('title', 'Unknown')
    
    debug_log(f"Processing entry '{entry.get('title', 'Unknown')}' with categories: {categories}", verbose)
    debug_log(f"Available services: {[service.__class__.__name__ for service in services]}", verbose)
    
    # Check if "posse" category is present - if so, all services should publish
    should_publish_all = 'posse' in categories
    
    for service in services:
        service_processed = False
        
        if should_publish_all:
            # If "posse" is present, all services should publish
            debug_log(f"'posse' category found - {service.__class__.__name__} will handle all entries", verbose)
            if service.post(entry):
                processed = True
                service_processed = True
                debug_log(f"{service.__class__.__name__} successfully posted (posse)", verbose)
            else:
                log(f"{service.__class__.__name__} failed to post {title}")
        else:
            # Normal category-based processing
            for category in categories:
                debug_log(f"Checking if {service.__class__.__name__} can handle '{category}'", verbose)
                if service.can_handle(category):
                    debug_log(f"{service.__class__.__name__} will handle '{category}'", verbose)
                    if service.post(entry):
                        processed = True
                        service_processed = True
                        debug_log(f"{service.__class__.__name__} successfully posted", verbose)
                    else:
                        log(f"{service.__class__.__name__} failed to post {title}")
                    break  # Service handled this category, no need to check others
                else:
                    debug_log(f"{service.__class__.__name__} cannot handle '{category}'", verbose)
        
        if service_processed:
            log(f"SUCCESS: {title} -> {service.__class__.__name__}")
    
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
    
    debug_log(f"Processing feed: {feed_url}", verbose)
    debug_log(f"History file: {history_file}", verbose)
    debug_log(f"Output directory: {output_dir}", verbose)
    if creds_file:
        debug_log(f"Credentials file: {creds_file}", verbose)
    
    # Load credentials
    credentials = load_credentials(creds_file, verbose)
    if not credentials:
        log("Error: No credentials found. Please check your credentials file.")
        sys.exit(1)
    
    # Get available services
    services = get_syndication_services(credentials, test_mode)
    if not services:
        log("Error: No syndication services available. Please check your credentials.")
        sys.exit(1)
    
    debug_log(f"Available services: {[service.__class__.__name__ for service in services]}", verbose)
    
    # Download and parse feed
    debug_log(f"Downloading feed from {feed_url}", verbose)
    xml_content = feed.download_feed(feed_url)
    if not xml_content:
        log("Error: Failed to download feed")
        sys.exit(1)
    
    entries = feed.parse_feed(xml_content)
    if not entries:
        log("Error: No entries found in feed")
        sys.exit(1)
    
    debug_log(f"Found {len(entries)} entries in feed", verbose)
    
    # Load history
    processed_ids = feed.load_history(history_file)
    debug_log(f"Loaded {len(processed_ids)} previously processed entries", verbose)
    
    # Process new entries
    new_entries = [entry for entry in entries if entry['id'] not in processed_ids]
    debug_log(f"Found {len(new_entries)} new entries to process", verbose)
    
    if not new_entries:
        debug_log("No new entries to process", verbose)
        return
    
    # Process each new entry
    processed_count = 0
    for entry in new_entries:
        debug_log(f"Processing: {entry['title']}", verbose)
        
        if process_syndication(entry, services, verbose):
            processed_ids.add(entry['id'])
            processed_count += 1
            debug_log(f"Successfully processed: {entry['title']}", verbose)
        else:
            log(f"Failed to process: {entry['title']}")
    
    # Save updated history
    feed.save_history(history_file, processed_ids)
    log(f"Processed {processed_count} new entries")
    debug_log(f"Updated history file: {history_file}", verbose)


if __name__ == '__main__':
    main() 