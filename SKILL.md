---
name: agent-standup-characters
description: Use when the user wants to change, swap, set or reset which picture Agent Standup (the VS Code extension showing Claude Code sessions as a video call) uses for the lead (Claude) or for "you" (the human), or asks which character images are available in ~/.agent-standup/characters.
---

# Agent Standup characters: lead and you

## Overview
Agent Standup assigns pictures by **file name** in `~/.agent-standup/characters/`:

| File | Shows as |
|---|---|
| `lead.*` or `claude.*` | the lead (Claude) |
| `you.*`, `human.*` or `user.*` | the human |
| any other image | the sub-agent pool, picked by a hash of the agent's ID, **never by name** |
| `NAME-talk.*` | open-mouth frame of `NAME.*` |

Accepted formats are PNG, WebP, GIF and JPG. **Files over 300 KB are silently ignored**, and the default drawing shows instead.

## Script
`scripts/set_character.py` (next to this file) handles the details:

```bash
S=~/.claude/skills/agent-standup-characters/scripts/set_character.py
python3 $S list            # current lead/you, the pool, the library, oversized files
python3 $S set lead Nana   # Nana (+ Nana-talk) becomes the lead
python3 $S set you Nono    # ...becomes you
python3 $S reset lead      # back to the default drawing
```

What `set` does:
- writes `ROLE.webp` and `ROLE-talk.webp`, at most 512 px and under 300 KB
- moves the old role files to `~/.agent-standup/originals/ROLE-<timestamp>/`, never deleting them
- moves the chosen character out of the sub-agent pool into `~/.agent-standup/library/` so it doesn't also appear as a sub-agent; `--keep-in-pool` leaves it there
- matches names without regard to case, and also searches the library, so earlier choices can be picked again

## Extension patches
`scripts/patch_extension.py status|apply|revert [unique-pool] [name-tags] [name-match]` patches the installed extension (written against 1.24.0):
- **unique-pool:** a new sub-agent gets a random image no other agent in the session holds, then a random image from the whole pool once all are taken. Duplicates are unavoidable when a session has more sub-agents than images.
- **name-tags:** sub-agents are shown as `@ImageName`, and the lead and you as `Claude (@ImageName)` and `You (@ImageName)`. Lead and you names come from `characters/names.json`, which `set` writes. A lead or you image placed by hand shows no tag.
- **name-match:** a sub-agent whose tile label (the `Agent` task description) contains a pool image name gets that image, e.g. description `@Nana — Orchestration Architect` → Nana. Others still get a random free image. It builds on the other two: `apply` refuses without them, and reverting either reverts name-match first.

Extension updates remove the patches, so run `apply` again after one. Afterwards, run **Developer: Reload Window** in VS Code.

## Steps
1. Run `list` and show the user the choices if they didn't name one.
2. Run `set`, then tell the user to press **Reload** in Agent Standup's ⚙ menu.

## Common mistakes
- Assigning a sub-agent picture to a specific agent by naming the file after it. The pool is hash-based, so this doesn't work.
- Leaving an image over 300 KB in the folder. It's ignored without any warning; `list` flags these.
- Keeping two lead files, such as `lead.png` and `claude.webp`. Only one wins, and you can't predict which. `set` clears all role variants.
