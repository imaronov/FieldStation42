"""TVmaze show and episode lookups."""

import re
from functools import lru_cache

import requests

from . import tvdb_helper

BASE_URL = "https://api.tvmaze.com"


class EpisodeOrderError(ValueError):
    """The selected episode order cannot be used for this show."""


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


@lru_cache(maxsize=512)
def _aired_episode(show_id, season, number):
    return _get(f"/shows/{show_id}/episodebynumber", season=season, number=number)


@lru_cache(maxsize=64)
def list_episodes(show_id):
    return _get(f"/shows/{show_id}/episodes", specials=1) or []


def _order(show, config):
    orders = config.get("episode_orders", {})
    if not isinstance(orders, dict):
        raise EpisodeOrderError("episode_orders must be an object in main_config.json.")
    order = orders.get(str(show["id"]))
    if order is None:
        return None
    if isinstance(order, dict) and len(order) == 1:
        list_id = order.get("tvmaze_list_id")
        if type(list_id) is int and list_id > 0:
            return "tvmaze", list_id
        if order.get("tvdb_order") in tvdb_helper.ORDERS:
            return "tvdb", order["tvdb_order"]
    raise EpisodeOrderError(f"Invalid episode order for {show['name']} in main_config.json.")


@lru_cache(maxsize=64)
def _alternate_episodes(show_id, list_id):
    lists = _get(f"/shows/{show_id}/alternatelists") or []
    if not any(item.get("id") == list_id for item in lists):
        raise EpisodeOrderError(f"TVmaze alternate list {list_id} does not belong to show {show_id}.")
    return _get(f"/alternatelists/{list_id}/alternateepisodes", embed="episodes") or []


def season_episodes(show, season, config):
    order = _order(show, config)
    if order is None:
        return [item for item in list_episodes(show["id"]) if item.get("season") == season]

    provider, selection = order
    if provider == "tvmaze":
        episodes = []
        for item in _alternate_episodes(show["id"], selection):
            if item.get("season") != season:
                continue
            originals = (item.get("_embedded") or {}).get("episodes") or []
            episode = originals[0].copy() if len(originals) == 1 else {}
            episode.update(number=item.get("number"), name=item.get("name") or episode.get("name"))
            episodes.append(episode)
        return episodes

    key = config.get("tvdb_api_key")
    series_id = (show.get("externals") or {}).get("thetvdb")
    if not key or not series_id:
        raise EpisodeOrderError(f"The selected TheTVDB order for {show['name']} requires a TVDB API key and a linked TVDB series.")
    return tvdb_helper.season_episodes(series_id, selection, season, key, config.get("tvdb_pin"))


def get_episode(show, season, number, config, *, include_metadata=False):
    order = _order(show, config)
    if order is None:
        return _aired_episode(show["id"], season, number)

    matches = [item for item in season_episodes(show, season, config) if item.get("number") == number]
    if len(matches) != 1:
        return None
    episode = matches[0]
    if order[0] != "tvdb" or not include_metadata:
        return episode

    # Cross-reference the provider's episode by title and air date rather than by number.
    title = title_key(episode.get("name") or "")
    airdate = episode.get("aired")
    aired_episodes = list_episodes(show["id"])
    candidates = [item for item in aired_episodes
                  if title and title_key(item.get("name") or "") == title
                  and (not airdate or not item.get("airdate") or item["airdate"] == airdate)]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates and airdate:
        same_day = [item for item in aired_episodes if item.get("airdate") == airdate]
        if len(same_day) == 1:
            return same_day[0]
    return {"name": episode.get("name"), "summary": episode.get("overview")}
