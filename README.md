# videoanima

História → **decupagem cinematográfica** → imagens → clipes → filme vertical narrado,
com provedor de imagem e de vídeo escolhíveis por parâmetro.

> ⚠️ **Em ajuste — não é versão estável.** O pipeline roda ponta a ponta, mas está em
> ciclo aberto de correção a partir dos filmes que ele mesmo produziu. O primeiro corte
> saiu ruim (cenas paradas, personagem inconsistente, narração picotada); o que foi
> medido, e o que já mudou por causa disso, está em
> [`doc/pos-mortem-montanha-leao.md`](doc/pos-mortem-montanha-leao.md) — leia antes de
> usar como referência. Ainda em aberto: narração ainda estica os planos além do ritmo
> planejado, os SFX entram sem audição prévia, e a referência encadeada entre planos
> (plano N usando o N−1) não foi implementada.

## 📖 Guia de uso

Guia completo (landing + passo a passo): **https://inematds.github.io/videoanima-skill/guia/**

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
| `provedores.py` | adaptadores de imagem (`agnes`/`inemaimg`/`kie`) e vídeo (`agnes`/`kling`/`klingai`/`kie`); cada armadilha medida mora no adaptador dela |
| `narracao.py` | inemavox chatterbox (voz por decupagem: `bella` para história), com a revisão de dicção antes do TTS |
| `montagem.py` | o que o gerador não faz: slow/speed-ramp, handheld, zoom-punch, trilha com ducking, SFX, loudnorm, medição de movimento |
| `rodar.py` | orquestra, idempotente, com preview de custo antes da primeira chamada paga |
| `~/projetos/output/videoanima/<id>/decupagem.yaml` | o contrato — escrito e conferido **antes** de gastar; vive junto dos artefatos |
| `historias/<id>/` | semente no repo: copiada para o output na primeira execução |

**Movimento é o que separa filme de slideshow.** Cada plano traz `acao` em verbo
contínuo e `acao_b` (onde o gesto termina) — é a diferença entre A e B que o gerador
anima. Há negative prompt contra `still frame` e um portão que mede o movimento de cada
clipe e refaz o que sair parado. O porquê de cada uma dessas decisões está no post-mortem.

**Vídeo:** `--video agnes` (US$ 0, submissão em lote) · `--video kling` (assinatura
própria, via CLI, aceita caminho local) · `--video klingai` (Kling por **fal.ai**,
`FAL_KEY`) · `--video kie`. `klingai` e `kie` exigem keyframe em URL pública → combine
com `--img agnes` ou `--img kie`. Personagem criança cai no filtro da Agnes (HTTP 400):
use `--img inemaimg`.

Skill: `~/.claude/skills/videoanima/SKILL.md`
