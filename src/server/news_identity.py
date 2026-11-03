def get_publication_id(article):
    headline = ' '.join(article['headline'].split()).casefold()
    return headline
