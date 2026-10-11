#!/usr/bin/env python3
"""Local patches for the Agent Standup VS Code extension (written against 1.24.0).

Patches:
  unique-pool  A new sub-agent gets a random pool image no other agent in the session holds;
               once all are taken, a random image from the whole pool. (Stock: hash pick, often duplicated.)
  name-tags    Display names follow the bound image: sub-agents show "@ImageName",
               the lead and you show "Claude (@ImageName)" / "You (@ImageName)". Lead/you names
               come from characters/names.json, which set_character.py maintains.
  name-match   A sub-agent whose tile label (its task description) contains a pool image name gets
               that image, e.g. "@Nana — Orchestration Architect" -> Nana. Other sub-agents
               still get a random free image. Requires unique-pool and name-tags (it edits their code).

Extension updates overwrite patches; run `apply` again afterwards. If an update changed the
patched code, the patch is skipped rather than forced.

Usage:
  patch_extension.py status
  patch_extension.py apply  [unique-pool] [name-tags] [name-match]   (default: all)
  patch_extension.py revert [unique-pool] [name-tags] [name-match]   (default: all; dependents are reverted first)
"""
import argparse
import shutil
import sys
from pathlib import Path

PAGE, SERVER = "public/index.html", "server.js"

PATCHES = {
    "unique-pool": [
        (PAGE,
         "const customFor = (id) => (id === 'main' ? CHARS.lead : id === 'user' ? CHARS.you : CHARS.pool.length ? "
         "CHARS.pool.reduce((b, c) => (hash(id + '|' + (c.idle || '')) > hash(id + '|' + (b.idle || '')) ? c : b)) : null);",
         "/* agent-standup-characters: unique pool */ const customFor = (id) => {\n"
         "  if (id === 'main') return CHARS.lead; if (id === 'user') return CHARS.you; if (!CHARS.pool.length) return null;\n"
         "  const used = new Set(Object.entries(S.agents || {}).filter(([k, a]) => k !== id && a && a.custom).map(([, a]) => a.custom.name));\n"
         "  const free = CHARS.pool.filter((c) => !used.has(c.name)), from = free.length ? free : CHARS.pool;\n"
         "  return from[Math.floor(Math.random() * from.length)];\n"
         "};"),
        # Reload reassigns every agent: clear first so old picks don't count as "used".
        (PAGE,
         "for (const id in S.agents) S.agents[id].custom = customFor(id);",
         "for (const id in S.agents) S.agents[id].custom = null; for (const id in S.agents) S.agents[id].custom = customFor(id);"),
    ],
    "name-tags": [
        (PAGE,
         "function persona(a) { const p = persona0(a); p.custom = customFor(a.id); return p; }",
         "/* agent-standup-characters: name tags */\n"
         "const tagName = (p) => { const c = p.custom, b = p.baseName, own = p.id === 'main' || p.id === 'user';\n"
         "  p.name = !c ? b : own ? (c.label ? `${b} (@${c.label})` : b) : '@' + c.name; return p; };\n"
         "function persona(a) { const p = persona0(a); const own = a.id === 'main' || a.id === 'user';\n"
         "  p.baseName = own || a.baseName == null ? p.name : a.baseName;   // lead/you: fresh (localized) name; others keep their first name\n"
         "  p.custom = a.custom !== undefined ? a.custom : customFor(a.id);   // keep the bound image when a persona is rebuilt\n"
         "  return tagName(p); }"),
        (PAGE,
         "S.agents[id].custom = customFor(id); buildStage();",
         "S.agents[id].custom = customFor(id); for (const id in S.agents) tagName(S.agents[id]); buildStage();"),
        (PAGE,
         "const e = { name: c.stem, idle:",
         "const e = { name: c.stem, label: c.label || null, idle:"),
        (SERVER,
         "  return { dir, max: CHAR_MAX, chars };",
         "  /* agent-standup-characters: name tags */ let tags = {};\n"
         "  try { const nf = path.join(dir, 'names.json'); if (fs.lstatSync(nf).isFile()) tags = JSON.parse(fs.readFileSync(nf, 'utf8')) || {}; } catch {}\n"
         "  for (const c of chars) { const t = c.role !== 'agent' && tags[c.role];\n"
         "    try { if (t && typeof t.name === 'string' && t.file === c.file && t.size === fs.lstatSync(path.join(dir, c.file)).size) c.label = t.name.slice(0, 60); } catch {} }\n"
         "  return { dir, max: CHAR_MAX, chars };"),
    ],
    "name-match": [
        (PAGE,
         "const customFor = (id) => {\n"
         "  if (id === 'main') return CHARS.lead; if (id === 'user') return CHARS.you; if (!CHARS.pool.length) return null;\n",
         "const customFor = (id, role) => {\n"
         "  if (id === 'main') return CHARS.lead; if (id === 'user') return CHARS.you; if (!CHARS.pool.length) return null;\n"
         "  /* agent-standup-characters: name match */ const named = nameMatch(role != null ? role : S.agents && S.agents[id] && (S.agents[id].roleEn || S.agents[id].role)); if (named) return named;\n"),
        (PAGE,
         "a.custom : customFor(a.id);",
         "a.custom : customFor(a.id, a.roleEn || a.role);"),
        (PAGE,
         "function renderCharInfo() {",
         "/* agent-standup-characters: name match */ function nameMatch(label) {   // longest pool name found in the tile label wins\n"
         "  const l = String(label || '').toLowerCase(); if (!l) return null;\n"
         "  return CHARS.pool.filter((c) => l.includes(c.name.toLowerCase())).sort((x, y) => y.name.length - x.name.length)[0] || null;\n"
         "}\n"
         "function renderCharInfo() {"),
    ],
}
ORDER = list(PATCHES)
REQUIRES = {"name-match": ["unique-pool", "name-tags"]}   # these edit text the required patches introduced


