"""Check that nonfinal lines in a rendered knowledge card use the available width."""
import argparse
import json
from pathlib import Path

from PIL import Image


def line_boxes(image, x0, x1, y0, y1):
    pixels = image.load()
    rows = []
    for y in range(y0, y1):
        xs = []
        for x in range(x0, x1):
            r, g, b = pixels[x, y][:3]
            if min(r, g, b) >= 205 and max(r, g, b) - min(r, g, b) <= 35:
                xs.append(x)
        if len(xs) >= 5:
            rows.append((y, min(xs), max(xs)))
    groups = []
    for row in rows:
        if groups and row[0] - groups[-1][-1][0] <= 4:
            groups[-1].append(row)
        else:
            groups.append([row])
    return [(g[0][0], g[-1][0], min(r[1] for r in g), max(r[2] for r in g)) for g in groups]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--card", required=True, type=Path, action="append")
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8-sig"))
    layout = cfg["cardLayout"]
    typ = layout["typography"]
    min_ratio = typ["usageNonFinalLineMinFillRatio"]
    left = layout["textLeftPx"]
    right = layout["contentHorizontalBoundsPx"][1] - layout["bodyRightPaddingPx"]
    failed = False
    for path in args.card:
        im = Image.open(path).convert("RGB")
        boxes = line_boxes(im, left, right, typ["usageBodyYPx"], layout["usageCardYRangePx"][1] - 10)
        if not boxes:
            raise ValueError(f"No usage text found: {path}")
        ratios = [round((b[3] - b[2] + 1) / (right - left), 3) for b in boxes]
        status = "PASS" if all(r >= min_ratio for r in ratios[:-1]) else "FAIL"
        failed |= status == "FAIL"
        print(f"{status} {path.name}: line fill {ratios}; min nonfinal {min_ratio}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
