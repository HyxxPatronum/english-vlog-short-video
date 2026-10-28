"""Objective QA for the English VLOG series. No LLM or image model is used."""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
from io import BytesIO
from pathlib import Path


def check(report, name, status, detail):
    report.append({"check": name, "status": status, "detail": detail})


def ass_color(hex_rgb, opacity=1.0):
    rgb = hex_rgb.removeprefix("#")
    return f"&H{round((1-opacity)*255):02X}{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}".upper()


def validate_config(cfg, report):
    try:
        assert cfg["schemaVersion"] == 1
        render = cfg["render"]
        assert render["canvasWidthPx"] > 0 and render["canvasHeightPx"] > 0
        assert render["fps"] > 0 and render["sampleAspectRatio"] == "1:1"
        assert render["videoCodec"] == "h264" and render["audioChannels"] == 2
        assert render["audioBitrateBps"] > 0
        assert 0 <= render["videoCrfTarget"] <= render["videoCrfMaximum"] <= 51
        bg = cfg["subtitle"]["background"]
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", bg["colorHex"])
        assert 0 < bg["opacity"] < 1
        lo, hi = bg["qaOpacityRange"]
        assert 0 <= lo <= bg["opacity"] <= hi <= 1
        assert bg["assBorderStyle"] == 1 and bg["boxRenderMode"] == "singleVectorRectanglePerCue"
        assert cfg["subtitle"]["text"]["horizontalScalePercent"] == 100
        assert cfg["subtitle"]["text"]["longLinePolicy"] == "splitIntoSequentialSingleLineCues"
        video = cfg["subtitle"]["mainVideo"]
        assert 0 <= video["xPx"] < render["canvasWidthPx"]
        assert 0 <= video["yPx"] < render["canvasHeightPx"]
        assert video["xPx"] + video["widthPx"] <= render["canvasWidthPx"]
        assert video["yPx"] + video["heightPx"] <= render["canvasHeightPx"]
        card = cfg["cardLayout"]
        assert cfg["episodeLabel"]["prefix"] and "{prefix}" in cfg["episodeLabel"]["format"]
        assert cfg["workflow"]["orderedStages"] == ["bilingualOriginal", "noteTransition", "knowledgeReplayAndExplanation", "blindTransition", "blindOriginal"]
        assert cfg["workflow"]["replayAndNarrationShareFullCard"] is True
        assert cfg["workflow"]["replaySource"] == "selectedClipOfCurrentEpisode"
        assert cfg["workflow"]["knowledgePointStages"] == ["normalSpeedReplay", "slowSpeedReplay", "slowReplayEndFrameHold", "staticCardNarration"]
        top = card["topVideoRectPx"]
        freeze = card["staticTailFramePolicy"]
        assert freeze["source"] == "lastFrameOfSlowReplay" and freeze["humanReviewRequired"] is True
        assert freeze["subtitleAndWatermarkMustMatchReplay"] is True and freeze["pixelMatchMaxMae"] >= 0
        assert 0 < freeze["transitionToStaticSeconds"] <= 0.5
        assert 0 < freeze["tailHoldSeconds"] <= 0.5
        assert 0 < freeze["replayTagFadeOutSeconds"] < freeze["tailHoldSeconds"]
        assert 0 <= freeze["replayTagFadeStartOffsetFromHoldSeconds"] < freeze["tailHoldSeconds"]
        assert freeze["replayTagFadeStartOffsetFromHoldSeconds"] + freeze["replayTagFadeOutSeconds"] <= freeze["tailHoldSeconds"]
        assert freeze["replayTagMustBeAbsentFromStaticCard"] is True
        assert cfg["timing"]["staticFrameHoldSeconds"] > 0 and cfg["timing"]["staticFrameHoldToleranceSeconds"] >= 0
        cap = card["replayCaption"]
        top_cap = card["topSubtitle"]
        assert cap["fontSizePx"] == cfg["subtitle"]["text"]["englishFontSizePx"]
        assert cap["baselineYPx"] == top[3] - top_cap["bottomInsetPx"]
        assert cap["boxTopYPx"] == cap["baselineYPx"] - top_cap["boxTopInsetPx"]
        assert cap["boxBottomYPx"] == cap["baselineYPx"] + top_cap["boxBottomOffsetPx"]
        assert cap["horizontalPaddingPx"] == top_cap["horizontalPaddingPx"]
        assert cap["backgroundColorHex"] == cfg["subtitle"]["background"]["colorHex"]
        assert cap["backgroundOpacity"] == cfg["subtitle"]["background"]["opacity"]
        assert card["topVideoBorder"]["enabled"] is False and card["topVideoBorder"]["widthPx"] == 0
        assert 0 <= top[0] < top[2] <= render["canvasWidthPx"]
        assert 0 <= top[1] < top[3] <= render["canvasHeightPx"]
        typ = card["typography"]
        assert typ["episodeLabelYPx"] < card["dividerYPx"]
        assert typ["episodeToExpressionVisibleGapPx"] > 0 and typ["expressionToMeaningVisibleGapPx"] > 0
        assert typ["visibleGapEqualityTolerancePx"] >= 0 and typ["visibleGapTargetTolerancePx"] >= 0
        assert typ["meaningToDividerMinGapPx"] >= 0
        assert typ["usageTitleYPx"] < typ["usageBodyYPx"] < card["usageCardYRangePx"][1]
        assert typ["exampleTitleYPx"] < typ["exampleBodyYPx"] < card["exampleCardYRangePx"][1]
        tr = cfg["transitionLayout"]
        assert cfg["workflow"]["transitionTitles"]["note"] == ["{count}个日常表达", "做笔记了喔！"]
        assert cfg["workflow"]["transitionTitles"]["blind"] == ["去掉字幕", "盲听看看能听懂多少"]
        assert tr["effectOrder"] == ["blurAndDarkenBackground", "fadeInRabbitAndTextWithLift", "clearHold", "fadeOutElements", "restoreNextScene"]
        assert tr["soundEffectPlayback"] == "completeOncePerTransition"
        assert cfg["watermark"]["transitionPolicy"] == "noOverlayDuringTransition"
        assert "noteTransition" not in cfg["watermark"]["appliesTo"] and "blindTransition" not in cfg["watermark"]["appliesTo"]
        from PIL import ImageFont
        title_font = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", tr["titleFontSizePx"])
        subtitle_font = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", tr["subtitleFontSizePx"])
        title_box = title_font.getbbox(cfg["workflow"]["transitionTitles"]["note"][0].format(count=3))
        subtitle_box = subtitle_font.getbbox(cfg["workflow"]["transitionTitles"]["note"][1])
        title_bottom = tr["titleYPx"] + title_box[3]
        line_y = tr["dividerLinePx"][1]
        subtitle_top = tr["subtitleYPx"] + subtitle_box[1]
        gap1 = line_y - title_bottom
        gap2 = subtitle_top - (line_y + 3)
        assert abs(gap1 - tr["visibleGapPx"]) <= tr["visibleGapTolerancePx"], f"title-to-line gap {gap1}px"
        assert abs(gap2 - tr["visibleGapPx"]) <= tr["visibleGapTolerancePx"], f"line-to-subtitle gap {gap2}px"
        assert 0 < tr["entryBlurSeconds"] < tr["exitStartSeconds"] < cfg["timing"]["transitionTargetSeconds"]
        assert tr["exitStartSeconds"] + tr["exitDurationSeconds"] <= cfg["timing"]["transitionTargetSeconds"]
        q=cfg["qa"]
        assert q["replaySourceMatchMaxPixelMae"] > 0 and q["replaySourceSampleSeconds"] > 0
        assert len(q["replaySourceCropInsetsPx"]) == 4 and all(v >= 0 for v in q["replaySourceCropInsetsPx"])
        assert card["usageCardYRangePx"][0] - card["dividerYPx"] == card["dividerToUsageGapPx"]
        assert card["exampleCardYRangePx"][0] - card["usageCardYRangePx"][1] == card["betweenCardsGapPx"]
        palette = card["palette"]
        for key in ("backgroundColorHex", "usagePanelColorHex", "examplePanelColorHex"):
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", palette[key]), key
        cut = cfg["cutting"]
        assert cut["requireCompleteLastAudiblePhoneme"] and cut["asrTimestampsAreLocatorsOnly"]
        low_tail, high_tail = cut["preferredNaturalTailSeconds"]
        assert 0 < low_tail <= high_tail < cut["reviewFinalSeconds"]
        assert 0 < cut["slowReplaySpeed"] <= 1
        assert cfg["summaryCard"]["sourceFrameCountRange"] == [2, 3]
        watermark = cfg["watermark"]
        assert watermark["widthPx"] > 0 and watermark["heightPx"] > 0
        assert watermark["insetFromVlogVideoXPx"] >= 0 and watermark["insetFromVlogVideoYPx"] >= 0
        assert re.fullmatch(r"[0-9A-Fa-f]{64}", watermark["sha256"])
        assert watermark["assetBuild"]["backgroundFromSubtitleConfig"] is True
        check(report, "config.schema_and_relations", "PASS", f"v{cfg['configVersion']}; ASS background {ass_color(bg['colorHex'], bg['opacity'])}; tail {math.ceil(low_tail*render['fps'])}-{round(high_tail*render['fps'])} frames")
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        check(report, "config.schema_and_relations", "FAIL", f"Invalid or inconsistent parameter: {exc}")


