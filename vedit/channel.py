"""Channel library: config dir, default channel, channel.yaml, and runtime style/accent resolution.

Style used (first set wins): cue `style:` > cues.yaml `style:` > project.yaml `style:` > channel default >
global default (config.yaml) > `base`. `style_choice()` returns it with where it came from.
"""

import os
from pathlib import Path

import yaml


def config_dir() -> Path:
    env = os.environ.get("VEDIT_CONFIG_DIR")
    return Path(env).expanduser() if env else Path.home() / ".config" / "vedit"


def _read(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def load_config() -> dict:
    """`config.yaml`: `channel:` (default handle) and `style:` (default style). {} when absent."""
    return _read(config_dir() / "config.yaml")


def channel_file(handle: str) -> Path:
    return config_dir() / "channels" / handle / "channel.yaml"


def load_channel(handle: str | None) -> dict | None:
    """channel.yaml as a dict (style, lang, dialect, accent, hint, logos); None when there is no file."""
    if not handle or not channel_file(handle).is_file():
        return None
    return _read(channel_file(handle))


def default_channel() -> str | None:
    v = load_config().get("channel")
    return str(v) if v else None


def _resolve(project, key: str) -> tuple[str | None, str | None]:
    """(value, origin): project, then its channel, then global config (style only)."""
    if getattr(project, key, None):
        return getattr(project, key), "project.yaml"
    handle = getattr(project, "channel", None)
    ch = load_channel(handle)
    if ch and ch.get(key):
        return str(ch[key]), f"channel {handle}"
    if key == "style" and load_config().get("style"):
        return str(load_config()["style"]), "global config"
    return None, None


def effective_style(project) -> tuple[str | None, str | None]:
    return _resolve(project, "style")


def effective_accent(project) -> tuple[str | None, str | None]:
    return _resolve(project, "accent")


CHANNEL_KEYS = ("style", "lang", "dialect", "accent", "hint", "logos")


def save_channel(handle: str, data: dict) -> Path:
    """Write channel.yaml (creates the folder); keys in CHANNEL_KEYS order, empty values dropped."""
    f = channel_file(handle)
    f.parent.mkdir(parents=True, exist_ok=True)
    out = {k: data[k] for k in CHANNEL_KEYS if data.get(k)}
    out.update({k: v for k, v in data.items() if k not in CHANNEL_KEYS and v})
    f.write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return f


def channels() -> list[str]:
    """Handles that have a folder under `<config_dir>/channels/`."""
    d = config_dir() / "channels"
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


def project_channel(root) -> str | None:
    """The `channel:` of a project folder's project.yaml (None when absent or unreadable)."""
    v = _read(Path(root) / "project.yaml").get("channel")
    return str(v) if v else None


def style_choice(project, cues_style: str | None = None, cue_style: str | None = None) -> tuple[str, str]:
    """(style name, where it came from). Pass the cue's and cues.yaml's `style:` when known."""
    if cue_style:
        return str(cue_style), "cue"
    if cues_style:
        return str(cues_style), "cues.yaml"
    val, origin = effective_style(project)
    return (val, origin) if val else ("base", "built-in fallback (nothing sets a style)")
