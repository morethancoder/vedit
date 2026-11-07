"""Importer plugins: Python files in `<config>/importers/` (and folders in `$VEDIT_IMPORTERS`, `:`-separated).

Each plugin is your own code, loaded as-is. It defines:

    NAME = "myrec"                                   # optional, default: the file name
    def read(path: Path) -> Recording | None: ...    # None: not mine. RecordingError: mine, but broken
    def originals(origin: Path) -> tuple[list[tuple[Path, str]], list[Path]]: ...
        # optional, for `vedit clean --posted`: (paths to delete with why, paths kept and why not)

Files starting with `_` or `test_` are skipped. Plugins are tried in file-name order; the first match wins.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from vedit import channel as chan
from vedit.recording import Recording
from vedit.report import VeditError


@dataclass
class Importer:
    name: str
    file: Path
    module: ModuleType

    @property
    def about(self) -> str:
        doc = (self.module.__doc__ or "").strip()
        return doc.splitlines()[0] if doc else ""

    def read(self, path: Path) -> Recording | None:
        return self.module.read(path)

    def originals(self, origin: Path) -> tuple[list[tuple[Path, str]], list[Path]] | None:
        fn = getattr(self.module, "originals", None)
        return fn(origin) if fn else None


def dirs() -> list[Path]:
    out = [chan.config_dir() / "importers"]
    out += [Path(p).expanduser() for p in os.environ.get("VEDIT_IMPORTERS", "").split(os.pathsep) if p]
    return [d for d in out if d.is_dir()]


def _load(f: Path) -> Importer:
    mod_name = f"vedit_importer_{f.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, f)
    if spec is None or spec.loader is None:
        raise VeditError(f"importer {f}: cannot be loaded")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        raise VeditError(
            f"importer {f} failed to load: {e}", next=f"fix {f} or move it out of the folder"
        ) from e
    if not callable(getattr(mod, "read", None)):
        raise VeditError(f"importer {f} has no read(path) function", next="vedit guide importers")
    return Importer(str(getattr(mod, "NAME", f.stem)), f, mod)


def load() -> list[Importer]:
    found: dict[str, Importer] = {}
    for d in dirs():
        for f in sorted(d.glob("*.py")):
            if f.name.startswith(("_", "test_")):
                continue
            imp = _load(f)
            found.setdefault(imp.name, imp)
    return list(found.values())


def get(name: str | None) -> Importer | None:
    return next((i for i in load() if i.name == name), None) if name else None


def recognise(path: Path) -> tuple[Importer, Recording] | None:
    """The first importer that knows `path`, with what it read; None when none does (a plain video file)."""
    for imp in load():
        rec = imp.read(path)
        if rec is not None:
            if rec.camera is not None:
                rec.camera.check(f"{imp.name} importer, {path}")
            return imp, rec
    return None
