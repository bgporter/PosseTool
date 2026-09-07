# PosseTool

A utility that syndicates blog posts from an Atom/RSS feed to social media platforms (Bluesky, Mastodon), composing platform-appropriate post text and link previews from each feed entry.

## Language

**Summary**:
The feed entry's `<summary>` element. May be either an author-written teaser (from the blog's `Summary:` front matter field) or an auto-truncated excerpt the blog engine generates from the article body when no `Summary:` was set. Distinguishing the two matters: an auto-truncated summary ends in the blog engine's truncation suffix ("…") and reads as an arbitrary word-count cutoff, not a real teaser.
_Avoid_: excerpt, blurb (don't distinguish authored from auto-generated)

**Lede extraction**:
The fallback heuristic that pulls the first substantive paragraph out of an entry's full `content` HTML (skipping headings, image captions, admonitions) when no usable authored Summary exists. Known to sometimes surface a paragraph that reads fine in the article but makes no sense as a standalone teaser.
_Avoid_: first paragraph, summary extraction

**Trigger tag**:
A reserved feed category term (`bsky`, `mastodon`, `posse`) that controls which service(s) syndicate a given entry. Not shown to readers.
_Avoid_: category, tag (too generic — always say trigger tag when routing is meant)

**Content tag**:
A feed category term that is *not* a trigger tag. Rendered as a hashtag in a Mastodon post body, and (going forward) as plain tag text in a Bluesky embed card's description.
_Avoid_: hashtag (that's one specific rendering of a content tag, not the concept itself), category

**Embed card**:
The rich link-preview object PosseTool itself constructs and attaches to a Bluesky post (title, description, thumbnail). Bluesky requires the posting client to build this; PosseTool has full control over its contents.
_Avoid_: link preview, card (ambiguous with Mastodon's card, which PosseTool does not control)

**Standard Site embed**:
An embed card enhanced with `associatedRefs`, qualifying it for Bluesky's richer Standard Site link card treatment. Resolved by looking up the `site.standard.document`/`site.standard.publication` AT Protocol records backing the linked page. Best-effort: falls back to a plain embed card if resolution fails.
_Avoid_: associatedRefs (that's the field name, not the concept)

**Mastodon link card**:
The link-preview widget Mastodon's own server generates by crawling the linked page's HTML `<meta>` tags. PosseTool sends Mastodon plain post text only and has no control over what this card shows.
_Avoid_: embed card (reserve that term for the Bluesky object PosseTool builds itself)
