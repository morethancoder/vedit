"""Style authoring: draft packs from reference images, specimens, options, the creator's pick, promotion.

Stages, one module each: `refs` (copy screenshots / sample a video at scene changes), `palette` (OpenCV k-means,
Lab distance), `drafts` (where drafts live; new, fork, pick, save as file moves), `specimen` (the same sample
cues rendered by the phase 04 engine for any pack), `sheet` (PNG sheets). `vedit/commands/style.py` drives them.
vedit renders and measures; the agent and the creator judge the look.
"""
