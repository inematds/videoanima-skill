# Post-mortem — "O menino, o cão e o leão da montanha" (2026-08-02)

O filme saiu ruim. Este documento compara o que a **videoanima** fez com o que o
projeto **`~/projetos/videos-agnes`** já fazia bem (mesma API, mesma casa, inclusive
uma história de montanha com menino e cão), para isolar as causas. Nada aqui é
opinião: cada item traz o número ou a linha de código que o sustenta.

Fontes: `~/projetos/videos-agnes/README.md`, `historias/montanha.py`, `pipeline.py`;
saídas em `~/projetos/output/videos-agnes/`; e o nosso
`~/projetos/output/videoanima/montanha-leao/`.

---

## 0. O ERRO PRINCIPAL: o filme não se move (slideshow)

Medido com diferença entre quadros consecutivos (`tblend=difference` + `signalstats`,
média de YAVG — quanto maior, mais movimento):

| nosso filme (kling) | movimento | referência `videos-agnes/wobbly2` | movimento |
|---|---|---|---|
| p01 | **0,15** | clipe-01 | 4,84 |
| p05 | **0,17** | clipe-02 | 5,03 |
| p18 | **0,33** | clipe-03 | 11,86 |
| p16 | **0,79** | clipe-04 | 3,09 |
| p19 | **0,99** | | |
| p02 | **1,18** | | |
| p17 | **1,30** | | |
| p09 / p13 / p20 / p08 / p07 | 9,8 / 9,0 / 6,2 / 5,7 / 5,5 | | |

**8 dos 20 planos ficaram abaixo de 2,0 — praticamente uma foto parada.** É daí que vem
a sensação de slideshow, e não do áudio.

Investiguei a hipótese de congelamento na montagem (o `tpad=stop_mode=clone` que estica
o plano clonando o último quadro): **não era isso** — só 3,4s de 95,6s, 4% do filme.

As três causas reais, todas nossas:

### a) O par A→B só descreve movimento de CÂMERA, nunca ação do sujeito

`gramatica.dica_keyframe_b()` diz o que muda de A para B, e o que ela diz é sempre
enquadramento: *"B desloca o enquadramento lateralmente"*, *"B sobe ou desce"*, *"B mais
fechado"*. Para `estatico` e `handheld` ela diz literalmente **"A e B praticamente
iguais"**. O personagem está na mesma pose nas duas pontas — o gerador não tem o que
interpolar, e devolve uma imagem viva com deriva mínima.

Os dados confirmam: quanto mais **parecidos** A e B (PSNR alto), menos movimento.

| plano | PSNR A↔B | movimento |
|---|---|---|
| p17 | **43,5** (quase idênticos) | 1,30 |
| p01 | 31,3 | 0,15 |
| p05 | 28,5 | 0,17 |
| p09 | **12,6** (bem diferentes) | **9,84** |
| p13 | 11,8 | **8,96** |
| p14 | 12,7 | 4,87 |

### b) A dica do keyframe B vai para o gerador EM PORTUGUÊS, como jargão interno

O prompt de imagem do keyframe B termina assim (verificado, plano 17):

```
... Pixar-style 3D animated feature render. Camera has moved: B desloca o enquadramento lateralmente.
```

O modelo recebe **"B desloca o enquadramento lateralmente"** — português, dentro de um
prompt em inglês, usando a nossa convenção de nome ("B"). Não é instrução acionável para
nenhum gerador. Pior: o README do `videos-agnes` mede que **prompt em PT cai no filtro
de conteúdo da Agnes (HTTP 400)**. Ou seja, a instrução que deveria criar a diferença
entre A e B era ruído. Por isso tantos pares saíram quase idênticos.

### c) A decupagem descreve QUADROS, o filme de origem descreve AÇÕES

O doc de referência, na coluna "O que aparece", é quase todo verbo:

> *Pés do menino correndo de chinelo · Cachorro correndo dentro de casa · Menino e cão
> saltando cerca de madeira · Menino e cão caem ajoelhados de emoção · Avô se abre em
> posição de abraço · Pés do menino correndo ao reencontro*

A nossa fica em estado, não em ação: *"A boy and his dog small on a high rocky mountain
ridge"*, *"the mountain lion's scarred face filling the frame"*. Aproveitamos do filme
de origem a **tabela** (enquadramento/ângulo/câmera) e deixamos de fora justamente o que
fazia aquele filme funcionar: **a ação contínua**. Não é coincidência que os nossos
planos com mais movimento (p09 leão saltando, p13 atravessando o tronco, p07 correndo,
p20 descendo a trilha) sejam exatamente os que têm verbo de ação na descrição.

### c-bis) O provedor "melhor" (Kling, pago) se moveu MENOS que a Agnes (grátis)

Os dois rodaram com **os mesmos keyframes, o mesmo prompt e as mesmas durações** — é um
teste controlado. Movimento médio entre quadros:

| | média | planos em que ganhou |
|---|---|---|
| **Agnes** `agnes-video-v2.0` (US$ 0) | **5,78** | **16 de 20** |
| **Kling** `kling-video-v3_0` 720p (créditos) | 3,36 | 4 de 20 |

