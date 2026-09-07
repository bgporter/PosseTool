# Detect an authored Summary by its absence of Pelican's truncation suffix

Post bodies now prefer the feed entry's `<summary>` over lede-extracted `content`, because an author-written `Summary:` front-matter field produces a far better social teaser than sniffing the first paragraph out of the article body. The problem: the same `<summary>` element also holds Pelican's auto-generated fallback (a raw 50-word truncation of `content`) for posts that don't set `Summary:`, and that auto-generated text is exactly the kind of awkward, mid-sentence excerpt we're trying to avoid — so we can't trust `summary` unconditionally.

We distinguish the two by checking whether `summary` ends in Pelican's `SUMMARY_END_SUFFIX` (`" …"`, the default, unconfigured in this site's `pelicanconf.py`): if it does, treat it as auto-generated and fall back to lede extraction from `content`; otherwise treat it as authored and use it verbatim. We also skip this trust when `summary == content` (the RSS case, where no separate summary was ever produced), always falling back to lede extraction there.

**Considered and rejected**: adding a brand-new dedicated feed field (e.g. `posse:blurb`) for the social teaser, so the intent would be unambiguous. Rejected because roughly half the existing posts already have a hand-written `Summary:` that renders correctly today, and there's no reason to make the author maintain two nearly-identical fields per post.

**Risk**: this relies on an undocumented default of the blog's static site generator. If `SUMMARY_END_SUFFIX` in `pelicanconf.py` is ever changed, authored summaries could be misdetected as auto-generated (or vice versa) with no error — just a quietly worse post body.
