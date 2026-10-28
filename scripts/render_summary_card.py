"""Render a series summary card from a series config and per-episode manifest."""
import argparse
import json
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def frame(ffmpeg, source, t):
    result = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-ss", str(t),
         "-i", str(source), "-frames:v", "1", "-f", "image2pipe",
         "-vcodec", "png", "pipe:1"], capture_output=True, check=True
    )
    return Image.open(BytesIO(result.stdout)).convert("RGB")


def cover(im, w, h):
    scale = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS)
    return im.crop(((im.width - w) // 2, (im.height - h) // 2,
                    (im.width + w) // 2, (im.height + h) // 2))


def fitted_font(draw, value, path, size, width):
    while size > 20 and draw.textbbox((0, 0), value, font=ImageFont.truetype(str(path), size))[2] > width:
        size -= 1
    result = ImageFont.truetype(str(path), size)
    if draw.textbbox((0, 0), value, font=result)[2] > width:
        raise ValueError(f"Text does not fit: {value}")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    args = ap.parse_args()
    cfg = read_json(args.config)
    ep = read_json(args.manifest)
    spec = cfg["summaryCard"]
    layout = spec["referenceLayout"]
    card = ep["summaryCard"]
    points = card["points"]
    times = card["sourceFrameSeconds"]
    if not 1 <= len(points) <= 5:
        raise ValueError("summaryCard.points must contain 1–5 items")
    if not spec["sourceFrameCountRange"][0] <= len(times) <= spec["sourceFrameCountRange"][1]:
        raise ValueError("summaryCard.sourceFrameSeconds count outside configured range")
    start, end = ep["selectedClip"]["sourceStartSeconds"], ep["selectedClip"]["sourceEndSeconds"]
    if not all(start <= t <= end for t in times):
        raise ValueError("Summary card frames must be inside selected clip")
    source = Path(ep["sourceVideoPath"])
    if not source.is_file():
        raise FileNotFoundError(source)
    font_dir = Path(r"C:\Windows\Fonts")
    cn, cn_bold, en_bold = (font_dir / name for name in ("msyh.ttc", "msyhbd.ttc", "arialbd.ttf"))
    font = lambda path, size: ImageFont.truetype(str(path), size)
    w, h = spec["widthPx"], spec["heightPx"]
    canvas = Image.new("RGB", (w, h))
    for i, t in enumerate(times):
        y0, y1 = round(i * h / len(times)), round((i + 1) * h / len(times))
        canvas.paste(cover(frame(args.ffmpeg, source, t), w, y1 - y0), (0, y0))
    canvas = canvas.filter(ImageFilter.GaussianBlur(layout["backgroundBlurRadiusPx"])).convert("RGBA")
    canvas = Image.alpha_composite(canvas, Image.new("RGBA", (w, h), tuple(layout["backgroundTintRgba"])))
    board = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(board).rounded_rectangle(tuple(layout["boardRectPx"]),
        radius=layout["boardCornerRadiusPx"], fill=tuple(layout["boardFillRgba"]))
    canvas = Image.alpha_composite(canvas, board)
    draw = ImageDraw.Draw(canvas)
    white, yellow, muted = (layout[k] for k in ("whiteHex", "yellowHex", "mutedHex"))
    label = cfg["episodeLabel"]["format"].format(prefix=cfg["episodeLabel"]["prefix"], episode=ep["episode"])
    draw.text(tuple(layout["episodePositionPx"]), label, font=font(cn_bold, layout["episodeFontSizePx"]), fill=white)
    title = cfg["workflow"]["transitionTitles"]["note"][0].format(count=len(points))
    draw.text(tuple(layout["titlePositionPx"]), title, font=font(cn_bold, layout["titleFontSizePx"]), fill=yellow)
    x = layout["entryXPx"]
    available = layout["boardRectPx"][2] - layout["entryRightPaddingPx"] - x
    first = layout["entryFirstYPx"]
    step = min(layout["entryStepYPx"],
               (layout["boardRectPx"][3] - layout["entryBottomPaddingPx"] - first) / max(1, len(points) - 1))
    for i, point in enumerate(points):
        y = round(first + i * step)
        for key, font_path, size_key, dy, color in (
            ("english", en_bold, "englishFontSizePx", 0, yellow),
            ("chinese", cn_bold, "chineseFontSizePx", layout["chineseOffsetYPx"], white),
            ("usage", cn, "usageFontSizePx", layout["usageOffsetYPx"], muted),
        ):
            value = point[key]
            draw.text((x, y + dy), value,
                font=fitted_font(draw, value, font_path, layout[size_key], available), fill=color)
    watermark = layout["bottomWatermarkText"]
    wf = font(cn, layout["bottomWatermarkFontSizePx"])
    box = draw.textbbox((0, 0), watermark, font=wf)
    draw.text(((w - (box[2] - box[0])) // 2, layout["bottomWatermarkYPx"]),
              watermark, font=wf, fill=white)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(args.output, optimize=True)
    print(args.output)


if __name__ == "__main__":
    main()