Casos extremos: p17 **10,80 × 1,30**; p11 10,20 × 4,06; p10 10,94 × 3,74; p01 2,58 × 0,15.

Hipótese (não verificada): a Agnes roda `mode: "keyframes"` com o par [A, B] como dois
**keyframes de verdade** e é obrigada a percorrer o caminho entre eles; o Kling recebe
`first_image` + `tail_image`, mas parece ancorar muito mais na primeira imagem. Também é
possível que o prompt curto pese mais no Kling.

Consequência prática: **trocar para o provedor pago piorou o sintoma que mais incomodou**.
Antes de repetir a escolha, medir movimento — não assumir que o modelo mais novo/caro
entrega mais movimento com o mesmo material.

### d) Prompt de vídeo curto e sem negative prompt

O que mandamos por clipe (plano 01, na íntegra):

> *"A boy and his dog small on a high rocky mountain ridge, an ocean of peaks behind
> them, last sunlight leaving the stone. vertical tilt revealing the scene. Natural
> motion, consistent characters and style."*

Compare com o template oficial de image-to-video do **LTX-2** (encontrado em
`~/projetos/VideosDGX2/comfyui-env/.../templates/video_ltx2_i2v_lora.json`), que descreve
o movimento beat a beat em ~130 palavras — expressão, para onde olha, o que acontece
"as he looks down", e o que a câmera faz e deixa de fazer.

E o mais direto: **todos** esses templates trazem *negative prompt* contra imagem parada.

- LTX-2 (`video_ltx2_i2v_distilled.json`, `..._depth_to_video.json`):
  `blurry, low quality, still frame, frames, watermark, overlay, titles, ...`
- Wan 2.2 (`workflow_wan22_14b_t2v.json`), em chinês:
  `... 静态 ... 画面静止 ... 静止不动的画面 ...` → *estático · imagem parada · quadro imóvel*.

Nós **não usamos negative prompt em nenhuma chamada** — apesar de o README do
`videos-agnes` registrar que `negative_prompt` **existe** no endpoint de vídeo da Agnes
(e `seed` também). A indústria trata "still frame" como o defeito padrão a combater, e
nós não combatemos.

---

## 1. A causa raiz do FORMATO: o documento de referência era um ANÚNCIO

A gramática da videoanima foi destilada de `doc/analise-estilo-fbvideo.md`, que na
própria ficha técnica diz:

> **Tipo de Conteúdo:** Vídeo publicitário / Chamada para Workshop de Animação com IA

O `SKILL.md` até avisa que dali só transferem "vocabulário e ritmo, não a forma do
anúncio". **Mas transferimos a forma junto**, porque ela estava tabelada e era fácil
de codificar:

| do anúncio | virou na videoanima | efeito no filme de história |
|---|---|---|
| §6 texto na tela / card / CTA | campo `texto_tela`, `drawtext` em 4 planos | **legendas que você não pediu e não deveriam existir** |
| planos de 1–3s (montagem publicitária) | `dur` média 3,7s, 20 planos em 62s | narração picotada (item 3) |
| 23 planos com apresentador e split-screen | 20 planos de corte seco | história vira videoclipe |

O `videos-agnes` **não desenha texto nenhum** no vídeo — o único `legenda` do código é
a *caption do Telegram* (`pipeline.py:223 enviar_telegram(path, legenda)`). Não existe
`drawtext` no pipeline dele. A legenda foi invenção nossa, herdada de um formato de
propaganda.

---

## 2. Consistência de personagem: nós jogamos fora a descrição textual

Esta é a explicação técnica de "poucas cenas consistentes".

**Como o `videos-agnes` faz** — a descrição completa do personagem entra **em toda
cena**, por interpolação de string, *além* das âncoras como referência:

```python
LUCAS = ('Lucas, an eleven-year-old boy with short brown hair, wearing a red winter '
         'coat, blue snow pants, a wool hat and gloves')
('cena-02-a', f'{LUCAS} noticing a bright blue bird flying between the pine trees...',
 ['anc-lucas']),
```

**Como a videoanima faz** — `gramatica.prompt_de_imagem()`:

```python
for pid in plano.get('refs', []):
    if pid in personagens and not refs_usadas:      # <-- aqui
        partes.append(personagens[pid]...)
```

Quando há referência (quase sempre), a descrição do personagem é **descartada**.
Verificado no plano 08 do nosso filme:

```
"messy black hair" está no prompt final? False
```

Ou seja: o gerador recebeu "The boy sprinting..." + "keep the same characters as in the
reference images" — e nenhuma palavra sobre cabelo preto bagunçado, moletom azul ou
mochila vermelha. A âncora sozinha **não trava identidade**; o próprio README do
`videos-agnes` mede isso:

> Preserva **estilo e composição** ✅. **NÃO** trava **identidade de personagem** com 1
> ref (o rosto muda). Com **2 refs** a identidade melhora muito.

