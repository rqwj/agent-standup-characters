# agent-standup-characters

A [Claude Code](https://claude.com/claude-code) skill for choosing the pixel-art characters in [Agent Standup](https://github.com/Atoll92/agent-standup), the VS Code extension that shows your Claude Code session as a live video call.

With this skill you can say *"make Nono the lead"* or *"which characters do I have?"* and Claude does the file juggling for you. It also comes with optional patches for the installed extension:

- every sub-agent gets its own picture
- tiles show the character's name (`@Nana`)
- a sub-agent can get a picture chosen by name

## Contents

```
SKILL.md                     instructions Claude reads when the skill triggers
scripts/set_character.py     choose / reset the lead and "you" pictures, list what you have
scripts/patch_extension.py   apply / revert / check the optional extension patches
```

## Requirements

- Claude Code (for the skill). Both scripts also run fine on their own.
- Python 3.9 or newer
- [Pillow](https://pypi.org/project/pillow/), used by `set_character.py` to convert and shrink images: `pip install pillow`
- The Agent Standup extension, for the patches. They target version **1.24.0** in VS Code, VS Code Insiders, Cursor or Windsurf.

## Install

Clone the repo straight into your Claude Code skills folder:

```bash
git clone https://github.com/rqwj/agent-standup-characters.git ~/.claude/skills/agent-standup-characters
```

Start a new Claude Code session (or run `/clear`) and the skill becomes available. To update it later:

```bash
git -C ~/.claude/skills/agent-standup-characters pull
```

## How Agent Standup picks pictures

Agent Standup reads images from `~/.agent-standup/characters/`. The setting `agentStandup.charactersPath` changes the folder, and this skill's scripts follow the `AGENT_STANDUP_CHARACTERS` environment variable instead. Each file's role comes from its **name**:

| File | Shows as |
|---|---|
| `lead.*` or `claude.*` | the lead (Claude) |
| `you.*`, `human.*` or `user.*` | you, the human |
| any other image | the sub-agent pool |
| `NAME-talk.*` | the open-mouth frame of `NAME.*`, shown while that character speaks |

Accepted formats are PNG, WebP, GIF and JPG. **Files over 300 KB are ignored without any warning**, and the default drawing shows instead. Without the patches below, each sub-agent's picture is chosen from a hash of the agent's ID: two sub-agents can get the same one, and naming a file after an agent has no effect.

After any change, press **Reload** in Agent Standup's ⚙ menu.

## Using it through Claude

The skill triggers when you ask about the lead or "you" picture, for example:

- "Which Agent Standup characters do I have?"
- "Make Nana the lead."
- "Use Nono for me."
- "Put the default drawing back for the lead."

Claude runs `set_character.py list` to show your options, then `set` or `reset`, and reminds you to press Reload.

## `set_character.py`

```bash
S=~/.claude/skills/agent-standup-characters/scripts/set_character.py

python3 $S list                           # current lead/you, the sub-agent pool, the library, oversized files
python3 $S set lead Nana                  # Nana (and Nana-talk) becomes the lead
python3 $S set you Nono                   # Nono becomes you
python3 $S set lead Lulu --keep-in-pool   # ...and stays in the sub-agent pool too
python3 $S reset lead                     # back to the default drawing
```

### `list`

Shows the characters folder, what the lead and you currently use, every character in the sub-agent pool (with `(+talk)` when it has a talk frame), and the library (see below). Any file over 300 KB that Agent Standup would ignore is flagged with `!!`.

### `set lead|you NAME`

1. **Finds** `NAME` in the characters folder, then in the library. The match ignores case, and `NAME-talk` is found automatically.
2. **Backs up** the current role files (`lead.*`, `claude.*`, `lead-talk.*`, …, whichever exist) to `~/.agent-standup/originals/<role>-<timestamp>/`. Nothing is ever deleted.
3. **Writes** `<role>.webp` and `<role>-talk.webp`, scaled to at most 512 px and compressed under 300 KB with transparency kept, so they're never too big to load.
4. **Records** the character's name in `characters/names.json`. The `name-tags` patch reads it to show `Claude (@Nana)`.
5. **Moves** the original `NAME` images out of the pool into `~/.agent-standup/library/`, so the same character doesn't also appear as a sub-agent. `--keep-in-pool` skips this step. Characters in the library can still be picked later with `set`.

### `reset lead|you`

Backs up the role files the same way, and removes the name from `names.json`. Agent Standup then shows its default drawing.

### Folder layout

```
~/.agent-standup/
├── characters/      what Agent Standup reads: lead, you, the sub-agent pool, names.json
├── library/         characters taken out of the pool by `set` (still pickable)
└── originals/       timestamped backups of replaced lead/you files
```

## `patch_extension.py`: optional extension patches

These patches edit the **installed** extension in place (`public/index.html` and `server.js`). Before the first change, the script saves an untouched copy of each file as `*.orig`.

```bash
P=~/.claude/skills/agent-standup-characters/scripts/patch_extension.py

python3 $P status              # state of each patch, for each installed copy
python3 $P apply               # apply all three
python3 $P apply unique-pool   # or only some
python3 $P revert name-match   # undo one
python3 $P revert              # undo all
```

After `apply` or `revert`, run **Developer: Reload Window** in VS Code so the extension's server and page restart.

| Patch | What it does |
|---|---|
| `unique-pool` | A new sub-agent gets a random picture that no other agent on the call holds. Pictures repeat only once every one is taken. Reload reassigns everyone. |
| `name-tags` | Tiles show whose picture it is: sub-agents appear as `@ImageName`, and the lead and you as `Claude (@ImageName)` and `You (@ImageName)`. The lead and you names come from `names.json`, which `set` writes; a lead or you picture you placed by hand shows no tag. |
| `name-match` | A sub-agent whose label (the description of its `Agent` task) contains a pool image's name gets that image. For example, `@Nana — Orchestration Architect` → `Nana.webp`. The longest matching name wins, and other sub-agents still get a random free picture. **It requires `unique-pool` and `name-tags`**: `apply` refuses without them, and reverting either one reverts `name-match` first. |

With all three applied, you can cast a multi-agent session, such as a panel discussion. Put `Nana.webp`, `Momo.webp`, … in the pool and launch sub-agents with descriptions `@Nana`, `@Momo`, …. Each one joins the call with its own face and name.

### Status values

| Status | Meaning |
|---|---|
| `applied` | the patch is in place |
| `not applied` | the extension's original code is there and the patch can be applied |
| `not applied (needs …)` | a required patch is missing |
| `unknown (code differs from 1.24.0)` | the extension's code changed, so the patch is skipped rather than forced |

### Extension updates

Updating Agent Standup replaces its files, which removes the patches. Run `apply` again afterwards. If the new version changed the code a patch edits, the patch shows `SKIPPED: unknown …` and nothing is touched.

To get back the exact original files, restore the `.orig` copies, or simply reinstall the extension.

## Common mistakes

- **Naming a pool image after an agent without `name-match`.** The stock extension picks sub-agent pictures by hash, so the name doesn't matter.
- **Images over 300 KB.** Agent Standup ignores them without a warning. `list` flags them, and `set` always writes files small enough.
- **Two lead files**, such as `lead.png` and `claude.webp`. Only one wins, and you can't tell which. `set` and `reset` clear every variant of the role.
- **Forgetting to reload.** Pictures need **Reload** in the ⚙ menu, and patches need **Developer: Reload Window**.

## Related

- Agent Standup: <https://github.com/Atoll92/agent-standup>. Its README's "Your own characters" section explains the image rules.
- A version of `unique-pool` that keeps the same picture per agent across replays has been proposed upstream. If it's merged, a future release won't need that patch.

## License

[MIT](LICENSE)