def validate_transition_assets(config_path, cfg, report):
    try:
        for key, item in cfg["transitionAssets"].items():
            path = config_path.parent.parent / item["assetRelativePath"]
            assert path.is_file(), f"{key}: missing {path}"
            actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
            assert actual == item["sha256"].upper(), f"{key}: SHA-256 mismatch"
        check(report, "transition.assets", "PASS", "Rabbit GIFs and sound effect SHA-256 match")
    except (AssertionError, KeyError, OSError) as exc:
        check(report, "transition.assets", "FAIL", str(exc))


def parse_ass(path):
    text = path.read_text(encoding="utf-8-sig")
    info = {}
    styles = {}
    events = []
    for line in text.splitlines():
        if line.startswith("PlayResX:") or line.startswith("PlayResY:"):
            key, value = line.split(":", 1)
            info[key] = int(value.strip())
        elif line.startswith("Style: "):
            fields = [v.strip() for v in line.removeprefix("Style: ").split(",")]
            styles[fields[0]] = fields
        elif line.startswith("Dialogue: "):
            fields = line.removeprefix("Dialogue: ").split(",", 9)
            events.append({"start": fields[1], "end": fields[2], "style": fields[3], "name": fields[4], "text": fields[9]})
    return text, info, styles, events


def ass_time(value):
    h, m, rest = value.split(":")
    return int(h)*3600 + int(m)*60 + float(rest)


