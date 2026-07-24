"""
Resolution helpers for the Standard Site AT Protocol lexicon
(site.standard.document / site.standard.publication).

Given the URL of a published post, this module discovers the at:// record
that backs it (via a <link rel="site.standard.document"> tag Sequoia writes
into the page) and resolves that record - and the publication record it
points back to - into the associatedRefs shape Bluesky's
app.bsky.embed.external expects for its enhanced Standard Site link card:

    https://github.com/bluesky-social/atproto/discussions/4978
"""

import re

import requests

REQUEST_TIMEOUT = 10

_LINK_TAG_RE = re.compile(r'<link\b[^>]*>', re.IGNORECASE)
_ATTR_RE = re.compile(r"""(\w[\w-]*)\s*=\s*"([^"]*)"|(\w[\w-]*)\s*=\s*'([^']*)'""")
_AT_URI_RE = re.compile(r'^at://([^/]+)/([^/]+)/([^/]+)$')


def find_document_at_uri(page_html):
    """Find the site.standard.document at:// URI in a rendered page's <head>."""
    for tag in _LINK_TAG_RE.findall(page_html):
        attrs = {}
        for match in _ATTR_RE.finditer(tag):
            if match.group(1):
                attrs[match.group(1).lower()] = match.group(2)
            else:
                attrs[match.group(3).lower()] = match.group(4)
        if attrs.get('rel') == 'site.standard.document' and attrs.get('href'):
            return attrs['href']
    return None


def _parse_at_uri(at_uri):
    match = _AT_URI_RE.match(at_uri)
    if not match:
        raise ValueError(f"Not a valid at:// record URI: {at_uri}")
    return match.group(1), match.group(2), match.group(3)


def _resolve_pds(did):
    """Resolve a DID document to find its owning PDS's XRPC base URL."""
    if did.startswith('did:plc:'):
        response = requests.get(f'https://plc.directory/{did}', timeout=REQUEST_TIMEOUT)
    elif did.startswith('did:web:'):
        hostname = did[len('did:web:'):].replace(':', '/')
        response = requests.get(
            f'https://{hostname}/.well-known/did.json', timeout=REQUEST_TIMEOUT
        )
    else:
        raise ValueError(f"Unsupported DID method: {did}")

    response.raise_for_status()
    doc = response.json()

    for service in doc.get('service', []):
        service_id = service.get('id', '')
        if service_id == '#atproto_pds' or service_id.endswith('#atproto_pds'):
            return service['serviceEndpoint'].rstrip('/')

    raise ValueError(f"No AT Protocol PDS service found in DID document for {did}")


def _get_record(pds_url, did, collection, rkey):
    response = requests.get(
        f'{pds_url}/xrpc/com.atproto.repo.getRecord',
        params={'repo': did, 'collection': collection, 'rkey': rkey},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def resolve_associated_refs(post_url):
    """
    Fetch a published post's page and resolve the Standard Site document (and
    its parent publication) record it's backed by, if any.

    Returns a list of {"uri": ..., "cid": ...} refs suitable for
    app.bsky.embed.external's associatedRefs field, or None if the page
    isn't backed by a Standard Site document.
    """
    response = requests.get(post_url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    doc_at_uri = find_document_at_uri(response.text)
    if not doc_at_uri:
        return None

    did, collection, rkey = _parse_at_uri(doc_at_uri)
    pds_url = _resolve_pds(did)

    doc_record = _get_record(pds_url, did, collection, rkey)
    refs = [{'uri': doc_record['uri'], 'cid': doc_record['cid']}]

    publication_at_uri = doc_record.get('value', {}).get('site')
    if publication_at_uri:
        pub_did, pub_collection, pub_rkey = _parse_at_uri(publication_at_uri)
        pub_record = _get_record(pds_url, pub_did, pub_collection, pub_rkey)
        refs.append({'uri': pub_record['uri'], 'cid': pub_record['cid']})

    return refs
