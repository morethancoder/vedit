"""vedit formats: aspects and platform placements, with each one's canvas, HUD safe box and what a crop hides.
Several platforms at once print the area they all leave clear (where captions and graphics may go)."""

from __future__ import annotations

from vedit import formats as fm
from vedit.report import Report

EPILOG = "example: vedit formats instagram-reels tiktok youtube-shorts --json"


def add_args(sp) -> None:
    sp.add_argument("platforms", nargs="*", metavar="PLATFORM", help="platform ids (default: list them all)")
    sp.add_argument(
        "--aspect", metavar="W:H", help="canvas aspect for the safe box (default: the platform's)"
    )
    sp.epilog = EPILOG


def _row(pid: str, p: dict) -> dict:
    size = tuple(p["canvas"])
    return {
        "id": pid,
        "name": p["name"],
        "kind": p["kind"],
        "aspect": p["aspect"],
        "canvas": list(size),
        "safe_insets": {k: round(v) for k, v in fm.insets(pid, size).items()},
        "safe_box": fm.safe_box([pid], size).as_dict(),
        "hud": [{"name": r["name"], "what": r["what"], **r["box"].as_dict()} for r in fm.hud(pid, size)],
        "crops": p["crops"],
        "max_s": p["max_s"],
        "confidence": p["confidence"],
        "fallback": bool(p.get("fallback")),
        "sources": [s.get("url") for s in p["sources"]],
    }


def run(ns) -> Report:
    r = Report("formats")
    allp = fm.platforms()
    ids = ns.platforms or list(allp)
    for pid in ids:
        fm.platform(pid)  # unknown ids fail with bad_input before anything prints
    rows = [_row(pid, allp[pid]) for pid in ids]
    aspects = {x["aspect"] for x in rows}
    data: dict = {"aspects": {a: list(s) for a, s in fm.ASPECTS.items()}, "platforms": rows}
    for x in rows:
        i = x["safe_insets"]
        tag = " (fallback)" if x["fallback"] else ""
        r.info(
            f"{x['id']:<22} {x['aspect']:<5} {x['canvas'][0]}x{x['canvas'][1]}  "
            f"clear of top {i['top']} bottom {i['bottom']} left {i['left']} right {i['right']}  "
            f"[{x['confidence']}{tag}]"
        )
    if ns.platforms:
        aspect = ns.aspect or (aspects.pop() if len(aspects) == 1 else None)
        if aspect is None:
            r.warn(
                f"these platforms mix aspects ({', '.join(sorted({x['aspect'] for x in rows}))}): pass --aspect"
            )
        else:
            size = fm.canvas(aspect)
            same = [x["id"] for x in rows if fm.ratio(x["aspect"]) == fm.ratio(aspect)]
            box = fm.safe_box(same, size)
            r.ok_(
                f"safe box for {', '.join(same)} on {size[0]}x{size[1]}: x {box.x:.0f}-{box.x1:.0f}, "
                f"y {box.y:.0f}-{box.y1:.0f} ({box.w:.0f}x{box.h:.0f})"
            )
            data["union"] = {
                "aspect": aspect,
                "canvas": list(size),
                "platforms": same,
                "safe_box": box.as_dict(),
            }
    r.data = data
    r.next = "vedit guide formats"
    return r