def validate_ass(path, cfg, report):
    try:
        text, info, styles, events = parse_ass(path)
        r = cfg["render"]
        assert info == {"PlayResX": r["canvasWidthPx"], "PlayResY": r["canvasHeightPx"]}
        sub = cfg["subtitle"]
        bg = sub["background"]
        clearance = bg["minimumClearanceFromVideoPx"]
        assert bg["preventBackgroundOverlap"] is True and bg["chineseEnglishBoxesMustNotOverlap"] is True
        expected_bg = ass_color(bg["colorHex"], bg["opacity"])
        white = ass_color(sub["text"]["defaultColorHex"])
        transparent = "&HFF000000"
        specs = {
            "CN": (sub["text"]["chineseFont"], sub["text"]["chineseFontSizePx"]),
            "EN": (sub["text"]["englishFont"], sub["text"]["englishFontSizePx"]),
        }
        for name, (font, size) in specs.items():
            fields = styles[name]
            assert fields[1] == font and int(fields[2]) == size, f"{name} font/size"
            assert fields[3].upper() == white, f"{name} text color"
            assert int(fields[11]) == sub["text"]["horizontalScalePercent"], f"{name} horizontal scaling"
            assert fields[5].upper() == transparent and fields[6].upper() == transparent, f"{name} text style must have no background"
            assert int(fields[15]) == 1 and int(fields[16]) == 0 and int(fields[17]) == 0, f"{name} must not draw a box"
        box_style = styles["Box"]
        assert box_style[3].upper() == expected_bg, "Box vector fill color/opacity"
        assert int(box_style[15]) == 1 and int(box_style[16]) == 0 and int(box_style[17]) == 0
        main = sub["mainVideo"]
        place = sub["placement"]
        expected_pos = {
            "CN": (main["xPx"]+main["widthPx"]//2, main["yPx"]+place["chineseBaselineOffsetFromMainTopPx"]),
            "EN": (main["xPx"]+main["widthPx"]//2, main["yPx"]+main["heightPx"]-place["englishBaselineInsetFromMainBottomPx"]),
        }
        grouped = {name: [] for name in specs}
        vector_boxes = {}
        for event in events:
            assert ass_time(event["start"]) < ass_time(event["end"]), "empty subtitle event"
            if event["style"] in grouped:
                grouped[event["style"]].append(event)
                pos = re.search(r"\\pos\((\d+),(\d+)\)", event["text"])
                assert pos and tuple(map(int, pos.groups())) == expected_pos[event["style"]], f"{event['style']} position"
            elif event["style"] == "Box":
                pos = re.search(r"\\pos\((\d+),(\d+)\)", event["text"])
                dims = re.search(r"l (\d+) 0 l \d+ (\d+) l 0 \d+", event["text"])
                assert pos and dims and r"\p1" in event["text"] and r"\p0" in event["text"], "Invalid subtitle background vector"
                x, y = map(int, pos.groups()); width, height = map(int, dims.groups())
                vector_boxes[(event["start"], event["end"], event["name"])] = (x, y, x+width, y+height)
        assert len(grouped["CN"]) == len(grouped["EN"]) > 0
        assert len(vector_boxes) == 2 * len(grouped["CN"]), "Expected exactly one vector background per subtitle cue"
        for cn, en in zip(grouped["CN"], grouped["EN"]):
            assert (cn["start"], cn["end"]) == (en["start"], en["end"]), "Chinese/English timing mismatch"
            cnbox = vector_boxes.get((cn["start"], cn["end"], "CN"))
            enbox = vector_boxes.get((en["start"], en["end"], "EN"))
            assert cnbox and enbox, f"Missing unique background box at {cn['start']}"
            assert cnbox[3] <= main["yPx"] - clearance, f"Chinese subtitle background touches main video at {cn['start']}"
            assert enbox[1] >= main["yPx"] + clearance, f"English subtitle background escapes video top at {en['start']}"
            assert enbox[3] <= main["yPx"] + main["heightPx"] - clearance, f"English subtitle background touches video bottom at {en['start']}"
            assert cnbox[3] + clearance <= enbox[1], f"Chinese/English subtitle backgrounds overlap at {cn['start']}"
            assert cnbox[0] >= 0 and cnbox[2] <= r["canvasWidthPx"] and enbox[0] >= 0 and enbox[2] <= r["canvasWidthPx"], "Subtitle background exceeds canvas"
        from PIL import ImageFont
        font_paths = {"EN": r"C:\Windows\Fonts\arialbd.ttf", "CN": r"C:\Windows\Fonts\msyh.ttc"}
        for name, cues in grouped.items():
            size = specs[name][1]
            font = ImageFont.truetype(font_paths[name], size)
            prior_end = None
            for cue in sorted(cues, key=lambda e: ass_time(e["start"])):
                plain = re.sub(r"\{[^}]*\}", "", cue["text"])
                lines = re.split(r"\\[Nn]", plain)
                assert all(line.strip() for line in lines), f"{name} caption has an empty line"
                assert not re.search(r"\\fscx\d+", cue["text"], re.IGNORECASE), f"{name} caption must not be horizontally scaled"
                assert all(font.getlength(line) <= sub["text"]["maximumLineWidthPx"] for line in lines), f"{name} caption line is too wide: {plain}"
                start, end = ass_time(cue["start"]), ass_time(cue["end"])
                assert prior_end is None or start >= prior_end, f"{name} subtitle cues overlap"
                prior_end = end
        assert "Watermark" not in styles and not any(event["style"] == "Watermark" for event in events), "Watermark must be overlaid from the fixed PNG asset, not drawn in ASS"
        highlight = ass_color(sub["text"]["highlightColorHex"])[-6:]
        marker = f"\\c&H{highlight}&"
        assert marker in text, "highlight color missing"
        assert sub["text"]["highlightTargets"] == ["englishKnowledgeSpan", "chineseEquivalentSpan"]
        highlighted_pairs = 0
        for cn, en in zip(grouped["CN"], grouped["EN"]):
            if marker in en["text"]:
                assert marker in cn["text"], f"Chinese highlight missing at {cn['start']}"
                highlighted_pairs += 1
            else:
                assert marker not in cn["text"], f"Chinese highlight without English match at {cn['start']}"
        assert highlighted_pairs > 0, "No highlighted bilingual knowledge cues"
        check(report, "ass.styles_layout_and_cues", "PASS", f"{len(grouped['CN'])} matched bilingual cues; {highlighted_pairs} matched highlight pairs; one nonoverlapping background rectangle per cue")
    except (AssertionError, KeyError, IndexError, ValueError) as exc:
        check(report, "ass.styles_layout_and_cues", "FAIL", str(exc) or "ASS check failed")

def resolve_watermark(config_path, cfg, explicit):
    if explicit:
        return explicit
    installed = config_path.parent.parent / cfg["watermark"]["assetRelativePath"]
    if installed.exists():
        return installed
    adjacent = config_path.parent / Path(cfg["watermark"]["assetRelativePath"]).name
    return adjacent


def validate_watermark_asset(path, cfg, report):
    try:
        from PIL import Image
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest().upper()
        wm = cfg["watermark"]
        assert digest == wm["sha256"].upper(), f"SHA-256 mismatch: {digest}"
        with Image.open(BytesIO(raw)) as im:
            assert im.format == "PNG" and im.mode == "RGBA", f"got {im.format}/{im.mode}, expected PNG/RGBA"
            assert im.size == (wm["widthPx"], wm["heightPx"]), f"wrong dimensions {im.size}"
            assert im.getpixel((0,0))[3] == 0, "transparent outer corner missing"
            center_bg = im.getpixel((wm["widthPx"]-5, wm["heightPx"]-5))
            expected_alpha = round(cfg["subtitle"]["background"]["opacity"]*255)
            assert abs(center_bg[3]-expected_alpha) <= 1, f"background alpha {center_bg[3]}, expected {expected_alpha}"
        check(report, "watermark.asset", "PASS", f"PNG/RGBA {wm['widthPx']}x{wm['heightPx']}; SHA-256 match")
    except (AssertionError, ImportError, OSError, KeyError) as exc:
        check(report, "watermark.asset", "FAIL", str(exc))


def find_ffmpeg(requested):
    if requested:
        return requested
    if os.getenv("FFMPEG_BIN"):
        return os.environ["FFMPEG_BIN"]
    found = shutil.which("ffmpeg")
    if found:
        return found
    local = Path(r"C:\Program Files\Steinberg\Cubase 15\Externals\FFmpeg\5.1.1\ffmpeg.exe")
    return str(local) if local.exists() else None


def media_info(path, ffmpeg):
    p = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace")
    out = p.stderr + p.stdout
    duration = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", out)
    video = next((line for line in out.splitlines() if re.search(r"Stream #.*Video:", line)), "")
    audio = next((line for line in out.splitlines() if re.search(r"Stream #.*Audio:", line)), "")
    if not duration or not video:
        raise ValueError("ffmpeg did not return video metadata")
    dims = re.search(r"\b(\d{2,5})x(\d{2,5})\b", video)
    fps = re.search(r"\b(\d+(?:\.\d+)?) fps\b", video)
    sar = re.search(r"SAR (\d+):(\d+)", video)
    sample_rate = re.search(r"\b(\d+) Hz\b", audio)
    return {
        "durationSeconds": int(duration[1])*3600+int(duration[2])*60+float(duration[3]),
        "width": int(dims[1]) if dims else None,
        "height": int(dims[2]) if dims else None,
        "fps": float(fps[1]) if fps else None,
        "sar": f"{sar[1]}:{sar[2]}" if sar else None,
        "videoCodec": re.search(r"Video: ([\w]+)", video)[1] if re.search(r"Video: ([\w]+)", video) else None,
        "pixelFormat": re.search(r"Video:.*?, ([\w]+)\(", video)[1] if re.search(r"Video:.*?, ([\w]+)\(", video) else None,
        "audioCodec": re.search(r"Audio: ([\w]+)", audio)[1] if re.search(r"Audio: ([\w]+)", audio) else None,
        "audioSampleRateHz": int(sample_rate[1]) if sample_rate else None,
        "audioChannels": 2 if "stereo" in audio else (1 if "mono" in audio else None),
    }


def validate_video(path, cfg, report, ffmpeg, manifest):
    if not ffmpeg:
        check(report, "video.metadata", "SKIP", "ffmpeg unavailable")
        return
    try:
        info = media_info(path, ffmpeg)
        r = cfg["render"]
        expected = {k: r[k] for k in ("videoCodec", "pixelFormat", "audioCodec", "audioSampleRateHz", "audioChannels")}
        expected.update(width=r["canvasWidthPx"], height=r["canvasHeightPx"], fps=r["fps"], sar=r["sampleAspectRatio"])
        mismatches = [f"{k}: got {info[k]}, expected {v}" for k,v in expected.items() if info[k] != v]
        if manifest and manifest.get("videoRole", "subtitlePreview") in ("subtitlePreview", "blindPreview") and "selectedClip" in manifest:
            clip = manifest["selectedClip"]
            expected_duration = clip["sourceEndSeconds"] - clip["sourceStartSeconds"] + clip.get("tailHoldSeconds", 0)
            if abs(info["durationSeconds"] - expected_duration) > cfg["qa"]["metadataDurationToleranceSeconds"]:
                mismatches.append(f"duration: got {info['durationSeconds']:.3f}, expected {expected_duration:.3f}")
        elif manifest and manifest.get("videoRole") == "fullFinal" and manifest.get("timeline"):
            expected_duration = max(item["endSeconds"] for item in manifest["timeline"])
            if abs(info["durationSeconds"] - expected_duration) > cfg["qa"]["metadataDurationToleranceSeconds"]:
                mismatches.append(f"duration: got {info['durationSeconds']:.3f}, expected timeline end {expected_duration:.3f}")
        check(report, "video.metadata", "FAIL" if mismatches else "PASS", "; ".join(mismatches) if mismatches else f"{info['width']}x{info['height']} {info['fps']} fps; {info['durationSeconds']:.3f}s; audio {info['audioSampleRateHz']}Hz/{info['audioChannels']}ch")
    except (OSError, ValueError, KeyError) as exc:
        check(report, "video.metadata", "FAIL", str(exc))


def decoded_frame(path, seconds, ffmpeg):
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{seconds:.3f}", "-i", str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1"],
        capture_output=True,
    )
    if proc.returncode or not proc.stdout:
        raise ValueError(f"Cannot decode frame at {seconds:.3f}s from {path}")
    from PIL import Image
    return Image.open(BytesIO(proc.stdout)).convert("RGB")


