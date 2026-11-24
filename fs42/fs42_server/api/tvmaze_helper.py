"""TVmaze lookups for episode rename previews."""

import re
from functools import lru_cache

import requests

BASE_URL = "https://api.tvmaze.com"


def title_key(title):
    return re.sub(r"[\W_]+", "", title.casefold())


def _get(path, **params):
    response = requests.get(f"{BASE_URL}{path}", params=params, timeout=5)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


@lru_cache(maxsize=128)
def search_shows(query):
    match = re.fullmatch(r"(.+?)\s*\((\d{4})\)", query)
    title, year = match.groups() if match else (query, None)
    shows = (item["show"] for item in _get("/search/shows", q=title) or [])
    return tuple(
        show for show in shows
        if title_key(show["name"]) == title_key(title)
        and (not year or (show.get("premiered") or "")[:4] == year)
    )


def get_episode(show_id, season, number):
    return _get(f"/shows/{show_id}/episodebynumber", season=season, number=number)


@lru_cache(maxsize=64)
def list_episodes(show_id):
    return _get(f"/shows/{show_id}/episodes") or []
