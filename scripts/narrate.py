#!/usr/bin/env python3
"""Make per-scene narration from a script.json and write timing for Remotion.

Usage:
  python scripts/narrate.py motion/src/milmyeon/script.json

Writes motion/public/<id>/<scene>.mp3 and motion/src/<id>/timing.json:
  {"fps": 30, "scenes": [{"id", "label", "text", "audio", "from", "frames",
                          "captions": [{"text", "from", "to"}]}], "total": N}
Caption chunks are timed by character count within each scene's narration.
Put "|" in a scene's text to choose caption breaks yourself (it is not spoken).
Replace any <scene>.mp3 with your own recording and rerun with --keep-audio.
"""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 30


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True,
                         check=True).stdout
    return float(out)


def tts(text, out, voice):
    from gtts import gTTS
    tmp = out.with_suffix(".raw.mp3")
    gTTS(text, lang=voice.get("lang", "ko")).save(str(tmp))
    # speed up a little and trim leading/trailing silence
    af = (f"atempo={voice.get('tempo', 1.0)},"
          "silenceremove=start_periods=1:start_threshold=-45dB,"
          "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp), "-af", af,
                    "-ar", "44100", str(out)], check=True)
    tmp.unlink()


def split_caption(text, max_chars=16):
    """Split narration into caption chunks at punctuation, then by length."""
    pieces, cur = [], ""
    for token in text.replace(",", ", ").replace(".", ". ").split():
        if cur and len(cur) + 1 + len(token) > max_chars:
            pieces.append(cur)
            cur = token
        else:
            cur = f"{cur} {token}".strip()
        if token.endswith((".", ",", "?", "!")) and len(cur) >= 4:
            pieces.append(cur)
            cur = ""
    if cur:
        pieces.append(cur)
    return [p.rstrip(".,") for p in pieces]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--keep-audio", action="store_true", help="reuse existing mp3 files")
    args = ap.parse_args()

    script_path = Path(args.script)
    script = json.loads(script_path.read_text(encoding="utf-8"))
    pid = script["id"]
    audio_dir = ROOT / "motion" / "public" / pid
    audio_dir.mkdir(parents=True, exist_ok=True)
    gap = script.get("gap", 0.3)

    scenes, cursor = [], 0
    for sc in script["scenes"]:
        mp3 = audio_dir / f"{sc['id']}.mp3"
        # "|" in the text marks caption breaks; it is not spoken
        spoken = " ".join(sc["text"].replace("|", " ").split())
        if not (args.keep_audio and mp3.exists()):
            tts(spoken, mp3, script.get("voice", {}))
        dur = duration(mp3)
        frames = round((dur + gap) * FPS)
        if "|" in sc["text"]:
            chunks = [c.strip().rstrip(".,") for c in sc["text"].split("|") if c.strip()]
        else:
            chunks = split_caption(spoken)
        sc = {**sc, "text": spoken}
        total_chars = sum(len(c) for c in chunks)
        caps, t = [], 0.0
        for c in chunks:
            span = dur * len(c) / total_chars
            caps.append({"text": c, "from": round(t * FPS), "to": round((t + span) * FPS)})
            t += span
        scenes.append({**sc, "audio": f"{pid}/{mp3.name}", "from": cursor,
                       "frames": frames, "captions": caps})
        print(f"{sc['id']:10s} {dur:5.2f}s  {len(chunks)} captions")
        cursor += frames

    timing = {"fps": FPS, "scenes": scenes, "total": cursor}
    out = script_path.with_name("timing.json")
    out.write_text(json.dumps(timing, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"total {cursor / FPS:.1f}s -> {out}")


if __name__ == "__main__":
    main()
