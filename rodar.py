"""historia (decupagem.yaml) -> filme.

    python3 rodar.py <pasta-da-historia> [--img agnes|inemaimg|kie]
                                         [--video agnes|klingai|kie]
                                         [--so-decupagem] [--sim]

Idempotente: cada etapa pula o que ja existe em disco. Reexecutar depois de apagar
um keyframe refaz so aquele keyframe (e o clipe que depende dele).

Ordem deliberada — narracao ANTES do video: a fala e que define quantos segundos
cada plano precisa durar. Gerar clipe antes da voz produz filme que nao casa.
"""
import argparse, json, os, shutil, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(line_buffering=True)   # log util mesmo redirecionado
except Exception:
    pass
import gramatica as G
import provedores as P
import montagem as M
from narracao import narrar, revisar

OUT_BASE = os.path.expanduser('~/projetos/output/videoanima')
# medido: clipes bons do videos-agnes ficam entre 3 e 12 de movimento medio
LIMIAR_MOV = 2.5


def carregar(caminho):
    try:
        import yaml
    except ImportError:
        sys.exit('falta PyYAML: pip install --user pyyaml')
    return yaml.safe_load(open(caminho))


def resolver_spec(arg):
    """A historia mora no OUTPUT, junto do que ela produz.

    Um id solto (`montanha-leao`) resolve para ~/projetos/output/videoanima/<id>/
    decupagem.yaml. Caminho explicito continua valendo — inclusive o `historias/`
    do repo, que vira semente: na primeira execucao a decupagem e COPIADA para o
    output e passa a ser a viva. Separar texto de imagem so cria duas verdades.
    """
    cands = []
    if arg.endswith('.yaml'):
        cands.append(arg)
    else:
        cands += [f'{OUT_BASE}/{os.path.basename(arg.rstrip("/"))}/decupagem.yaml',
                  f'{arg}/decupagem.yaml']
    for c in cands:
        if os.path.exists(c):
            return c
    sys.exit(f'decupagem nao encontrada. Procurei em:\n  ' + '\n  '.join(cands))


def semear(spec_path, D):
    """Se a decupagem veio de fora do output, copia para dentro e usa a de dentro."""
    destino = f'{D}/decupagem.yaml'
    if os.path.abspath(spec_path) != os.path.abspath(destino):
        shutil.copy(spec_path, destino)
        print(f'  decupagem copiada para o output: {destino}')
    return destino


