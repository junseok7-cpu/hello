#!/usr/bin/env python3
"""Re-time caption chunks in a timing.json to the spoken words (faster-whisper word timestamps).

Usage: python scripts/align.py motion/src/<id>/timing.json [--replace "열두 개=12개"] [--only <scene>]
Run after narrate.py. Chunks keep their text; only from/to move.
"""
import argparse, json, re, subprocess
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent.parent


def load(mp3):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-ar", "16000", "-ac", "1",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def norm(s):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timing")
    ap.add_argument("--replace", action="append", default=[], help="caption text a=b")
    ap.add_argument("--only", action="append", default=[], help="scene id(s) to align; others keep their timing")
    a = ap.parse_args()
    path = Path(a.timing)
    t = json.loads(path.read_text(encoding="utf-8"))
    fps = t["fps"]
    model = WhisperModel("small", compute_type="int8")
    for sc in t["scenes"]:
        if a.only and sc["id"] not in a.only:
            continue
        segs, _ = model.transcribe(load(ROOT / "motion/public" / sc["audio"]), language="ko",
                                   word_timestamps=True)
        words = [w for s in segs for w in s.words]
        # character position (normalized) -> time of the word holding it
        starts, ends, pos = [], [], 0
        for w in words:
            n = len(norm(w.word))
            starts.append((pos, w.start)); pos += n; ends.append((pos, w.end))
        heard = pos
        caps = sc["captions"]
        total = sum(len(norm(c["text"])) for c in caps) or 1
        cur = 0
        for c in caps:
            n = len(norm(c["text"]))
            p0 = cur / total * heard; p1 = (cur + n) / total * heard
            s0 = min(starts, key=lambda x: abs(x[0] - p0))[1] if starts else 0
            e1 = min(ends, key=lambda x: abs(x[0] - p1))[1] if ends else 0
            c["from"], c["to"] = round(s0 * fps), max(round(e1 * fps), round(s0 * fps) + 6)
            cur += n
        caps[0]["from"] = 0
        for r in a.replace:
            k, v = r.split("=", 1)
            for c in caps:
                c["text"] = c["text"].replace(k, v)
        print(sc["id"], [(c["text"], c["from"]) for c in caps])
    path.write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
