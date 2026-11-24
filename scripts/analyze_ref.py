#!/usr/bin/env python3
"""Analyze reference videos so Claude can derive an editing style.

Usage:
  python scripts/analyze_ref.py refs/*.mp4 [--no-transcribe]

For each video writes work/refs/<name>/:
  sheet.jpg     contact sheet (24 frames, evenly spaced) to look at layout, captions, colors
  summary.json  duration, resolution, cut times, average shot length, speech rate
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edit import WORK, load_style, probe  # noqa: E402


def scene_cuts(path, threshold=0.3):
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-an",
         "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True)
    return [round(float(t), 2) for t in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]


def contact_sheet(path, duration, out, cols=6, rows=4):
    n = cols * rows
    fps = n / max(duration, 0.1)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(path),
         "-vf", f"fps={fps},scale=270:-2,tile={cols}x{rows}", "-frames:v", "1", str(out)],
        check=True)


def analyze(path, do_transcribe):
    out_dir = WORK / "refs" / path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    info = probe(path)
    cuts = scene_cuts(path)
    shots = len(cuts) + 1
    summary = {
        "file": str(path),
        "duration": round(info["duration"], 2),
        "resolution": f"{info['width']}x{info['height']}",
        "has_audio": info["has_audio"],
        "cuts": cuts,
        "shots": shots,
        "avg_shot_seconds": round(info["duration"] / shots, 2),
    }
    contact_sheet(path, info["duration"], out_dir / "sheet.jpg")

    if do_transcribe and info["has_audio"]:
        from edit import transcribe
        tjson = transcribe(path, load_style(), out_dir / "transcript.json")
        words = json.loads(tjson.read_text(encoding="utf-8"))["words"]
        if words:
            spoken = words[-1]["end"] - words[0]["start"]
            chars = sum(len(w["word"]) for w in words)
            summary["chars_per_second"] = round(chars / max(spoken, 0.1), 2)
            summary["first_words"] = " ".join(w["word"] for w in words[:30])

    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{path.name}: {summary['duration']}s, {shots} shots, "
          f"avg {summary['avg_shot_seconds']}s/shot -> {out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--no-transcribe", action="store_true")
    args = ap.parse_args()
    for v in args.videos:
        analyze(Path(v), not args.no_transcribe)


if __name__ == "__main__":
    main()