def extensions():
    roots = [Path.home() / d for d in (".vscode/extensions", ".vscode-insiders/extensions", ".cursor/extensions", ".windsurf/extensions")]
    return sorted(p for r in roots if r.is_dir() for p in r.glob("doublegeste.agent-standup-*") if (p / PAGE).is_file())


def read(ext):
    return {f: (ext / f).read_text(encoding="utf-8") for f in (PAGE, SERVER)}


def is_applied(files, name):
    return all(files[f].count(new) == 1 for f, _, new in PATCHES[name])


def undo(files, name):
    for f, old, new in reversed(PATCHES[name]):
        files[f] = files[f].replace(new, old, 1)


def state(ext, name):
    missing = [r for r in REQUIRES.get(name, []) if state(ext, r) != "applied"]
    if missing:
        return f"not applied (needs {', '.join(missing)})"
    files = read(ext)
    for later in reversed(ORDER[ORDER.index(name) + 1:]):   # look past patches layered on top of this one
        if name in REQUIRES.get(later, []) and is_applied(files, later):
            undo(files, later)
    if is_applied(files, name):
        return "applied"
    if all(files[f].count(old) == 1 for f, old, _ in PATCHES[name]):
        return "not applied"
    return "unknown (code differs from 1.24.0)"


def apply(ext, name):
    st = state(ext, name)
    if st != "not applied":
        return "already applied" if st == "applied" else f"SKIPPED: {st}"
    files = read(ext)
    for f, old, new in PATCHES[name]:
        orig = ext / (f + ".orig")
        if not orig.exists():
            shutil.copy2(ext / f, orig)   # pristine copy, taken before the first patch touches the file
        files[f] = files[f].replace(old, new, 1)
    for f, text in files.items():
        (ext / f).write_text(text, encoding="utf-8")
    return "applied"


def revert(ext, name):
    st = state(ext, name)
    if st != "applied":
        return "not applied" if st.startswith("not applied") else f"SKIPPED: {st}"
    notes = []
    for dep in reversed(ORDER):
        if name in REQUIRES.get(dep, []) and state(ext, dep) == "applied":
            notes.append(f"{dep} {revert(ext, dep)} first")
    files = read(ext)
    undo(files, name)
    for f, text in files.items():
        (ext / f).write_text(text, encoding="utf-8")
    return "reverted" + (f" ({'; '.join(notes)})" if notes else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["status", "apply", "revert"])
    ap.add_argument("patches", nargs="*", choices=[[], *PATCHES], metavar="patch")
    args = ap.parse_args()
    exts = extensions()
    if not exts:
        sys.exit("Agent Standup extension not found")
    fn = {"apply": apply, "revert": revert, "status": state}[args.action]
    names = [n for n in ORDER if n in (args.patches or ORDER)]
    for ext in exts:
        for name in reversed(names) if args.action == "revert" else names:
            print(f"{ext.name}  {name:12} {fn(ext, name)}")
    if args.action != "status":
        print("Then run 'Developer: Reload Window' in VS Code (restarts the extension's server and page).")


if __name__ == "__main__":
    main()