def estimate_opacity(rendered, baseline, region, bg_rgb):
    x0, y0, x1, y1 = region
    a_values = []
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 4):
            base = baseline.getpixel((x, y))
            out = rendered.getpixel((x, y))
            if sum(base) - sum(out) < 30:
                continue
            delta = [base[c] - bg_rgb[c] for c in range(3)]
            denom = sum(v*v for v in delta)
            if denom < 2500:
                continue
            alpha = sum(delta[c]*(base[c]-out[c]) for c in range(3)) / denom
            if 0.2 <= alpha <= 2.0:
                a_values.append(alpha)
    if len(a_values) < 80:
        raise ValueError(f"Only {len(a_values)} usable box pixels")
    return statistics.median(a_values), len(a_values)


def validate_rendered_opacity(video, baseline, cfg, manifest, report, ffmpeg):
    if not baseline:
        check(report, "video.rendered_subtitle_opacity", "REVIEW_REQUIRED", "No uncaptioned baseline video supplied for pixel comparison")
        return
    if not ffmpeg:
        check(report, "video.rendered_subtitle_opacity", "SKIP", "ffmpeg unavailable")
        return
    if not manifest or not manifest.get("subtitleQaSampleSeconds"):
        check(report, "video.rendered_subtitle_opacity", "SKIP", "Subtitle sample times missing from manifest")
        return
    try:
        sub = cfg["subtitle"]
        rgb = tuple(int(sub["background"]["colorHex"][i:i+2], 16) for i in (1,3,5))
        top = sub["mainVideo"]["yPx"]
        bottom = top + sub["mainVideo"]["heightPx"]
        regions = {
            "CN": (70, top-70, cfg["render"]["canvasWidthPx"]-70, top-5),
            "EN": (70, bottom-105, cfg["render"]["canvasWidthPx"]-70, bottom-5),
        }
        values = []
        for label, seconds in manifest["subtitleQaSampleSeconds"].items():
            rendered = decoded_frame(video, seconds, ffmpeg)
            clean = decoded_frame(baseline, seconds, ffmpeg)
            assert rendered.size == clean.size, "baseline dimensions mismatch"
            for role, region in regions.items():
                alpha, count = estimate_opacity(rendered, clean, region, rgb)
                values.append((label, role, alpha, count))
        lo, hi = sub["background"]["qaOpacityRange"]
        failures = [f"{label}/{role}={alpha:.3f}" for label, role, alpha, _ in values if not lo <= alpha <= hi]
        details = ", ".join(f"{label}/{role}={alpha:.3f}({count}px)" for label, role, alpha, count in values)
        check(report, "video.rendered_subtitle_opacity", "FAIL" if failures else "PASS", details)
    except (AssertionError, ValueError, ImportError, OSError) as exc:
        check(report, "video.rendered_subtitle_opacity", "FAIL", str(exc))


