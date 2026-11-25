import json
from pathlib import Path


SUBTITLE_STYLE_PATH = Path("runtime/subtitle_style.json")
BACKGROUND_COLORS = {
    "none": "0/0/0/0",
    "translucent": "0/0/0/0.65",
    "solid": "0/0/0/1",
}


def read_subtitle_style():
    try:
        saved = json.loads(SUBTITLE_STYLE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(saved, dict):
        return {}
    settings = {}
    position = saved.get("position")
    if type(position) is int and 0 <= position <= 100:
        settings["position"] = position
    background = saved.get("background")
    if isinstance(background, str) and background in BACKGROUND_COLORS:
        settings["background"] = background
    return settings
