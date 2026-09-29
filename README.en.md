# videoanima

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

Story → **cinematic shot breakdown** → images → clips → narrated vertical film,
with image and video providers selectable via parameters.

> ⚠️ **Under adjustment — not a stable release.** The pipeline runs end to end, but it is in an open correction cycle based on the films it has produced. The first cut came out poorly (static scenes, inconsistent character, choppy narration); what was measured and what has already changed as a result are documented in
> [`doc/pos-mortem-montanha-leao.md`](doc/pos-mortem-montanha-leao.md) — read it before
> using this as a reference. Still unresolved: narration stretches shots beyond the planned pacing, SFX are added without prior listening, and chained references between shots (shot N using N−1) have not been implemented.

## 📖 User Guide

Complete guide (landing page + step-by-step instructions): **https://inematds.github.io/videoanima-skill/guia/en/**

```bash
python3 rodar.py exemplo --so-decupagem          # validates pacing + cost, does not spend
python3 rodar.py exemplo --img agnes --video agnes
python3 rodar.py exemplo --img kie   --video klingai
```

**Everything lives in the output.** A standalone ID resolves to
`~/projetos/output/videoanima/<id>/decupagem.yaml` — text and image in the same place.
`historias/<id>/` in the repo is just a seed: on the first run, the shot breakdown is copied
to the output, and the copy there becomes the active one (edit that one).

| file | what it is |
|---|---|
| `gramatica.py` | directing vocabulary distilled from `doc/analise-estilo-fbvideo.md`: framing, angle, movement, speed, look, pacing → prompt fragments |
| `provedores.py` | image adapters (`agnes`/`inemaimg`/`kie`) and video adapters (`agnes`/`kling`/`klingai`/`kie`); each measured pitfall lives in its own adapter |
| `narracao.py` | inemavox chatterbox (voice per shot breakdown: `bella` for stories), with diction review before TTS |
| `montagem.py` | what the generator does not: slow/speed-ramp, handheld, zoom-punch, ducked soundtrack, SFX, loudnorm, motion measurement |
| `rodar.py` | orchestrates, idempotent, with a cost preview before the first paid call |
| `~/projetos/output/videoanima/<id>/decupagem.yaml` | the contract — written and checked **before** spending; lives alongside the artifacts |
| `historias/<id>/` | seed in the repo: copied to the output on the first run |

**Motion is what separates film from slideshow.** Each shot has `acao` as a continuous verb and `acao_b` (where the gesture ends) — the difference between A and B is what the generator animates. There is a negative prompt against `still frame` and a gate that measures the motion of each clip and recreates anything that comes out static. The post-mortem explains the reason for each of these decisions.

**Video:** `--video agnes` (US$ 0, batch submission) · `--video kling` (own subscription, via CLI, accepts a local path) · `--video klingai` (Kling via **fal.ai**,
`FAL_KEY`) · `--video kie`. `klingai` and `kie` require a keyframe at a public URL → pair with `--img agnes` or `--img kie`. A child character gets caught by Agnes's filter (HTTP 400): use `--img inemaimg`.

Skill: `~/.claude/skills/videoanima/SKILL.md`