def clipes_lote_agnes(itens, janela=65, por_janela=4, espaco_poll=4, prazo=1500):
    """Submete TODOS os clipes e colhe em paralelo, respeitando os dois rate limits.

    MEDIDO: no laco serial (submete -> espera pronto -> submete o proximo) cada clipe
    custava ~170s de parede, dos quais so ~30s eram geracao — o resto era espera
    ociosa. Como a Agnes e assincrona, o teto real e o rate limit de criacao
    (5/min): 50 clipes saem em ~15 min de submissao com a geracao acontecendo em
    paralelo, em vez de ~2h20.

    O polling TAMBEM tem limite proprio, entao as consultas sao espacadas e feitas
    uma de cada vez, em rodizio — nunca em rajada.

    `itens`: lista de dicts {n, dest, fa, fb, prompt, seg}. Devolve {n: movimento}.
    """
    fila, em_voo, subs, saida = list(itens), {}, [], {}
    while fila or em_voo:
        agora = time.time()
        subs[:] = [t for t in subs if agora - t < janela]
        if fila and len(subs) < por_janela:
            it = fila.pop(0)
            vid = P.agnes_submit(it['fa'], it['fb'], it['prompt'], it['seg'])
            subs.append(time.time())
            if vid:
                em_voo[it['n']] = dict(it, vid=vid, desde=time.time())
                print(f"  [p{it['n']:02d}] submetido ({len(em_voo)} em voo, "
                      f"{len(fila)} na fila)")
            elif it.get('tent', 1) < 2:
                fila.append(dict(it, tent=it.get('tent', 1) + 1))
            else:
                print(f"  [p{it['n']:02d}] FALHOU ao submeter")
            continue
        if not em_voo:
            time.sleep(3)          # fila travada so pelo rate limit
            continue
        n = next(iter(em_voo))
        it = em_voo.pop(n)
        est = P.agnes_estado(it['vid'], it['dest'])
        if est == 'esperando':
            # PRAZO por job: sem isso, um job que nunca responde 'completed' faz o
            # laco consultar para sempre (aconteceu: 10h presas em 2 clipes).
            if time.time() - it['desde'] > prazo:
                print(f'  [p{n:02d}] sem resposta em {prazo}s — desistindo desse job')
                est = 'erro'
            else:
                em_voo[n] = it     # volta para o fim do rodizio
                time.sleep(espaco_poll)
                continue
        if est == 'erro':
            if it.get('tent', 1) < 2:
                print(f'  [p{n:02d}] erro — recolocando na fila')
                fila.append(dict(it, tent=it.get('tent', 1) + 1))
            else:
                print(f'  [p{n:02d}] FALHOU')
            continue
        mv = M.movimento(it['dest'])
        # PORTAO DE MOVIMENTO: clipe parado e foto com deriva. Uma segunda tentativa
        # com a ordem de movimento reforcada antes de deixar entrar na montagem.
        if mv < LIMIAR_MOV and it.get('tent', 1) < 2:
            print(f'  [p{n:02d}] mov {mv:.2f} < {LIMIAR_MOV} — refazendo reforçado')
            os.remove(it['dest'])
            fila.append(dict(it, tent=it.get('tent', 1) + 1,
                             prompt=it['prompt'] + ' The subject is in constant visible '
                                    'motion from the first frame to the last; nothing '
                                    'in the frame is frozen.'))
            continue
        saida[n] = mv
        print(f"  [p{n:02d}] ok {P.dur(it['dest']):.1f}s · mov {mv:.2f}"
              + ('  ⚠️ ainda parado' if mv < LIMIAR_MOV else '')
              + f'  ({len(fila)} na fila, {len(em_voo)} em voo)')
    return saida