def validate_rendered_watermark(video, baseline, watermark_path, cfg, manifest, report, ffmpeg):
    if not baseline or not ffmpeg:
        check(report, "video.rendered_watermark", "REVIEW_REQUIRED", "Uncaptioned baseline and ffmpeg required")
        return
    try:
        from PIL import Image
        seconds = 12.2
        if manifest and manifest.get("subtitleQaSampleSeconds"):
            seconds = next(iter(manifest["subtitleQaSampleSeconds"].values()))
        final = decoded_frame(video, seconds, ffmpeg)
        clean = decoded_frame(baseline, seconds, ffmpeg)
        with Image.open(watermark_path) as im:
            wm = im.convert("RGBA")
        main = cfg["subtitle"]["mainVideo"]
        settings = cfg["watermark"]
        x0 = main["xPx"] + settings["insetFromVlogVideoXPx"]
        y0 = main["yPx"] + settings["insetFromVlogVideoYPx"]
        errors = []
        for y in range(2, wm.height-2, 3):
            for x in range(2, wm.width-2, 3):
                wr,wg,wb,wa = wm.getpixel((x,y))
                if wa < 32:
                    continue
                base = clean.getpixel((x0+x,y0+y))
                actual = final.getpixel((x0+x,y0+y))
                a = wa/255
                expected = (a*wr+(1-a)*base[0], a*wg+(1-a)*base[1], a*wb+(1-a)*base[2])
                errors.append(sum(abs(actual[c]-expected[c]) for c in range(3))/3)
        error = statistics.median(errors)
        status = "PASS" if error <= 15 else "FAIL"
        check(report, "video.rendered_watermark", status, f"median RGB error {error:.1f}/255 across {len(errors)} asset pixels")
    except (AssertionError, ValueError, ImportError, OSError) as exc:
        check(report, "video.rendered_watermark", "FAIL", str(exc))


