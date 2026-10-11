#!/usr/bin/env python3
"""Assign Agent Standup character images to the lead (Claude) or you (the human).

Agent Standup (VS Code extension) reads ~/.agent-standup/characters/:
  lead.* / claude.*        -> the lead
  you.* / human.* / user.* -> the human
  any other image          -> pool for sub-agents (picked by hash of agent id, not by name)
  NAME-talk.*              -> optional open-mouth frame of NAME.*
Files over 300 KB are silently ignored, so everything written here is WebP <= 300 KB.

Usage:
  set_character.py list
  set_character.py set lead|you NAME [--keep-in-pool]
  set_character.py reset lead|you
"""
import argparse
import io
import json
import os
import shutil
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path.home() / ".agent-standup"
CHARS = Path(os.environ.get("AGENT_STANDUP_CHARACTERS", ROOT / "characters"))
LIBRARY = CHARS.parent / "library"      # characters taken out of the sub-agent pool
BACKUPS = CHARS.parent / "originals"    # replaced lead/you files
EXTS = {".png", ".gif", ".webp", ".jpg", ".jpeg"}
MAX_BYTES = 300 * 1024
MAX_SIDE = 512
ROLE_STEMS = {"lead": {"lead", "claude"}, "you": {"you", "human", "user"}}
RESERVED = set().union(*ROLE_STEMS.values())


def images(folder):
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTS)


def find(name):
    """Return (idle, talk) paths for a character NAME, searching the characters folder then the library."""
    key = name.lower().removesuffix("-talk")
    for folder in (CHARS, LIBRARY):
        files = {p.stem.lower(): p for p in images(folder)}
        if key in files:
            return files[key], files.get(key + "-talk")
    return None, None


def to_webp(src, dst):
    """Write src as a WebP no larger than MAX_SIDE px and MAX_BYTES, keeping transparency."""
    im = Image.open(src)
    im = im.convert("RGBA")
    if max(im.size) > MAX_SIDE:
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    for quality in (90, 80, 70, 60, 50):
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=quality, method=6, alpha_quality=100)
        if buf.tell() <= MAX_BYTES:
            dst.write_bytes(buf.getvalue())
            return
        im.thumbnail((im.width * 3 // 4, im.height * 3 // 4), Image.LANCZOS)
    sys.exit(f"Could not get {src.name} under 300 KB")


def record_name(role, name):
    """Remember which character a role file came from (characters/names.json, read by the name-tags patch)."""
    path = CHARS / "names.json"
    try:
        names = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        names = {}
    if name:
        f = CHARS / f"{role}.webp"
        names[role] = {"name": name, "file": f.name, "size": f.stat().st_size}
    else:
        names.pop(role, None)
    path.write_text(json.dumps(names, indent=2) + "\n", encoding="utf-8")


def clear_role(role):
    """Move the current lead/you files (any accepted stem or extension) into a timestamped backup."""
    stems = ROLE_STEMS[role] | {s + "-talk" for s in ROLE_STEMS[role]}
    current = [p for p in images(CHARS) if p.stem.lower() in stems]
    if current:
        dest = BACKUPS / f"{role}-{time.strftime('%Y%m%d-%H%M%S')}"
        dest.mkdir(parents=True, exist_ok=True)
        for p in current:
            shutil.move(str(p), dest / p.name)
        print(f"Backed up old {role} images to {dest}")
    record_name(role, None)


def cmd_list(_):
    print(f"Characters folder: {CHARS}")
    for role, stems in ROLE_STEMS.items():
        hit = [p.name for p in images(CHARS) if p.stem.lower() in stems]
        print(f"  {role:5}: {', '.join(hit) or '(default drawing)'}")
    for label, folder in (("Sub-agent pool", CHARS), ("Library (not in pool)", LIBRARY)):
        rows = [p for p in images(folder)
                if not p.stem.lower().endswith("-talk") and p.stem.lower() not in RESERVED]
        if not rows and folder == LIBRARY:
            continue
        print(f"{label}:")
        for p in rows or []:
            _, talk = find(p.stem)
            big = [q.name for q in (p, talk) if q and q.parent == CHARS and q.stat().st_size > MAX_BYTES]
            note = f"  !! over 300 KB, ignored by Agent Standup: {', '.join(big)}" if big else ""
            print(f"  {p.stem}{'  (+talk)' if talk else ''}{note}")
        if not rows:
            print("  (none)")


def cmd_set(args):
    idle, talk = find(args.name)
    if not idle:
        sys.exit(f"No character named '{args.name}'. Run: set_character.py list")
    if idle.stem.lower() in RESERVED:
        sys.exit(f"'{idle.name}' is already a role file; pick a named character.")
    clear_role(args.role)
    to_webp(idle, CHARS / f"{args.role}.webp")
    if talk:
        to_webp(talk, CHARS / f"{args.role}-talk.webp")
    record_name(args.role, idle.stem)
    print(f"{args.role} is now {idle.stem}" + (" (with talk frame)" if talk else " (no talk frame found)"))
    if not args.keep_in_pool and idle.parent == CHARS:
        LIBRARY.mkdir(parents=True, exist_ok=True)
        for p in (idle, talk):
            if p:
                shutil.move(str(p), LIBRARY / p.name)
        print(f"Moved {idle.stem} out of the sub-agent pool into {LIBRARY}")
    print("Press Reload in Agent Standup's settings menu to see the change.")


def cmd_reset(args):
    clear_role(args.role)
    print(f"{args.role} is back to the default drawing. Press Reload in Agent Standup.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    s = sub.add_parser("set")
    s.add_argument("role", choices=ROLE_STEMS)
    s.add_argument("name")
    s.add_argument("--keep-in-pool", action="store_true", help="also leave the character in the sub-agent pool")
    s.set_defaults(fn=cmd_set)
    r = sub.add_parser("reset")
    r.add_argument("role", choices=ROLE_STEMS)
    r.set_defaults(fn=cmd_reset)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