def preview_custo(planos, pi, pv):
    n_img = len(planos) * 2
    seg = sum(p['dur'] for p in planos)
    c = n_img * P.CUSTO_IMG[pi] + seg * P.CUSTO_VID_SEG[pv]
    print(f'\n  {len(planos)} planos · {seg:.0f}s · {n_img} imagens ({pi}) · video ({pv})')
    print(f'  custo estimado: US$ {c:.2f}' + ('  (gratuito)' if c == 0 else ''))
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('historia')
    ap.add_argument('--img', default='agnes', choices=list(P.IMAGEM))
    ap.add_argument('--video', default='agnes', choices=list(P.VIDEO))
    ap.add_argument('--so-decupagem', action='store_true',
                    help='valida ritmo e mostra o custo; nao gera nada')
    ap.add_argument('--so-imagens', action='store_true',
                    help='para depois dos keyframes e monta a folha de contato, '
                         'para conferir a cena antes de gastar video')
    ap.add_argument('--sim', action='store_true', help='nao pergunta antes de gastar')
    ap.add_argument('--prompt-minimo', action='store_true',
                    help='manda so a ordem de movimento ao gerador de video, sem '
                         'descrever a cena — sai em video-<provedor>-min/')
    a = ap.parse_args()

    spec_path = resolver_spec(a.historia)
    S = carregar(spec_path)
    nome = S.get('id') or os.path.basename(os.path.dirname(os.path.abspath(spec_path)))
    planos = S['planos']
    B = S.get('biblia', {})
    elenco = B.get('personagens') or S.get('personagens', [])
    ambientes = B.get('ambientes') or S.get('ambientes', [])
    ficha = lambda x: (x.get('imutavel') or x.get('prompt') or '').strip()
    person = {p['id']: ficha(p) for p in elenco}
    person.update({amb['id']: ficha(amb) for amb in ambientes})
    look_pad = S.get('look', {}).get('global', 'neutro-cinema')
    # LOOK POR BLOCO: o look global dizia literalmente "daylight" e os 50 planos
    # herdavam — a busca do fim de tarde e a chegada noturna saiam com luz de meio-dia.
    # `blocos: [{planos: [1, 8], look: "..."}]` pinta a faixa; o plano ainda pode ter
    # o seu proprio `look`, que vence.
    for b in S.get('blocos', []) or []:
        faixa = b.get('planos') or []
        if not (b.get('look') and len(faixa) == 2):
            continue
        for pl in S['planos']:
            if faixa[0] <= pl['n'] <= faixa[1] and not pl.get('look'):
                pl['look'] = b['look']
    size = S.get('formato', {}).get('size', '736x1312')

    print(f'\n{"="*60}\n{S.get("titulo", nome)}\n{"="*60}')

    # -------- 0. sanidade de ritmo (§3 do doc) antes de qualquer gasto
    for av in G.validar_estrutura(planos) + G.validar_ritmo(planos) + G.validar_prompts(planos):
        print(f'  ⚠️  {av}')
    custo = preview_custo(planos, a.img, a.video)
    if a.so_decupagem:
        return
    if custo > 0 and not a.sim:
        if input(f'\n  gastar ~US$ {custo:.2f}? [s/N] ').strip().lower() not in ('s', 'sim', 'y'):
            return print('  cancelado.')

    D = f'{OUT_BASE}/{nome}'
    # video separado POR PROVEDOR: rodar agnes e kling na mesma historia tem que
    # dar dois filmes comparaveis, nao um sobrescrevendo o outro.
    VD = f'{D}/video-{a.video}' + ('-min' if a.prompt_minimo else '')
    for sub in ('', '/img', '/narracao', '/' + os.path.basename(VD)):
        os.makedirs(D + sub, exist_ok=True)
    spec_path = semear(spec_path, D)
    est = f'{D}/estado.json'
    E = json.load(open(est)) if os.path.exists(est) else {'urls': {}, 'dur': {}}
    salvar = lambda: json.dump(E, open(est, 'w'), indent=2)
    gerar_img = P.IMAGEM[a.img]
    gerar_vid = P.VIDEO[a.video]

    # -------- 1. ANCORAS de personagem (model sheet)
    # A mae vai em text2img; as demais DERIVAM dela por img2img. Gerar em paralelo
    # produz individuos diferentes — nenhum desses geradores tem seed de identidade.
    print('\n[1/5] ÂNCORAS')
    # MEDIDO (2026-08-01, 6 chamadas): a Agnes devolve HTTP 400 de forma DETERMINISTICA
    # para "boy"/"child" — o mesmo prompt com adulto passa. Sem esse aviso o filme sai
    # com um adulto no lugar da crianca e ninguem entende por que.
    CRIANCA = ('boy', 'girl', 'child', 'kid', 'toddler', 'baby', 'year-old')
    if a.img == 'agnes':
        alvo = [p['id'] for p in elenco if any(w in ficha(p).lower() for w in CRIANCA)]
        if alvo:
            print(f'  ⚠️  personagem-criança na Agnes ({alvo}): o filtro de conteúdo '
                  f'bloqueia (400).\n      Use --img inemaimg (local, sem filtro) '
                  f'ou reescreva como personagem não-humano.')
    for p in elenco + ambientes:
        pid, png = p['id'], f"{D}/img/anc-{p['id']}.png"
        if pid in E['urls'] and os.path.exists(png):
            print(f'  [{pid}] ok'); continue
        mae = p.get('deriva_de')
        refs = [E['urls'][mae]] if mae and mae in E['urls'] else None
        # ambiente nao e model sheet: e uma vista ampla do lugar, que servira de
        # referencia para todo plano que se passa ali (antes cada plano inventava a vila)
        e_ambiente = any(x['id'] == pid for x in ambientes)
        prompt = (ficha(p) + '. '
                  + ('Wide establishing view of this place, no characters. '
                     if e_ambiente else
                     'Character model sheet, three-quarter view, plain background. ')
                  + G.LOOKS.get(look_pad, look_pad) + '.')
        u = gerar_img(png, prompt, refs, size)
        print(f'  [{pid}] {"ok" if u else "FALHOU"}')
        if u:
            E['urls'][pid] = u; salvar()
    # Sem ancora nao ha consistencia de personagem: os planos sairiam com pessoas
    # diferentes a cada quadro. Parar aqui e mais barato que descobrir na montagem.
    faltam = [p['id'] for p in elenco if p['id'] not in E['urls']]
    if faltam:
        return print(f'\n  ✗ âncora(s) sem imagem: {faltam}\n'
                     f'    Rode de novo — o que já ficou pronto é pulado.\n'
                     f'    (a Agnes devolve ~34% de 503; o retry às vezes não basta)')

    # -------- 2. KEYFRAMES A e B de cada plano
    # Dois frames por plano porque o movimento de camera E a diferenca entre eles
    # (gramatica.dica_keyframe_b diz o que muda em cada tipo de movimento).
    print('\n[2/5] KEYFRAMES')
    for pl in planos:
        look = pl.get('look', look_pad)
        for lado in ('a', 'b'):
            kid = f"p{pl['n']:02d}-{lado}"
            png = f'{D}/img/{kid}.png'
            if kid in E['urls'] and os.path.exists(png):
                continue
            teto = 4 if a.img == 'inemaimg' else 2      # flux2-klein aceita 4 refs
            refs = [E['urls'][r] for r in pl.get('refs', []) if r in E['urls']]
            amb = pl.get('ambiente')
            if amb and amb in E['urls']:
                refs.append(E['urls'][amb])
            refs = refs[:teto]
            prompt = G.prompt_de_imagem(pl, person, look, bool(refs))
            if lado == 'b':
                # O B DERIVA DO A. Antes o B era gerado do zero com as mesmas ancoras,
                # sem nunca ver o A — e tudo fora das ancoras era reinventado: o
                # snowboard trocou de cor e angulo, a luva "abriu os dedos". Com o A
                # como primeira referencia, o B e o MESMO quadro instantes depois.
                anterior = E['urls'].get(f"p{pl['n']:02d}-a")
                if anterior:
                    refs = [anterior] + refs[:teto - 1]
                prompt += (f" This is the exact same shot a few seconds later, same "
                           f"scene, same objects in the same places: "
                           f"{G.dica_keyframe_b(pl)}.")
            u = gerar_img(png, prompt, refs or None, size)
            print(f'  [{kid}] {"ok" if u else "FALHOU"}')
            if u:
                E['urls'][kid] = u; salvar()

    if a.so_imagens:
        # Folha de contato: ver os 20 planos lado a lado revela o que nenhuma imagem
        # isolada revela — quebra de continuidade, personagem que mudou de cara,
        # duas escalas iguais coladas. E o momento certo de corrigir.
        fc = M.folha_de_contato(D, planos, f'{D}/folha-contato.jpg')
        return print(f'\n>> folha de contato: {fc}')

    # -------- 3. CLIPES (antes da narracao: consistencia e ritmo primeiro)
    print('\n[3/5] CLIPES')
    lim = P.RATE_LIMIT_VID.get(a.video)
    feitos = 0
    # PLANO DE ESTADO (tipo_plano: tableau) nao vai para gerador nenhum: a camera se
    # move sobre a imagem parada. Cena sem movimento de sujeito nao tem o que animar, e
    # pedir animacao e o que fez o snowboard trocar de cor entre A e B.
    for pl in planos:
        n = pl['n']
        mp4 = f'{VD}/p{n:02d}.mp4'
        ka = f'{D}/img/p{n:02d}-a.png'
        if pl.get('tipo_plano') != 'tableau' or os.path.exists(mp4) or not os.path.exists(ka):
            continue
        fator = G.VELOCIDADE.get(pl.get('velocidade', 'normal'), 1.0)
        r = M.clipe_de_imagem(ka, mp4, max(1.0, pl['dur'] * fator),
                              pl.get('camera', 'zoom-in'), size)
        print(f'  [p{n:02d}] tableau (câmera sobre a imagem) '
              f'{"ok " + f"{P.dur(mp4):.1f}s · mov {M.movimento(mp4):.2f}" if r else "FALHOU"}')

    if a.video == 'agnes':
        # caminho em LOTE: submete tudo e colhe em paralelo (ver clipes_lote_agnes)
        itens = []
        for pl in planos:
            n = pl['n']
            mp4 = f'{VD}/p{n:02d}.mp4'
            ka, kb = f'{D}/img/p{n:02d}-a.png', f'{D}/img/p{n:02d}-b.png'
            if os.path.exists(mp4) or not os.path.exists(ka):
                continue
            fator = G.VELOCIDADE.get(pl.get('velocidade', 'normal'), 1.0)
            itens.append({'n': n, 'dest': mp4, 'fa': P.data_uri(ka),
                          'fb': P.data_uri(kb) if os.path.exists(kb) else P.data_uri(ka),
                          'prompt': (G.prompt_de_video_minimo if a.prompt_minimo else G.prompt_de_video)(pl),
                          'seg': max(1.0, pl['dur'] * fator)})
        if itens:
            print(f'  {len(itens)} clipes em lote (5/min de teto na criação)')
            mv = clipes_lote_agnes(itens)
            if mv:
                print(f'  movimento médio: {sum(mv.values())/len(mv):.2f}')
        planos_serial = []
    else:
        planos_serial = planos
    for pl in planos_serial:
        n = pl['n']
        mp4 = f'{VD}/p{n:02d}.mp4'
        if os.path.exists(mp4):
            continue
        ka, kb = f'{D}/img/p{n:02d}-a.png', f'{D}/img/p{n:02d}-b.png'
        if not os.path.exists(ka):
            print(f'  [p{n:02d}] sem keyframe A'); continue
        if a.video in P.PRECISA_URL_PUBLICA:
            fa = E['urls'].get(f'p{n:02d}-a', '')
            fb = E['urls'].get(f'p{n:02d}-b', '')
            if not fa.startswith('http'):
                print(f'  [p{n:02d}] {a.video} exige keyframe em URL pública — '
                      f'gere as imagens com --img agnes ou --img kie'); continue
        elif a.video in P.PRECISA_ARQUIVO_LOCAL:
            # CLI (kling): recebe CAMINHO e sobe o arquivo sozinho. Mandar data URI
            # aqui estoura o exec com "Argument list too long" — o base64 de um PNG
            # de 1MB nao cabe em argumento de linha de comando.
            fa, fb = ka, (kb if os.path.exists(kb) else ka)
        else:
            # o PNG local vem antes da URL guardada: a URL da Agnes e temporaria e
            # numa reexecucao no dia seguinte ela ja morreu. base64 funciona (medido).
            fa = P.data_uri(ka)
            fb = P.data_uri(kb) if os.path.exists(kb) else fa
        if lim and feitos and feitos % lim[0] == 0:
            print(f'  ... pausa {lim[1]}s (rate limit)'); time.sleep(lim[1])
        # velocidade: pede o clipe na duracao REAL de tela dividida pelo fator,
        # porque o slow motion na montagem estica o que foi gerado.
        fator = G.VELOCIDADE.get(pl.get('velocidade', 'normal'), 1.0)
        prompt_v = G.prompt_de_video(pl)
        r = gerar_vid(mp4, fa, fb, prompt_v, max(1.0, pl['dur'] * fator))
        feitos += 1
        if not r:
            print(f'  [p{n:02d}] FALHOU'); continue
        # PORTAO DE MOVIMENTO: clipe abaixo do limiar e foto com deriva — o defeito
        # que matou o primeiro corte. Uma segunda tentativa, com a ordem de movimento
        # reforcada, antes de deixar entrar na montagem.
        mv = M.movimento(mp4)
        if mv < LIMIAR_MOV:
            print(f'  [p{n:02d}] {P.dur(mp4):.1f}s · movimento {mv:.2f} < {LIMIAR_MOV} '
                  f'— refazendo com ordem de movimento reforçada')
            os.remove(mp4)
            reforco = (prompt_v + ' The subject is in constant visible motion from the '
                       'first frame to the last; nothing in the frame is frozen.')
            if lim:
                time.sleep(lim[1])
            r = gerar_vid(mp4, fa, fb, reforco, max(1.0, pl['dur'] * fator))
            feitos += 1
            mv = M.movimento(mp4) if r else 0.0
        print(f'  [p{n:02d}] {"ok " + f"{P.dur(mp4):.1f}s · mov {mv:.2f}" if r else "FALHOU"}'
              + ('  ⚠️ ainda parado' if r and mv < LIMIAR_MOV else ''))

    # -------- 3.5 AUDIO (trilha + SFX)
    # Baixa aqui, nao na montagem: a montagem e so ffmpeg, e um efeito que nao baixa
    # nao pode segurar o filme. Cada arquivo e cacheado em D/audio.
    print('\n[3.5/5] TRILHA E SFX')
    os.makedirs(f'{D}/audio', exist_ok=True)
    trilha = (S.get('audio', {}) or {}).get('trilha') or ''
    if trilha and not os.path.exists(trilha):
        # texto que nao e caminho e CONSULTA: 'cinematic tension' vira busca
        seg_total = sum(p['dur'] for p in planos)
        alvo = f'{D}/audio/trilha.wav'
        r = M.baixar_audio(trilha, alvo, tipo='musica', max_seg=max(60, seg_total * 2))
        print(f'  [trilha] {"ok" if r else "FALHOU"} — {trilha}')
        S.setdefault('audio', {})['trilha'] = r or ''
    elif trilha:
        print(f'  [trilha] arquivo local: {trilha}')
    pedidos = {s['q']: s['arq'] for pl in planos for s in M._sfx_do_plano(D, pl)}
    for q, arq in pedidos.items():
        if os.path.exists(arq):
            print(f'  [sfx] {q} (cache)'); continue
        # MEDIDO: --max-duration 10 zera a busca ("nenhum resultado") — o acervo do
        # Freesound tem foley gravado com cauda longa. Corta-se no ffmpeg depois,
        # que e de graca; filtrar na busca joga fora o efeito certo.
        print(f'  [sfx] {q} {"ok" if M.baixar_audio(q, arq, max_seg=45) else "FALHOU"}')

    # -------- 4. NARRACAO (encaixada na linha do tempo, ja com os clipes prontos)
    print('\n[4/5] NARRAÇÃO')
    voz = S.get('voz', 'rachel')
    E.setdefault('revisao', {})
    for pl in planos:
        txt = (pl.get('narracao') or '').strip()
        n = pl['n']
        if not txt:
            continue
        wav = f'{D}/narracao/p{n:02d}.wav'
        if os.path.exists(wav) and str(n) in E['dur']:
            continue
        txt_rev, mud = revisar(txt)
        if mud:
            print(f'  [p{n:02d}] revisão:', '; '.join(f'"{x}"→"{y}"' for x, y in mud))
            E['revisao'][str(n)] = [list(m) for m in mud]; salvar()
        d = narrar(wav, txt_rev, voz=voz)
        if d:
            E['dur'][str(n)] = d; salvar()
            print(f'  [p{n:02d}] {d:.1f}s')
    # A fala NAO manda mais na duracao. O ritmo escrito na decupagem e o que vale; a
    # locucao e encaixada na linha do tempo depois e pode atravessar planos. Medido: com
    # a fala mandando, 106s planejados viravam 150s e o corte agil morria.
    for pl in planos:
        falada = E['dur'].get(str(pl['n']))
        if falada and falada > pl['dur'] + 0.6:
            print(f"  [p{pl['n']:02d}] fala de {falada:.1f}s num plano de {pl['dur']}s "
                  f"— vai atravessar para o plano seguinte")

    # -------- 5. MONTAGEM
    print('\n[5/5] MONTAGEM')
    # plano sem clipe some do filme — e leva a fala junto. Melhor dizer do que
    # entregar um filme mais curto em silencio; reexecutar refaz so o que faltou.
    faltando = [p['n'] for p in planos if not os.path.exists(f"{VD}/p{p['n']:02d}.mp4")]
    if faltando:
        print(f'  ⚠️  {len(faltando)} plano(s) sem clipe e FORA do filme: {faltando}')
        print('      (rode de novo — as etapas prontas são puladas)')
    final = M.montar(D, planos, S, f'filme-{nome}-{os.path.basename(VD)[6:]}', vdir=VD)
    print(f'\n>> {final}' if final else '\n>> nada montado')


if __name__ == '__main__':
    main()