def validate_blind_no_captions(video, baseline, cfg, manifest, report, ffmpeg):
    if not baseline or not ffmpeg:
        check(report, "video.blind_has_no_captions", "REVIEW_REQUIRED", "Uncaptioned baseline and ffmpeg required")
        return
    try:
        seconds = 12.2
        if manifest and manifest.get("subtitleQaSampleSeconds"):
            seconds = next(iter(manifest["subtitleQaSampleSeconds"].values()))
        final = decoded_frame(video, seconds, ffmpeg)
        clean = decoded_frame(baseline, seconds, ffmpeg)
        top = cfg["subtitle"]["mainVideo"]["yPx"]
        bottom = top + cfg["subtitle"]["mainVideo"]["heightPx"]
        regions = [(100, top-65, 980, top-5), (100, bottom-100, 980, bottom-5)]
        errors = []
        for x0,y0,x1,y1 in regions:
            for y in range(y0,y1,4):
                for x in range(x0,x1,8):
                    a = final.getpixel((x,y))
                    b = clean.getpixel((x,y))
                    errors.append(sum(abs(a[c]-b[c]) for c in range(3))/3)
        median = statistics.median(errors)
        check(report, "video.blind_has_no_captions", "PASS" if median <= 8 else "FAIL", f"median RGB difference {median:.1f}/255 across subtitle zones")
    except (ValueError, ImportError, OSError) as exc:
        check(report, "video.blind_has_no_captions", "FAIL", str(exc))


def validate_manifest(cfg, manifest, report):
    if not manifest:
        check(report, "episode.cut_margins", "SKIP", "No episode manifest supplied")
        return
    clip = manifest.get("selectedClip", {})
    if not {"sourceStartSeconds", "sourceEndSeconds"} <= clip.keys():
        check(report, "episode.cut_margins", "FAIL", "Missing source cut points")
        return
    duration = clip["sourceEndSeconds"] - clip["sourceStartSeconds"]
    lo, hi = cfg["selection"]["preferredDurationSeconds"]
    if lo <= duration <= hi:
        status = "PASS"
    elif cfg["selection"]["durationIsHardLimit"]:
        status = "FAIL"
    else:
        status = "PASS_EXCEPTION" if clip.get("durationExceptionReason") else "WARN"
    check(report, "episode.preferred_duration", status, f"{duration:.3f}s; preferred {lo}-{hi}s")
    if not clip.get("lastPhonemeHumanReviewed"):
        check(report, "episode.cut_margins", "REVIEW_REQUIRED", "Last audible phoneme has no human-reviewed endpoint; ASR estimate cannot pass this check")
        return
    phoneme = clip.get("lastAudiblePhonemeEndSeconds")
    if phoneme is None:
        check(report, "episode.cut_margins", "FAIL", "Human-reviewed phoneme endpoint missing")
        return
    margin = duration - phoneme
    min_margin, max_margin = cfg["cutting"]["preferredNaturalTailSeconds"]
    status = "FAIL" if margin < min_margin else ("WARN" if margin > max_margin else "PASS")
    check(report, "episode.cut_margins", status, f"tail margin {margin:.3f}s; preferred {min_margin}-{max_margin}s")


def validate_timeline(cfg, manifest, report):
    if not manifest or not manifest.get("timeline"):
        return
    specs = {
        "transition": ("transitionTargetSeconds", "transitionToleranceSeconds"),
        "cardLead": ("cardLeadInSeconds", "cardLeadInToleranceSeconds"),
        "cardTail": ("cardTailAfterNarrationSeconds", "cardTailToleranceSeconds"),
        "slowReplayEndFrameHold": ("staticFrameHoldSeconds", "staticFrameHoldToleranceSeconds"),
    }
    problems = []
    replay_pairs = {}
    for index, item in enumerate(manifest["timeline"]):
        kind = item.get("kind")
        if kind == "replayGap":
            problems.append(f"{index}: replay gap is not allowed between normal and slow replay")
        if kind in ("normalSpeedReplay", "slowSpeedReplay"):
            replay_pairs.setdefault(item.get("pointId"), {})[kind] = item
        if kind not in specs:
            continue
        target_key, tolerance_key = specs[kind]
        actual = item["endSeconds"] - item["startSeconds"]
        target = cfg["timing"][target_key]
        tolerance = cfg["timing"][tolerance_key]
        if abs(actual-target) > tolerance:
            problems.append(f"{index}:{kind} {actual:.3f}s, expected {target}±{tolerance}s")
    for point_id, pair in replay_pairs.items():
        if set(pair) != {"normalSpeedReplay", "slowSpeedReplay"}:
            problems.append(f"{point_id}: normal/slow replay pair incomplete")
            continue
        normal_end = pair["normalSpeedReplay"]["endSeconds"]
        slow_start = pair["slowSpeedReplay"]["startSeconds"]
        if abs(normal_end - slow_start) > 1/cfg["render"]["fps"]:
            problems.append(f"{point_id}: normal/slow replay gap {slow_start-normal_end:.3f}s")
    check(report, "episode.timeline_numeric_timing", "FAIL" if problems else "PASS", "; ".join(problems) if problems else "All timed segment kinds within configured tolerances")


