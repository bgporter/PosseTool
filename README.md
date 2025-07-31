# PosseTool 

A utility to syndicate blog posts to social media. 

Written in Python 3.x 

## Overview

This script will download and parse an atom feed from a URL provided on the command line. 

We will maintain a history of each entry from the feed that we have already handled so that each entry is only syndicated once, the first time we encounter it. To do this, we can just update a text file where we write the text of the entry's `<id>` on a line by itself. The path and name of this file will also be provided on the command line. If the history file does not exist (because this is the first time we've run) we should add the id of all entries found in the feed and exit (only syndicating items added after this initial run).

Otherwise, we will iterate through the feed and compare the ID of each entry against the history file. If we have not seen that entry yet, we should pass it to the syndication processor code. For now, all that needs to do is to write out a copy of that entry to an XML file named after the title of the entry with all whitespace removed and an .xml extension.

## Syndications

Once we have identified new entries in the feed and have a list of 1 or more tuples like 
(summary, URL, [list, of, category/tags])

We can proceed to syndicating content. We'll look at the categories for 'trigger tags' that will tell the syndication mechanism what to do. The initial trigger tags are

- 'bsky': create a new skeet on Bluesky
- 'mastodon': create a toot on Mastodon

When a trigger tag is present in an entry's list of categories, that entry should be sent to that service. 

We will use a YAML file to maintain account/credential information for any services that we will add support for that will be formatted like:

service_name:
    first_attr: attr_val
    second_attr: attr_val
another_service:
    service_specific_attr: attr_val 

(etc)

Each service can have its own set of things used to connect and authenticate with its server. 

We will pass this file into the script with a new -c / --creds command line argument. 



### Bluesky 

We'll use the atproto library for this. 

When one or more entries should be sent to bluesky, we'll create a client object and authenticate, then for each of them post a skeet that contains as much of the summary as will fit and also the URL (as a link) to the post. 


### Mastodon 

For the moment, we will skip implementing mastodon support, but the design should accommodate it. 

