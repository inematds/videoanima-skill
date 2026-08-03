# videoanima v3 — o sistema refeito

Redesenho a partir do que foi **medido** nos três filmes de 2026-08-02 e das quatro
críticas externas. Cada regra abaixo tem uma causa observada, não uma suposição.

## O princípio que muda tudo

> **A imagem manda. O texto quase não é lido.**

Medido: mesmos keyframes, 43 planos, prompt de 81 palavras deu 10,07 de movimento e
prompt de 18 palavras deu 9,93 — **1,4% de diferença**. Todo controle que importa tem
que estar **na imagem** (no par A→B, nas âncoras, na composição), não em campos de
texto. Por isso o esquema v3 é enxuto: os campos que sobreviveram são os que viram
imagem ou viram decisão de pipeline.

## As 6 mudanças estruturais

### 1. `tipo_plano` — nem todo plano vai ao gerador de vídeo
| tipo | o que é | como é feito |
|---|---|---|
| `acao` | o sujeito executa algo | gerador de vídeo, par A→B |
| `revelacao` | a câmera mostra o que já estava lá | **imagem + câmera** (ffmpeg) |
| `tableau` | estado, atmosfera, objeto parado | **imagem + câmera** (ffmpeg) |

Causa: o snowboard trocou de cor e ângulo entre A e B (11,2 de movimento num objeto
largado na neve) e a luva "abriu os dedos". Plano de estado mandado ao gerador é um
pedido para ele inventar mudança. Sem API: sem deriva, sem filtro de conteúdo, duração
exata, instantâneo.

### 2. Keyframe B **deriva do A** (referência encadeada)
Hoje o B é gerado do zero com as mesmas âncoras do A — nunca vê o A. Tudo que não está
nas âncoras (prancha, luva, corda, cenário) é reinventado. No v3 o A entra como
referência do B. É a correção de continuidade com maior efeito por linha de código.

### 3. Bíblia: personagens **e ambientes**, com imutável separado do variável
Faltavam âncoras de **ambiente** (vila, floresta, bacia) — cada plano inventava o lugar.
E as fichas de personagem tinham 2 linhas para sustentar 50 planos, sem fixar de que
lado fica a orelha dobrada do cão ou a luva que falta.

### 4. `look` por **bloco de tempo**, não global
O look global dizia literalmente `daylight`, e os 50 planos herdavam — por isso a busca
do fim da tarde e a chegada noturna saíam com luz de meio-dia. O campo por plano já
existia e nunca era usado.

### 5. Narração por **bloco**, atravessando planos
Hoje a fala é por plano e o plano estica para caber ("a fala manda"). Resultado medido:
o filme planejado em 106s saiu com 150s, e o de 62s saiu com 95s. No v3 a narração é do
bloco e corre por cima de vários planos; só o último plano do bloco estica, e só se
precisar. O corte ágil sobrevive.

### 6. Prompt de vídeo mínimo por padrão
Já que o texto quase não muda o resultado, o padrão passa a ser a ordem de movimento
curta. Prompt longo vira opção (`--prompt-longo`), não regra.

## O que já entrou e fica

- **Negativo só no vídeo, nunca na imagem.** A negação vira atrator, e o `flux2-klein`
  não aceita `negative_prompt`. Validador `validar_prompts()` barra antes de gastar.
- **Descrição do personagem sempre no prompt**, com ou sem referência.
- **Portão de movimento** (refaz clipe abaixo do limiar) e **portão de duração** (nunca
  entregar filme truncado em silêncio).
- **Lote na Agnes** com prazo por job e detecção de job morto: 26s por clipe contra 170s.
- **Regra de composição para contato físico** — o filtro reage à imagem, não ao texto,
  e é aleatório entre execuções.

## Esquema v3

```yaml
id: minha-historia
titulo: "..."
formato: {size: "736x1312", fps: 24}
voz: bella

biblia:
  personagens:
    - id: menino
      imutavel: "A boy about ten, messy black hair, round face, brown eyes, red winter
                 coat with black zip, blue hoodie, red backpack with two black buckles"
      variavel: "neve acumulada no casaco conforme o bloco"
      deriva_de:
  ambientes:
    - id: vila
      imutavel: "A small alpine village of dark wooden houses with snow-covered roofs,
                 one narrow street, iron lanterns on posts"
    - id: bacia
      imutavel: "A steep white bowl below a cliff lip, scattered broken pines and
                 grey boulders"

blocos:
  - id: convocacao
    planos: [1, 8]
    look: "cold blue snowstorm daylight, flat white sky"
    narracao: "A mesma montanha, três meses depois... (parágrafo inteiro)"
  - id: busca
    planos: [9, 20]
    look: "grey overcast afternoon, falling snow, low contrast"
    narracao: "..."

planos:
  - n: 25
    tipo_plano: tableau          # não vai ao gerador
    dur: 2.4
    enquadramento: detalhe
    angulo: rente-ao-chao
    camera: pan
    ambiente: bacia
    acao: "A snowboard stands upright half buried in deep snow, bindings hanging open"
    refs: []
  - n: 27
    tipo_plano: acao
    dur: 1.6
    camera: tracking
    ambiente: bacia
    refs: [cao]
    acao: "The dog is bounding down the steep slope in long leaps, snow bursting up"
    acao_b: "the dog has landed far below, already turning to look back up"
```

Some do esquema, por não virar imagem nem decisão: `estado_entrada`, `lens`,
`visibilidade em metros`, `movimento_proibido`. Se a evidência mudar, voltam.