def validate_summary_card(path, cfg, report):
    try:
        from PIL import Image
        with Image.open(path) as im:
            actual = im.size
            expected = (cfg["summaryCard"]["widthPx"], cfg["summaryCard"]["heightPx"])
            assert actual == expected, f"got {actual}, expected {expected}"
            assert im.format == "PNG", f"got {im.format}, expected PNG"
        check(report, "summary_card.format", "PASS", f"PNG {actual[0]}x{actual[1]}")
    except (AssertionError, ImportError, OSError) as exc:
        check(report, "summary_card.format", "FAIL", str(exc))


def validate_knowledge_card_palette(paths, cfg, report):
    try:
        from PIL import Image
        pal = cfg["cardLayout"]["palette"]
        right=cfg["cardLayout"]["contentHorizontalBoundsPx"][1]
        samples = [((800, 1800), pal["backgroundColorHex"]), ((right-10, 1200), pal["usagePanelColorHex"]), ((right-10, 1500), pal["examplePanelColorHex"])]
        gaps=[]
        for path in paths:
            with Image.open(path) as im:
                assert im.size == (cfg["render"]["canvasWidthPx"], cfg["render"]["canvasHeightPx"]), path.name
                rgb = im.convert("RGB")
                for xy, color in samples:
                    expected = tuple(bytes.fromhex(color.lstrip("#")))
                    actual = rgb.getpixel(xy)
                    assert max(abs(a-b) for a, b in zip(actual, expected)) <= 3, f"{path.name} {xy}: {actual} expected {expected}"
                x0, y0, x1, y1 = cfg["cardLayout"]["topVideoRectPx"]
                white_edge = sum(min(rgb.getpixel((x0, y))) >= 225 for y in range(y0+20, y1-20, 5))
                count = len(range(y0+20, y1-20, 5))
                assert white_edge / count < .4, f"{path.name}: possible white top-video frame ({white_edge}/{count} edge samples)"
                panel_right = cfg["cardLayout"]["contentHorizontalBoundsPx"][1]
                usage_color = tuple(bytes.fromhex(pal["usagePanelColorHex"].lstrip("#")))
                background_color = tuple(bytes.fromhex(pal["backgroundColorHex"].lstrip("#")))
                assert rgb.getpixel((panel_right-10, 1200)) == usage_color, f"{path.name}: usage panel right edge"
                assert rgb.getpixel((panel_right+10, 1200)) == background_color, f"{path.name}: usage panel extends past configured right edge"
                left=cfg["cardLayout"]["textLeftPx"]
                yellow=tuple(bytes.fromhex(cfg["subtitle"]["text"]["highlightColorHex"].lstrip("#")))
                white=tuple(bytes.fromhex(cfg["subtitle"]["text"]["defaultColorHex"].lstrip("#")))
                muted=tuple(bytes.fromhex(pal["secondaryTextColorHex"].lstrip("#")))
                episode_y=cfg["cardLayout"]["typography"]["episodeLabelYPx"]
                divider=cfg["cardLayout"]["dividerYPx"]
                bands=[(episode_y-5,episode_y+65,yellow),(episode_y+35,divider-60,white),(divider-110,divider-5,muted)]
                extents=[]
                for y0,y1,color in bands:
                    rows=[]
                    color_bytes=bytes(color)
                    for y in range(y0,y1):
                        row=rgb.crop((left,y,panel_right,y+1)).tobytes()
                        hits=sum(row[i:i+3]==color_bytes for i in range(0,len(row),3))
                        if hits>=5:rows.append(y)
                    assert rows, f"{path.name}: title band missing {color}"
                    extents.append((rows[0],rows[-1]))
                gap1=extents[1][0]-extents[0][1]-1
                gap2=extents[2][0]-extents[1][1]-1
                typ=cfg["cardLayout"]["typography"]
                target=typ["episodeToExpressionVisibleGapPx"]
                assert abs(gap1-gap2)<=typ["visibleGapEqualityTolerancePx"] and abs(gap1-target)<=typ["visibleGapTargetTolerancePx"], f"{path.name}: visible gaps {gap1}px/{gap2}px, target {target}px"
                gaps.append((gap1,gap2))
        check(report, "knowledge_cards.palette_and_spacing", "PASS", f"{len(paths)} card(s); colors and bounds match; visible title gaps {gaps}")
    except (AssertionError, ImportError, KeyError, OSError) as exc:
        check(report, "knowledge_cards.palette_and_spacing", "FAIL", str(exc))


def validate_replay_manifest(manifest, cfg, report):
    if not manifest or "knowledgePoints" not in manifest:
        check(report, "episode.replay_source_mapping", "SKIP", "No knowledge point mapping supplied")
        return
    try:
        clip = manifest["selectedClip"]
        length = clip["sourceEndSeconds"] - clip["sourceStartSeconds"]
        static_fields_complete = True
        for point in manifest["knowledgePoints"]:
            a = point["replayRelativeStartSeconds"]
            b = point["replayRelativeEndSeconds"]
            frame = point["cardFrameRelativeSeconds"]
            assert 0 <= a < b <= length + .001, point["id"]
            assert 0 <= frame <= length, point["id"]
            static_frame = point.get("staticCardFrameRelativeSeconds")
            if static_frame is None:
                static_fields_complete = False
            else:
                assert a <= static_frame <= b, f"{point['id']}: static frame must be inside replay window"
                assert point["staticCardFrameSource"] == "slowReplayAtHumanSelectedFreezeFrame", point["id"]
                assert point["renderedStaticTailHoldFile"], point["id"]
            assert point["highlightSpoken"] in point["spokenSentence"], point["id"]
            assert point["voiceAsset"], point["id"]
        check(report, "episode.replay_source_mapping", "PASS", f"{len(manifest['knowledgePoints'])} replay windows relative to selected clip start {clip['sourceStartSeconds']:.3f}s")
        reviewed = static_fields_complete and all(point.get("staticCardFrameHumanReviewed") is True for point in manifest["knowledgePoints"])
        check(report, "episode.static_frame_face_review", "PASS" if reviewed else "REVIEW_REQUIRED", "Natural, clear face frame approved for every knowledge card" if reviewed else "Review eyes, expression, clarity, and caption state on each selected frame")
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        check(report, "episode.replay_source_mapping", "FAIL", str(exc))


