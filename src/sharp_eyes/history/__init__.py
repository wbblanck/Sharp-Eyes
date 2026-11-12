"""Serverless trader-history research: who is sharp on NFL, from public history.

``fetch`` downloads settled NFL games and every fill on them from the public
Gamma and Data APIs into a local cache; ``analyze`` scores each wallet on
results, closing-line value and edge left after a copy delay; ``report``
writes the ranked list. Nothing here needs PostgreSQL or an always-on host.
"""