Nós apostamos tudo no elo mais fraco (a referência visual) e removemos o mais forte (o
texto). Daí o porte do cão oscilando entre filhote e adulto e o menino mudando de cara.

**Agravante do nosso lado:** a Agnes tem `seed` no vídeo mas **não na imagem**; o
`inemaimg` (flux2-klein) tem. Corrigimos a seed no meio do caminho, mas ela é derivada
do prompt — e se o prompt não descreve o personagem, seed nenhuma segura identidade.

---

## 3. Narração: picotamos a história em telegramas

Números medidos nas duas decupagens da *mesma* premissa:

| | videos-agnes/montanha | videoanima/montanha-leao |
|---|---|---|
| blocos de narração | **12** | **20** |
| palavras por bloco (média) | **35,2** | **7,3** |
| menor bloco | 27 palavras | **1 palavra** ("Correram.") |
| voz | `bella` (o README chama de "tom de storytelling") | `rachel` |

O `videos-agnes` narra **um parágrafo por cena** — o locutor tem embalo, respiração,
prosódia. Nós escrevemos **uma frase curta por plano**, e o TTS recebeu 20 fragmentos
isolados: cada um começa do zero, com ataque e queda próprios. Isso é o que faz a
narração soar mecânica; não é defeito da `rachel`.

E teve um efeito colateral pior: como "a fala manda" (o plano estica até caber a
locução), 20 falas curtas com pausa própria **incharam o filme de 62s para 95,7s** —
média de 4,8s/plano contra os 3,7s da própria referência de ritmo. O filme ficou
arrastado *e* picotado ao mesmo tempo.

---

## 4. Áudio: adicionamos ruído que o pipeline bom não tem

O `pipeline.py` do `videos-agnes` não tem trilha, não tem SFX, não tem `amix`: só
narração. Nós acrescentamos trilha + 10 SFX buscados no Freesound por texto, **sem
audição de nenhum deles**. A busca é notoriamente frouxa — no meio do trabalho,
`"wind mountain"` devolveu *"a small brook in a forest"*. Não há nenhuma garantia de
que "dog growl low" ou "wood snap crack break" sejam o que o nome promete; entraram no
filme não ouvidos.

O que de fato estava quebrado no áudio e foi corrigido: o filme saía a **−30,7 LUFS**
(inaudível no celular), agora **−15,8 LUFS**.

---

## 5. O que a videoanima tem de melhor que o videos-agnes

Para não jogar fora o que presta:

- **Par de keyframes A→B com gramática de câmera** — o `videos-agnes` também usa
  `mode: keyframes`, mas sem vocabulário de movimento; nossa `gramatica.py` deriva o
  que muda de A para B a partir do movimento escolhido.
- **Provedor de vídeo trocável**, incluindo o **Kling direto pela assinatura**
  (`kling-video-v3_0`, único com `tail_image` + duração livre 3–15s).
- **Folha de contato** antes de gastar vídeo — foi ela que pegou os planos 11, 13, 14,
  15 e 20 errados.
- **Normalização de loudness** na montagem (o `videos-agnes` não tem).

---

## 6. O que mudaria, se fôssemos refazer (nada foi feito)

**Movimento primeiro — é o que quebrou o filme:**

1. **Keyframe B = o sujeito AVANÇOU na ação**, não a câmera mudou de lugar. B tem que
   ser o fim do gesto (pé no ar → pé no chão; boca fechada → latindo), e a dica precisa
   ir em **inglês**, descrevendo a cena, não a nossa convenção ("B desloca...").
2. **Escrever `acao` com verbo contínuo**, como a coluna do filme de origem, e não como
   legenda de foto.
3. **Negative prompt em toda chamada de vídeo**: `still frame, static image, motionless,
   frozen, slideshow`. É o padrão dos templates LTX-2 e Wan 2.2, e a Agnes aceita.
4. **Prompt de vídeo longo** (as ~130 palavras do padrão LTX), descrevendo o movimento
   beat a beat, em vez das nossas ~30.
5. Medir movimento (`tblend=difference`) como **portão de qualidade**: clipe abaixo de
   ~2,0 é foto e deveria ser refeito antes da montagem, do mesmo jeito que a folha de
   contato barra imagem errada.

**Depois, o resto:**

6. **Apagar `texto_tela` da gramática.** É herança de anúncio.
2. **Sempre injetar a descrição do personagem no prompt**, com ou sem referência —
   remover o `and not refs_usadas`.
3. **Narrar por bloco, não por plano**: 8–12 blocos de ~30–40 palavras, com vários
   planos correndo sob o mesmo bloco de locução, em vez de 1 fala por plano.
4. **Voz `bella`** para história (o `rachel` é o default global, mas o projeto que deu
   certo usa `bella` e documenta o porquê).
5. **Ouvir os SFX antes de mixar**, ou não usar SFX.
6. Considerar a **referência encadeada** (plano N usa o plano N−1 como referência), que
   o `videos-agnes` documenta como o próximo passo contra deriva de figurino — está
   parada lá por causa do rate limit da Agnes, mas **no Kling não há esse gargalo**.
