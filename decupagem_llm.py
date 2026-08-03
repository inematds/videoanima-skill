"""Gera uma decupagem com um LLM LOCAL (ollama) e a valida com as nossas regras.

    python3 decupagem_llm.py <id> "<premissa>" [--planos 40] [--modelo qwen3.6:35b-a3b]

Serve para COMPARAR: o modelo local recebe a mesma premissa e as mesmas regras
medidas que a gente usa, e a saida passa pelos mesmos validadores. O que ele escrever
vai para ~/projetos/output/videoanima/<id>/decupagem.yaml e roda no mesmo pipeline.

Nao ha mistica no prompt: as regras abaixo sao as que foram MEDIDAS nos filmes de
2026-08-02 (ver doc/pos-mortem-montanha-leao.md e doc/sistema-v3.md).
"""
import argparse, json, os, re, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gramatica as G

OLLAMA = 'http://localhost:11434/api/generate'
OUT_BASE = os.path.expanduser('~/projetos/output/videoanima')

REGRAS = """Você escreve DECUPAGEM CINEMATOGRÁFICA para um pipeline que transforma
texto em filme animado vertical. A saída é YAML puro, sem comentários fora do YAML e
sem texto antes ou depois.

REGRAS MEDIDAS (não são preferências — cada uma corrigiu um defeito real):

1. A IMAGEM MANDA. O gerador de vídeo recebe dois keyframes (A e B) e interpola entre
   eles. Prompt longo não muda o resultado (medido: 1,4% de diferença). O que cria
   movimento é a DIFERENÇA entre A e B.
2. `acao` em INGLÊS, com VERBO CONTÍNUO, descrevendo movimento ("The dog is bounding
   down the slope in long leaps"), nunca um quadro parado ("A dog on a slope").
3. `acao_b` em INGLÊS: onde o gesto TERMINA. É o keyframe B. Sem isso o clipe sai
   parado.
4. NUNCA use negação ("no people", "without", "nothing"). A negação vira atrator e traz
   justamente o que se quer evitar. Descreva o que ESTÁ no quadro.
5. `tipo_plano`:
   - `acao` → alguém executa algo (vai para o gerador de vídeo);
   - `revelacao` → a câmera mostra o que já estava lá;
   - `tableau` → estado, objeto parado, atmosfera.
   Objeto largado, paisagem vazia e rosto parado são `tableau` ou `revelacao` — se
   mandados como `acao`, o gerador inventa mudança (uma prancha largada trocou de cor).
6. Contato físico próximo entre crianças (abraço, braço no ombro, animal no colo) é
   BLOQUEADO pelo filtro de conteúdo. Componha com distância, de costas ou em silhueta.
7. `narracao` em PORTUGUÊS, só em alguns planos, em frases inteiras (25 a 40 palavras).
   Narrar todo plano com frase curta deixa a locução picotada.
8. Ritmo: média de 2 a 4 segundos por plano. Alternar escalas (detalhe/close/medio/geral)
   é o que cria ritmo visual.
9. Continuidade: um adereço-guia que atravessa a história; direção de movimento
   constante; e `look` por bloco de tempo (manhã → tarde → pôr do sol → noite).

ESQUEMA EXATO:

id: <id>
titulo: "..."
formato: {size: "736x1312", fps: 24}
voz: bella
biblia:
  personagens:
    - id: <slug>
      imutavel: "<descrição física e figurino fixos, em inglês, 25-40 palavras>"
      deriva_de:            # id de outro personagem, ou vazio
  ambientes:
    - id: <slug>
      imutavel: "<descrição do lugar, em inglês>"
blocos:
  - id: <slug>
    planos: [1, 8]
    look: "<luz e clima em inglês, com a hora do dia>"
audio:
  trilha: "<busca de música em inglês>"
planos:
  - n: 1
    tipo_plano: acao|revelacao|tableau
    dur: 2.5
    enquadramento: detalhe|close|medio|geral
    angulo: nivel|plongee|contra-plongee|rente-ao-chao
    camera: estatico|pan|tilt|tracking|tracking-traseiro|zoom-in|zoom-punch|handheld
    velocidade: normal|slow|speed-ramp
    transicao_saida: corte|zoom-punch
    ambiente: <id de ambiente>
    refs: [<ids de personagens em cena>]
    acao: "<inglês, verbo contínuo>"
    acao_b: "<inglês, onde o gesto termina>"
    narracao: "<português, só em alguns planos>"
    sfx: [{q: "<busca em inglês>", vol: 0.45}]
"""


