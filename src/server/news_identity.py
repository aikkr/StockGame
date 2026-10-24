"""Identify headlines across feeds using hashlib; no I/O or persistent side effects."""

import hashlib


def get_publication_id(article):
    """Hash normalized headline text across stocks and dates using hashlib; no side effects."""
    headline = ' '.join(article['headline'].split()).casefold()
    return hashlib.sha256(headline.encode()).hexdigest()
