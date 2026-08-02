# videoanima

História → **decupagem cinematográfica** → imagens → clipes → filme vertical narrado,
com provedor de imagem e de vídeo escolhíveis por parâmetro.

```bash
python3 rodar.py exemplo --so-decupagem          # valida ritmo + custo, não gasta
python3 rodar.py exemplo --img agnes --video agnes
python3 rodar.py exemplo --img kie   --video klingai
```

**Tudo mora no output.** Um id solto resolve para
`~/projetos/output/videoanima/<id>/decupagem.yaml` — texto e imagem no mesmo lugar.
`historias/<id>/` no repo é só semente: na primeira execução a decupagem é copiada
para o output e a de lá passa a ser a viva (edite essa).

| arquivo | o que é |
|---|---|
| `gramatica.py` | vocabulário de direção destilado de `doc/analise-estilo-fbvideo.md`: enquadramento, ângulo, movimento, velocidade, look, ritmo → fragmentos de prompt |
| `provedores.py` | adaptadores de imagem (`agnes`/`inemaimg`/`kie`) e vídeo (`agnes`/`klingai`/`kie`); cada armadilha medida mora no adaptador dela |
| `narracao.py` | inemavox chatterbox, voz `rachel`, com a revisão de dicção antes do TTS |
| `montagem.py` | o que o gerador não faz: slow/speed-ramp, texto na tela, handheld, zoom-punch, trilha com ducking |
| `rodar.py` | orquestra, idempotente, com preview de custo antes da primeira chamada paga |
| `~/projetos/output/videoanima/<id>/decupagem.yaml` | o contrato — escrito e conferido **antes** de gastar; vive junto dos artefatos |
| `historias/<id>/` | semente no repo: copiada para o output na primeira execução |

Kling não tem key própria aqui: `--video klingai` roteia por **fal.ai** (`FAL_KEY`).
`klingai` e `kie` exigem keyframe em URL pública → combine com `--img agnes` ou `--img kie`.

Skill: `~/.claude/skills/videoanima/SKILL.md`
