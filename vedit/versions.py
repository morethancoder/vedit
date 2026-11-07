"""External tool pins, in one place."""

HYPERFRAMES = "0.8.170"  # npx --yes hyperframes@<pin>
OPENCV = "4.10.0.84"  # opencv-python-headless, with numpy<2; pinned in pyproject.toml
GSAP = (
    "3.14.2"  # bundled as vedit/vendor/gsap/gsap.min.js, copied to hf/assets/ (no CDN); change both together
)
