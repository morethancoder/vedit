---
summary: product plug preset from project.yaml
next: vedit build
---
# cue type: plug

Status: built; `vedit build` renders it (`vedit build --plan` shows where it lands).

## What it is

A preset sequence for the product you promote (a phone demo and the URL click). The product is named by
`plug:` in project.yaml.

## Write

```yaml
- type: plug
  at: "words that start it"
```

## Rules

- Fields: `url` and `trial`, each the spoken words of that moment (the engine finds their time). Default length 18 s.
- The preset is `custom/plug/plug.yaml` in the project: `name`, `kicker`, `url`, `trial` (texts shown) and
  `logo`, `demo` (phone video), `hold` (its last frame), files in the same folder. Without it, the project's
  channel preset `~/.config/vedit/channels/<handle>/plug/plug.yaml` (same keys, files beside it) is used, so
  every video of the channel shares one phone demo. Without either: brand text only (`plug:` in project.yaml).
