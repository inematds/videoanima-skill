# videoanima

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

Historia → **desglose cinematográfico** → imágenes → clips → película vertical narrada,
con proveedor de imagen y de video seleccionables mediante parámetros.

> ⚠️ **En ajustes — no es una versión estable.** El pipeline se ejecuta de principio a fin, pero está en un
> ciclo abierto de correcciones a partir de las películas que él mismo produjo. El primer corte
> salió mal (escenas estáticas, personaje inconsistente, narración entrecortada); lo que se
> midió y lo que ya cambió a raíz de eso está en
> [`doc/pos-mortem-montanha-leao.md`](doc/pos-mortem-montanha-leao.md): léelo antes de
> usarlo como referencia. Sigue pendiente: la narración aún alarga los planos más allá del ritmo
> previsto, los SFX se agregan sin escucharlos antes y la referencia encadenada entre planos
> (el plano N usa el N−1) no está implementada.

## 📖 Guía de uso

Guía completa (landing + paso a paso): **https://inematds.github.io/videoanima-skill/guia/es/**

```bash
python3 rodar.py exemplo --so-decupagem          # valida el ritmo + el costo, no gasta
python3 rodar.py exemplo --img agnes --video agnes
python3 rodar.py exemplo --img kie   --video klingai
```

**Todo está en output.** Un id suelto se resuelve en
`~/projetos/output/videoanima/<id>/decupagem.yaml` — texto e imagen en el mismo lugar.
`historias/<id>/` en el repo es solo una semilla: en la primera ejecución, el desglose se copia
a output y el de allí pasa a ser el vigente (edítalo).

| archivo | qué es |
|---|---|
| `gramatica.py` | vocabulario de dirección destilado de `doc/analise-estilo-fbvideo.md`: encuadre, ángulo, movimiento, velocidad, look, ritmo → fragmentos de prompt |
| `provedores.py` | adaptadores de imagen (`agnes`/`inemaimg`/`kie`) y video (`agnes`/`kling`/`klingai`/`kie`); cada trampa detectada está en su adaptador |
| `narracao.py` | inemavox chatterbox (voz por desglose: `bella` para historia), con la revisión de dicción antes del TTS |
| `montagem.py` | lo que el generador no hace: slow/speed-ramp, handheld, zoom-punch, pista con ducking, SFX, loudnorm, medición de movimiento |
| `rodar.py` | orquesta, es idempotente y muestra una estimación de costos antes de la primera llamada paga |
| `~/projetos/output/videoanima/<id>/decupagem.yaml` | el contrato — se escribe y revisa **antes** de gastar; vive junto con los artefactos |
| `historias/<id>/` | semilla en el repo: se copia a output en la primera ejecución |

**El movimiento es lo que distingue una película de una presentación de diapositivas.** Cada plano incluye `acao` como verbo
continuo y `acao_b` (donde termina el gesto): es la diferencia entre A y B la que el generador
anima. Hay un negative prompt contra `still frame` y una compuerta que mide el movimiento de cada
clip y rehace los que quedan estáticos. El motivo de cada una de estas decisiones está en el post mortem.

**Video:** `--video agnes` (US$ 0, envío por lotes) · `--video kling` (suscripción
propia, vía CLI, acepta rutas locales) · `--video klingai` (Kling por **fal.ai**,
`FAL_KEY`) · `--video kie`. `klingai` y `kie` requieren un keyframe en una URL pública → combínalos
con `--img agnes` o `--img kie`. El personaje niño queda atrapado en el filtro de Agnes (HTTP 400):
usa `--img inemaimg`.

Skill: `~/.claude/skills/videoanima/SKILL.md`