def chamar(modelo, prompt, timeout=1800):
    body = {'model': modelo, 'prompt': prompt, 'stream': False, 'think': False,
            'options': {'num_ctx': 32768, 'temperature': 0.7}}
    r = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(),
                               headers={'Content-Type': 'application/json'})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(r, timeout=timeout).read())
    return d.get('response', ''), time.time() - t0


def extrair_yaml(txt):
    """O modelo costuma embrulhar em ``` ou tagarelar antes. Pega so o YAML."""
    m = re.search(r'```(?:yaml)?\s*(.+?)```', txt, re.S)
    bruto = m.group(1) if m else txt
    i = bruto.find('id:')
    return bruto[i:] if i >= 0 else bruto


def auditar(S):
    """Passa a saida do LLM pelos MESMOS validadores do pipeline."""
    import statistics as st
    planos = S.get('planos') or []
    p = [f'planos: {len(planos)}']
    if planos:
        durs = [x.get('dur', 0) for x in planos]
        p.append(f'duração: {sum(durs):.0f}s · média {st.mean(durs):.1f}s/plano')
        tipos = {}
        for x in planos:
            tipos[x.get('tipo_plano', 'ausente')] = tipos.get(x.get('tipo_plano', 'ausente'), 0) + 1
        p.append('tipos: ' + ', '.join(f'{k}={v}' for k, v in sorted(tipos.items())))
        sem_b = [x['n'] for x in planos if not x.get('acao_b')]
        p.append(f'sem acao_b: {sem_b or "nenhum"}')
        falas = [x for x in planos if (x.get('narracao') or '').strip()]
        if falas:
            pal = [len(x['narracao'].split()) for x in falas]
            p.append(f'narração: {len(falas)}/{len(planos)} planos · {st.mean(pal):.1f} palavras/bloco')
        ids = {c['id'] for c in (S.get('biblia', {}).get('personagens') or [])}
        ruins = sorted({r for x in planos for r in (x.get('refs') or []) if r not in ids})
        p.append(f'refs inválidas: {ruins or "nenhuma"}')
    avisos = G.validar_ritmo(planos) + G.validar_prompts(planos)
    return p, avisos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('id')
    ap.add_argument('premissa')
    ap.add_argument('--planos', type=int, default=40)
    ap.add_argument('--modelo', default='qwen3.6:35b-a3b')
    a = ap.parse_args()

    prompt = (f'{REGRAS}\n\nPREMISSA DA HISTÓRIA:\n{a.premissa}\n\n'
              f'Escreva a decupagem completa com EXATAMENTE {a.planos} planos, '
              f'id: {a.id}. Responda só o YAML.')
    print(f'  modelo {a.modelo} · {a.planos} planos pedidos...', flush=True)
    try:
        txt, seg = chamar(a.modelo, prompt)
    except Exception as e:
        sys.exit(f'  ollama falhou: {str(e)[:140]}\n  (o servidor está no ar? `ollama ps`)')
    print(f'  respondeu em {seg/60:.1f} min · {len(txt)} caracteres')

    import yaml
    bruto = extrair_yaml(txt)
    D = f'{OUT_BASE}/{a.id}'
    os.makedirs(D, exist_ok=True)
    open(f'{D}/resposta-crua.txt', 'w').write(txt)
    try:
        S = yaml.safe_load(bruto)
        assert isinstance(S, dict) and S.get('planos')
    except Exception as e:
        sys.exit(f'  YAML inválido ({str(e)[:100]}). Resposta crua em {D}/resposta-crua.txt')
    S['id'] = a.id
    open(f'{D}/decupagem.yaml', 'w').write(yaml.dump(S, allow_unicode=True, sort_keys=False))
    print(f'  >> {D}/decupagem.yaml\n')
    fatos, avisos = auditar(S)
    for f in fatos:
        print(f'  {f}')
    print()
    for av in (avisos or ['sem avisos dos validadores']):
        print(f'  ⚠️  {av}')


if __name__ == '__main__':
    main()