def validate_static_card_freeze(paths, manifest, cfg, report, ffmpeg):
    if not manifest or not manifest.get("knowledgePoints") or len(paths) != len(manifest["knowledgePoints"]):
        check(report, "knowledge_cards.static_frame_matches_replay", "REVIEW_REQUIRED", "One rendered card and slow replay mapping per knowledge point are required")
        return
    if not ffmpeg:
        check(report, "knowledge_cards.static_frame_matches_replay", "REVIEW_REQUIRED", "ffmpeg is required to decode slow replay end frames")
        return
    try:
        from PIL import Image, ImageChops, ImageStat
        rect = tuple(cfg["cardLayout"]["topVideoRectPx"])
        maes = []
        for card_path, point in zip(paths, manifest["knowledgePoints"]):
            slow_path = Path(point["renderedStaticTailHoldFile"])
            if not slow_path.is_absolute():
                slow_path = Path.cwd() / slow_path
            proc = subprocess.run(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-sseof", "-0.05", "-i", str(slow_path),
                 "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1"],
                capture_output=True, check=True
            )
            with Image.open(BytesIO(proc.stdout)) as im:
                end_frame = im.convert("RGB").crop(rect)
            with Image.open(card_path) as im:
                card_crop = im.convert("RGB").crop(rect)
            assert card_crop.size == end_frame.size, f"{point['id']}: card frame size mismatch"
            mae = sum(ImageStat.Stat(ImageChops.difference(card_crop, end_frame)).mean) / 3
            tolerance = cfg["cardLayout"]["staticTailFramePolicy"]["pixelMatchMaxMae"]
            assert mae <= tolerance, f"{point['id']}: top image differs from slow replay end frame (MAE {mae:.3f}, max {tolerance})"
            maes.append(round(mae, 3))
        check(report, "knowledge_cards.static_frame_matches_replay", "PASS", f"Top video crops match slow replay final frames; MAE {maes}")
    except (AssertionError, ImportError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        check(report, "knowledge_cards.static_frame_matches_replay", "FAIL", str(exc))


def main():
    parser = argparse.ArgumentParser()
    script_path = Path(__file__).resolve()
    installed_config = script_path.parents[1] / "config" / "series-params.json"
    adjacent_configs = sorted(script_path.parent.glob("english-vlog-series-params.v*.json"))
    default_config = installed_config if installed_config.exists() else (adjacent_configs[-1] if adjacent_configs else installed_config)
    parser.add_argument("--config", type=Path, default=default_config)
    parser.add_argument("--ass", type=Path)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--baseline-video", type=Path, help="Same video composition without subtitles, for pixel-level opacity checks")
    parser.add_argument("--watermark", type=Path, help="Fixed watermark PNG; inferred from config when omitted")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--summary-card", type=Path)
    parser.add_argument("--knowledge-card", type=Path, action="append", default=[], help="Rendered knowledge card PNG; repeat for each card")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--strict", action="store_true", help="Fail the delivery gate on warnings or required reviews")
    parser.add_argument("--final", action="store_true", help="Require all inputs for a complete final-video QA gate")
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    watermark_path = resolve_watermark(args.config, cfg, args.watermark)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest else None
    report = []
    validate_config(cfg, report)
    validate_watermark_asset(watermark_path, cfg, report)
    validate_transition_assets(args.config, cfg, report)
    if args.ass:
        validate_ass(args.ass, cfg, report)
    if args.video:
        ffmpeg = find_ffmpeg(args.ffmpeg)
        validate_video(args.video, cfg, report, ffmpeg, manifest)
        if manifest and manifest.get("videoRole") == "blindPreview":
            validate_blind_no_captions(args.video, args.baseline_video, cfg, manifest, report, ffmpeg)
        else:
            validate_rendered_opacity(args.video, args.baseline_video, cfg, manifest, report, ffmpeg)
        validate_rendered_watermark(args.video, args.baseline_video, watermark_path, cfg, manifest, report, ffmpeg)
    validate_manifest(cfg, manifest, report)
    validate_replay_manifest(manifest, cfg, report)
    validate_timeline(cfg, manifest, report)
    if args.summary_card:
        validate_summary_card(args.summary_card, cfg, report)
    if args.knowledge_card:
        validate_knowledge_card_palette(args.knowledge_card, cfg, report)
        validate_static_card_freeze(args.knowledge_card, manifest, cfg, report, find_ffmpeg(args.ffmpeg))
    if args.final:
        missing = [name for name, present in (("ASS", args.ass), ("video", args.video), ("baseline video", args.baseline_video), ("episode manifest", args.manifest)) if not present]
        if not manifest or not manifest.get("timeline"):
            missing.append("final timeline")
        check(report, "final.required_inputs", "FAIL" if missing else "PASS", ", ".join(missing) if missing else "All numeric QA inputs supplied")
    result = {"configVersion": cfg["configVersion"], "checks": report}
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(output + "\n", encoding="utf-8")
    print(output)
    if any(item["status"] == "FAIL" for item in report):
        raise SystemExit(1)
    if args.strict and any(item["status"] in ("WARN", "REVIEW_REQUIRED", "SKIP") for item in report):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
