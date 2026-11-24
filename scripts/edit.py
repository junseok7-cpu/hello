#!/usr/bin/env python3
"""Reels editing pipeline: transcribe -> cut pauses -> captions -> check version.

Usage:
  python scripts/edit.py transcribe raw/clip.mp4
  python scripts/edit.py cut        raw/clip.mp4
  python scripts/edit.py captions   raw/clip.mp4
  python scripts/edit.py check      raw/clip.mp4     # all three, writes output/<name>_check.mp4

Intermediate files go to work/<name>/. Caption and cut settings come from style.json.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
OUTPUT = ROOT / "output"
FONTS = ROOT / "assets" / "fonts"
STYLE_FILE = ROOT / "style.json"

DEFAULT_STYLE = {
    "cut": {"max_gap": 0.35, "pad_before": 0.08, "pad_after": 0.12},
    "captions": {
        "font": "Pretendard",
        "font_size_ratio": 0.045,   # font size as a fraction of video height
        "color": "#FFFFFF",
        "outline_color": "#000000",
        "outline": 6,
        "shadow": 0,
        "position": "lower",        # lower | center | upper
        "margin_ratio": 0.22,       # distance from the edge as a fraction of height
        "max_chars": 14,            # characters per caption chunk
        "highlight_color": None,    # e.g. "#FFE14D" to color the word being spoken
    },
    "whisper": {"model": "small", "language": "ko"},
}


def load_style():
    style = json.loads(json.dumps(DEFAULT_STYLE))
    if STYLE_FILE.exists():
        user = json.loads(STYLE_FILE.read_text(encoding="utf-8"))
        for section, values in user.items():
            if isinstance(values, dict) and section in style:
                style[section].update(values)
            else:
                style[section] = values
    return style


def run(cmd):
    print("$", " ".join(str(c) for c in cmd), file=sys.stderr)
    subprocess.run([str(c) for c in cmd], check=True)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    has_audio = any(s["codec_type"] == "audio" for s in data["streams"])
    return {
        "duration": float(data["format"]["duration"]),
        "width": video["width"] if video else None,
        "height": video["height"] if video else None,
        "has_audio": has_audio,
    }


def workdir(src):
    d = WORK / Path(src).stem
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- transcribe
def load_audio(src, sr=16000):
    """Decode audio with ffmpeg (avoids PyAV version issues in faster-whisper)."""
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(sr),
         "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def transcribe(src, style, out_json=None):
    from faster_whisper import WhisperModel

    out_json = Path(out_json or workdir(src) / "transcript.json")
    cfg = style["whisper"]
    model = WhisperModel(cfg["model"], device="cpu", compute_type="int8")
    segments, info = model.transcribe(load_audio(src), language=cfg.get("language"),
                                      word_timestamps=True, vad_filter=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"start": round(w.start, 3), "end": round(w.end, 3),
                          "word": w.word.strip()})
    out_json.write_text(json.dumps({"language": info.language, "words": words},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"transcript: {len(words)} words -> {out_json}", file=sys.stderr)
    return out_json


# ----------------------------------------------------------------------- cut
def keep_ranges(words, duration, max_gap, pad_before, pad_after):
    """Merge spoken words into ranges, dropping silences longer than max_gap."""
    ranges = []
    for w in words:
        s, e = max(0.0, w["start"] - pad_before), min(duration, w["end"] + pad_after)
        if ranges and s - ranges[-1][1] <= max_gap:
            ranges[-1][1] = max(ranges[-1][1], e)
        else:
            ranges.append([s, e])
    return [(round(s, 3), round(e, 3)) for s, e in ranges]


def remap(t, ranges):
    """Map a time in the source to the cut timeline (None if it was cut out)."""
    offset = 0.0
    for s, e in ranges:
        if s <= t <= e:
            return offset + (t - s)
        offset += e - s
    return None


def cut(src, style):
    wd = workdir(src)
    tjson = wd / "transcript.json"
    if not tjson.exists():
        transcribe(src, style, tjson)
    words = json.loads(tjson.read_text(encoding="utf-8"))["words"]
    info = probe(src)
    c = style["cut"]
    ranges = keep_ranges(words, info["duration"], c["max_gap"], c["pad_before"], c["pad_after"])
    if not ranges:
        raise SystemExit("no speech found; nothing to keep")

    expr = "+".join(f"between(t,{s},{e})" for s, e in ranges)
    vf = f"select='{expr}',setpts=N/FRAME_RATE/TB"
    af = f"aselect='{expr}',asetpts=N/SR/TB"
    out = wd / "cut.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", vf, "-af", af,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", out])

    cut_words = []
    for w in words:
        s, e = remap(w["start"], ranges), remap(w["end"], ranges)
        if s is not None and e is not None:
            cut_words.append({**w, "start": round(s, 3), "end": round(e, 3)})
    kept = sum(e - s for s, e in ranges)
    (wd / "cut.json").write_text(json.dumps(
        {"ranges": ranges, "original": info["duration"], "kept": round(kept, 3),
         "words": cut_words}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cut: {info['duration']:.1f}s -> {kept:.1f}s ({len(ranges)} pieces) -> {out}",
          file=sys.stderr)
    return out


# ------------------------------------------------------------------ captions
def ass_color(hex_color, alpha=0):
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t):
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def chunk_words(words, max_chars, max_pause=0.6):
    chunks, cur = [], []
    for w in words:
        text_len = sum(len(x["word"]) + 1 for x in cur) + len(w["word"])
        if cur and (text_len > max_chars or w["start"] - cur[-1]["end"] > max_pause):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(words, width, height, cs):
    size = round(height * cs["font_size_ratio"])
    margin = round(height * cs["margin_ratio"])
    align = {"lower": 2, "center": 5, "upper": 8}[cs["position"]]
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{cs['font']},{size},{ass_color(cs['color'])},&H000000FF,{ass_color(cs['outline_color'])},&H80000000,-1,0,0,0,100,100,0,0,1,{cs['outline']},{cs['shadow']},{align},60,60,{margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    hl = cs.get("highlight_color")
    for chunk in chunk_words(words, cs["max_chars"]):
        start, end = chunk[0]["start"], chunk[-1]["end"]
        if not hl:
            text = " ".join(w["word"] for w in chunk)
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{text}")
            continue
        # one event per word, coloring the word being spoken
        for i, w in enumerate(chunk):
            w_end = chunk[i + 1]["start"] if i + 1 < len(chunk) else end
            parts = [
                (f"{{\\c{ass_color(hl)}}}{x['word']}{{\\c{ass_color(cs['color'])}}}"
                 if j == i else x["word"])
                for j, x in enumerate(chunk)
            ]
            lines.append(f"Dialogue: 0,{ass_time(w['start'])},{ass_time(w_end)},Cap,,0,0,0,,"
                         + " ".join(parts))
    return header + "\n".join(lines) + "\n"


def captions(src, style, video=None, words_json=None, out=None):
    wd = workdir(src)
    video = Path(video or wd / "cut.mp4")
    words_json = Path(words_json or wd / "cut.json")
    if not video.exists() or not words_json.exists():
        cut(src, style)
    words = json.loads(words_json.read_text(encoding="utf-8"))["words"]
    info = probe(video)
    ass = wd / "captions.ass"
    ass.write_text(build_ass(words, info["width"], info["height"], style["captions"]),
                   encoding="utf-8")
    OUTPUT.mkdir(exist_ok=True)
    out = Path(out or OUTPUT / f"{Path(src).stem}_check.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-i", video,
         "-vf", f"subtitles={ass}:fontsdir={FONTS}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", out])
    print(f"captions -> {out}", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["transcribe", "cut", "captions", "check"])
    ap.add_argument("src", help="raw video, e.g. raw/clip.mp4")
    args = ap.parse_args()
    style = load_style()
    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"not found: {src}")
    if args.command == "transcribe":
        transcribe(src, style)
    elif args.command == "cut":
        cut(src, style)
    elif args.command == "captions":
        captions(src, style)
    else:
        transcribe(src, style)
        cut(src, style)
        print(captions(src, style))


if __name__ == "__main__":
    main()
