"""Montagem: aplica em ffmpeg o que os geradores nao fazem.

Os geradores entregam um clipe cru por plano. O que separa "sequencia de clipes"
de "filme" esta nos §4/§6/§7 do doc de referencia e mora aqui:

  velocidade  (§4) slow motion e speed ramp nos beats de emocao/impacto
  texto       (§6) legenda palavra-a-palavra sincronizada com a fala; card; estatico
  audio       (§7) locucao + trilha com ducking sob a voz + SFX pontuais
  transicao   (§4) corte seco por padrao; zoom-punch como acento

Musica/ambiencia/SFX vem do inemavox (dlp) — ver baixar_audio().
"""
import json, os, re, shutil, subprocess

FONTE = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def _sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print('   ffmpeg:', r.stderr[-300:])
    return r.returncode == 0


def dur(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _escapar(t):
    return t.replace('\\', '').replace(':', '\\:').replace("'", "’").replace('%', '')


def _filtro_texto(pl, alvo):
    """§6: sans bold, branco com contorno, palavra-chave em ambar.

    palavra-a-palavra: divide a duracao do plano pelas palavras. Sincroniza com a
    fala porque a duracao do plano JA e a duracao da locucao (rodar.py garante isso).
    """
    # DESLIGADO: `texto_tela` (§6) veio do doc de referencia, que e um ANUNCIO —
    # palavra-a-palavra, card e CTA sao gramatica de propaganda. Em filme de historia
    # a legenda rouba a cena e nao foi pedida. O pipeline que funciona (videos-agnes)
    # nao desenha texto nenhum no video.
    if not os.environ.get('VIDEOANIMA_TEXTO_TELA'):
        return []
    t = pl.get('texto_tela')
    if not t:
        return []
    estilo = t.get('estilo', 'estatico')
    txt = t['conteudo']
    base = (f"fontfile={FONTE}:fontcolor=white:borderw=6:bordercolor=black@0.85:"
            f"x=(w-text_w)/2")
    if estilo == 'palavra-a-palavra':
        palavras = txt.split()
        passo = alvo / max(1, len(palavras))
        out = []
        for i, p in enumerate(palavras):
            cor = 'yellow' if p.isupper() else 'white'
            out.append(f"drawtext={base}:fontcolor={cor}:fontsize=88:y=h*0.62:"
                       f"text='{_escapar(p)}':enable='between(t,{i*passo:.2f},{(i+1)*passo:.2f})'")
        return out
    if estilo == 'card':
        linhas = _escapar(txt).replace('\n', '\\n')
        return [f"drawbox=x=0:y=h*0.34:w=iw:h=h*0.30:color=black@0.72:t=fill",
                f"drawtext={base}:fontsize=64:y=h*0.38:line_spacing=16:text='{linhas}'"]
    return [f"drawtext={base}:fontsize=72:y=h*0.78:text='{_escapar(txt)}'"]


def movimento(mp4):
    """Movimento medio entre quadros consecutivos (YAVG da diferenca).

    Referencia medida: os clipes do `videos-agnes` que funcionaram ficam entre 3 e 12.
    Abaixo de ~2 o clipe e uma foto com deriva — foi o defeito central do primeiro
    corte de montanha-leao (8 de 20 planos). Serve de portao antes da montagem.
    """
    r = subprocess.run(
        ['ffmpeg', '-hide_banner', '-nostats', '-i', mp4, '-vf',
         'tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG',
         '-f', 'null', '-'], capture_output=True, text=True)
    vs = [float(x.split('=')[1]) for x in re.findall(r'YAVG=[0-9.]+', r.stderr)]
    return sum(vs) / len(vs) if vs else 0.0


def clipe_de_imagem(png, dest, seg, camera='zoom-in', size='736x1312', fps=30):
    """Plano SEM geracao de video: a camera se move sobre a imagem parada.

    Por que existe: um plano que e um ESTADO (a prancha largada, a luva na neve, a
    floresta em silencio) nao tem o que animar. Mandar para o gerador e pedir que ele
    invente mudanca — e ele inventa: o snowboard trocou de cor e de angulo entre A e B,
    a luva "abriu os dedos". Aqui a imagem e a verdade e so a camera se move.

    Ganhos medidos ao trocar geracao por este caminho:
      - zero deriva de objeto (a imagem e literalmente a mesma)
      - zero risco de filtro de conteudo (nao passa por API)
      - duracao exata pedida (o gerador arredonda)
      - instantaneo e gratuito
    O preco: nao ha movimento de sujeito. Por isso so vale para plano de estado —
    usar em plano de acao devolve o slideshow que queriamos matar.
    """
    w, h = (int(x) for x in size.split('x'))
    n = max(2, int(round(seg * fps)))
    # trabalha numa versao ampliada: sobra margem para deslocar sem borda preta
    base = f'scale={int(w*1.25)}:{int(h*1.25)}:force_original_aspect_ratio=increase,crop={int(w*1.2)}:{int(h*1.2)}'
    mov = {
        # push-in lento: o mais seguro, sempre le como intencao
        'zoom-in':   f"zoompan=z='min(zoom+0.0009,1.18)':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        'zoom-punch': f"zoompan=z='min(zoom+0.0018,1.30)':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        # pan/tilt: zoom fixo e o quadro desliza
        'pan':       f"zoompan=z=1.12:d={n}:x='(iw-iw/zoom)*(on/{n})':y='ih/2-(ih/zoom/2)'",
        'tilt':      f"zoompan=z=1.12:d={n}:x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(on/{n})'",
        'tracking':  f"zoompan=z=1.12:d={n}:x='(iw-iw/zoom)*(on/{n})':y='ih/2-(ih/zoom/2)'",
        'tracking-traseiro': f"zoompan=z='min(zoom+0.0007,1.14)':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        # 'estatico' nao e imovel: uma deriva minima evita a sensacao de foto colada
        'estatico':  f"zoompan=z='min(zoom+0.0003,1.06)':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        'handheld':  f"zoompan=z=1.10:d={n}:x='iw/2-(iw/zoom/2)+sin(on/18)*6':y='ih/2-(ih/zoom/2)+cos(on/23)*5'",
    }.get(camera, f"zoompan=z='min(zoom+0.0009,1.18)':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'")
    vf = f'{base},{mov}:s={w}x{h}:fps={fps},format=yuv420p'
    ok = _sh(['ffmpeg', '-loglevel', 'error', '-loop', '1', '-i', png, '-vf', vf,
              '-t', f'{seg:.2f}', '-r', str(fps), '-c:v', 'libx264', '-crf', '20',
              '-pix_fmt', 'yuv420p', '-an', '-y', dest])
    return dest if ok else None


def slug(t):
    return ''.join(c if c.isalnum() else '-' for c in t.lower()).strip('-')[:40]


def _sfx_do_plano(D, pl):
    """Normaliza o campo `sfx` da decupagem para uma lista uniforme.

    Aceita `sfx: "lion roar"`, uma lista de strings, ou dicts com controle fino:
        sfx: [{q: rockfall, em: 1.2, vol: 0.5}]     # em = segundo dentro do plano
    """
    bruto = pl.get('sfx') or []
    if isinstance(bruto, (str, dict)):
        bruto = [bruto]
    out = []
    for s in bruto:
        if isinstance(s, str):
            s = {'q': s}
        q = (s.get('q') or '').strip()
        if not q:
            continue
        out.append({'q': q, 'em': float(s.get('em', 0)), 'vol': float(s.get('vol', 0.45)),
                    'arq': f'{D}/audio/sfx-{slug(q)}.wav'})
    return out


def _plano(D, pl, T, size='736x1312', vdir=None):
    """Um plano: velocidade + texto + fala, com duracao final consistente."""
    n = pl['n']
    vp = f'{vdir or D + "/video"}/p{n:02d}.mp4'
    ap = f'{D}/narracao/p{n:02d}.wav'
    if not os.path.exists(vp):
        return None
    from gramatica import VELOCIDADE
    fator = VELOCIDADE.get(pl.get('velocidade', 'normal'), 1.0)
    dv = dur(vp) / fator                      # slow motion estica o clipe gerado
    # a duracao e a ESCRITA na decupagem. A narracao nao manda mais: ela e encaixada
    # depois, na linha do tempo, e pode atravessar planos.
    alvo = pl['dur'] if pl.get('dur') else dv

    v = [f'scale={size.replace("x", ":")}:force_original_aspect_ratio=increase',
         f'crop={size.replace("x", ":")}',
         f'setpts={1/fator:.3f}*PTS']
    if pl.get('camera') == 'handheld':
        # §2 plano 18: tremor organico leve, feito na montagem e nao no gerador
        v.append("crop=iw*0.97:ih*0.97:(iw*0.03/2)+sin(t*7)*3:(ih*0.03/2)+cos(t*5)*3")
    if pl.get('transicao_saida') == 'zoom-punch':
        # §4: acento de impacto no fim do plano
        v.append(f"zoompan=z='if(gte(in_time,{max(0, alvo-0.4):.2f}),1.18,1)'"
                 f":d=1:fps=30:s={size}")
    v += _filtro_texto(pl, alvo)
    v.append(f'tpad=stop_mode=clone:stop_duration={max(0, alvo-dv)+0.2:.2f}')
    v.append(f'trim=0:{alvo:.2f}')
    v.append('setpts=PTS-STARTPTS')
    fc = '[0:v]' + ','.join(v) + '[v]'

    out = f'{T}/p{n:02d}.mp4'
    # A parte de video e MUDA. O audio nao mora mais no plano: ele e montado na linha
    # do tempo do filme (ver montar). Duas razoes medidas:
    #   - a fala deixa de esticar o plano; o ritmo escrito na decupagem sobrevive
    #     (antes: 106s planejados viravam 150s, 62s viravam 95s)
    #   - some o `adelay` por parte, que torcia os carimbos de tempo e fazia o concat
    #     abortar no meio (45s de 158s)
    cmd = ['ffmpeg', '-loglevel', 'error', '-i', vp, '-filter_complex', fc,
           '-map', '[v]', '-an', '-t', f'{alvo:.2f}',
           '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p',
           '-r', '30', '-avoid_negative_ts', 'make_zero', '-y', out]
    return out if _sh(cmd) else None


def montar(D, planos, spec, base, vdir=None):
    """Monta o filme: video mudo primeiro, audio depois, na linha do tempo.

    A ordem importa. Antes o audio era colado dentro de cada plano, e a fala mandava
    na duracao — o filme inflava e o ritmo escrito morria. Agora cada plano tem a
    duracao que a decupagem pediu, e a locucao e encaixada por cima, podendo
    atravessar planos. Consistencia e ritmo primeiro; a fala se acomoda.
    """
    T = f'{D}/tmp-{os.path.basename(vdir or "video")}'
    os.makedirs(T, exist_ok=True)
    size = spec.get('formato', {}).get('size', '736x1312')
    partes, offsets, t0 = [], {}, 0.0
    for pl in planos:
        p = _plano(D, pl, T, size, vdir)
        if not p:
            continue
        partes.append(p)
        offsets[pl['n']] = t0
        t0 += dur(p)
    if not partes:
        return None
    lst = f'{T}/lista.txt'
    open(lst, 'w').write('\n'.join(f"file '{p}'" for p in partes))
    bruto = f'{T}/bruto.mp4'
    _sh(['ffmpeg', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
         '-c:v', 'libx264', '-crf', '22', '-preset', 'medium', '-pix_fmt', 'yuv420p',
         '-an', '-y', bruto])
    dbruto = dur(bruto)

    # ---- audio na linha do tempo: cada fala e cada SFX entra no segundo em que cai
    entradas, ramos, nomes = [], [], []
    def por(arq, atraso_s, vol, rot):
        entradas.extend(['-i', arq])
        i = len(entradas) // 2
        ms = int(max(0, atraso_s) * 1000)
        ramos.append(f'[{i}:a]aresample=44100,volume={vol},adelay={ms}|{ms}[{rot}]')
        nomes.append(f'[{rot}]')
    for pl in planos:
        n = pl['n']
        if n not in offsets:
            continue
        wav = f'{D}/narracao/p{n:02d}.wav'
        if os.path.exists(wav):
            por(wav, offsets[n], 1.0, f'v{n}')
        for j, s in enumerate(_sfx_do_plano(D, pl)):
            if os.path.exists(s['arq']):
                por(s['arq'], offsets[n] + s['em'], s['vol'], f's{n}_{j}')
    final = f'{D}/{base}.mp4'
    LOUD = 'loudnorm=I=-14:TP=-1.5:LRA=11'
    if not nomes:
        _sh(['ffmpeg', '-loglevel', 'error', '-i', bruto, '-f', 'lavfi',
             '-i', 'anullsrc=r=44100:cl=stereo', '-c:v', 'copy', '-c:a', 'aac',
             '-shortest', '-movflags', '+faststart', '-y', final])
        print(f'   {dur(final):.1f}s · {os.path.getsize(final)/1048576:.1f}MB (sem áudio)')
        return final
    fc = ';'.join(ramos)
    fc += f";{''.join(nomes)}amix=inputs={len(nomes)}:duration=longest:normalize=0[falado]"
    trilha = spec.get('audio', {}).get('trilha')
    if trilha and os.path.exists(trilha):
        # a trilha carrega emocao, nao disputa com a voz: sidechain abaixa a musica
        # sozinha quando ha locucao. alimiter antes do loudnorm evita NaN (medido).
        entradas.extend(['-stream_loop', '-1', '-i', trilha])
        im = len(entradas) // 2 - 1
        fc += (f';[{im}:a]aresample=44100,volume=0.28[m];[falado]asplit=2[vz][key];'
               f'[m][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];'
               f'[vz][duck]amix=inputs=2:duration=first:normalize=0,'
               f'alimiter=limit=0.95,{LOUD}[a]')
    else:
        fc += f';[falado]alimiter=limit=0.95,{LOUD}[a]'
    ok = _sh(['ffmpeg', '-loglevel', 'error', '-i', bruto, *entradas,
              '-filter_complex', fc, '-map', '0:v', '-map', '[a]',
              '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-t', f'{dbruto:.2f}',
              '-movflags', '+faststart', '-y', final])
    # NUNCA entregar filme truncado em silencio (ja aconteceu: 26s no lugar de 150s)
    if not ok or dur(final) < dbruto * 0.95:
        print(f'   ⚠️ passo de áudio falhou ({dur(final):.1f}s de {dbruto:.1f}s) — entregando mudo')
        _sh(['ffmpeg', '-loglevel', 'error', '-i', bruto, '-c', 'copy',
             '-movflags', '+faststart', '-y', final])
    print(f'   {dur(final):.1f}s · {os.path.getsize(final)/1048576:.1f}MB')
    return final


def folha_de_contato(D, planos, dest, colunas=5):
    """Grade com o keyframe A de cada plano, numerado — a prova visual da continuidade.

    Usa so o A porque e ele que define a leitura do plano; o B e variacao de camera.
    """
    entradas, filtros, i = [], [], 0
    for pl in planos:
        png = f"{D}/img/p{pl['n']:02d}-a.png"
        if not os.path.exists(png):
            continue
        entradas += ['-i', png]
        rot = f"{pl['n']:02d} {pl['enquadramento'][:3]}/{pl['camera'][:9]}"
        filtros.append(f"[{i}:v]scale=360:-1,pad=iw:ih+44:0:44:color=black,"
                       f"drawtext=fontfile={FONTE}:text='{_escapar(rot)}':fontcolor=white:"
                       f"fontsize=26:x=10:y=8[c{i}]")
        i += 1
    if not i:
        return None
    linhas = (i + colunas - 1) // colunas
    fc = ';'.join(filtros) + ';' + ''.join(f'[c{k}]' for k in range(i))
    fc += f'xstack=inputs={i}:fill=black:layout='
    fc += '|'.join(f'{"+".join(["w0"]*(k % colunas)) or "0"}_'
                   f'{"+".join(["h0"]*(k // colunas)) or "0"}' for k in range(i)) + '[out]'
    ok = _sh(['ffmpeg', '-loglevel', 'error', *entradas, '-filter_complex', fc,
              '-map', '[out]', '-frames:v', '1', '-q:v', '3', '-y', dest])
    if ok:
        print(f'   folha de contato: {i} planos em {linhas}x{colunas}')
    return dest if ok else None


VOX = os.path.expanduser('~/projetos/inemavox')


def baixar_audio(consulta, dest, tipo='sfx', max_seg=None):
    """Musica/ambiencia/SFX pelo inemavox (regra global do usuario).

    Interface REAL (conferida): `sfx_v1.py` / `musica_v1.py --query ... --outdir ...
    --json` devolvem {'ok', 'path'}. A key vive em inemavox/.env e os scripts NAO a
    carregam sozinhos — quem chama exporta. Sem key do Pixabay nesta maquina, entao
    `--prefer freesound`; pedir pixabay so gasta uma tentativa que vai falhar.

    Cacheia: se `dest` ja existe, nao baixa de novo (rodar duas vezes nao rebaixa
    20 efeitos).
    """
    if os.path.exists(dest):
        return dest
    script = f'{VOX}/{"musica_v1.py" if tipo == "musica" else "sfx_v1.py"}'
    if not os.path.exists(script):
        print(f'   {script} nao encontrado — "{consulta}" fica de fora')
        return None
    env = dict(os.environ)
    try:
        for linha in open(f'{VOX}/.env'):
            linha = linha.strip()
            if linha and not linha.startswith('#') and '=' in linha:
                k, v = linha.split('=', 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    tmp = f'{os.path.dirname(dest)}/.baixando'
    cmd = ['python3', script, '--query', consulta, '--outdir', tmp,
           '--prefer', 'freesound', '--json']
    if max_seg:
        cmd += ['--max-duration', str(int(max_seg))]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=VOX, env=env, timeout=300)
    # o JSON vem indentado em varias linhas: ler a ultima linha pega so "}".
    bruto = r.stdout[r.stdout.find('{'):r.stdout.rfind('}') + 1]
    try:
        d = json.loads(bruto)
    except Exception:
        print(f'   "{consulta}": sem resposta utilizavel do inemavox '
              f'({(r.stderr or r.stdout or "")[-90:].strip()})')
        return None
    if not d.get('ok') or not d.get('path') or not os.path.exists(d['path']):
        print(f'   "{consulta}": {str(d.get("error"))[:90]}')
        return None
    # normaliza para WAV 44.1k estereo: o mixer nao deve lidar com mp3 de taxa variavel
    ok = _sh(['ffmpeg', '-loglevel', 'error', '-i', d['path'], '-ar', '44100',
              '-ac', '2', '-y', dest])
    shutil.rmtree(tmp, ignore_errors=True)
    return dest if ok else None


def folha_roteiro(D, planos, dest, colunas=5, larg=300):
    """Folha de contato ANOTADA: cada quadro com a ação e a narração embaixo.

    A folha simples (`folha_de_contato`) prova continuidade visual, mas nao deixa
    conferir se a imagem bate com a HISTORIA — e esse e o erro caro, porque so aparece
    no filme montado. Aqui o roteiro fica ao lado do quadro.

    Custo de revisao (medido): olhar um keyframe inteiro sai por ~1.290 tokens e o
    prompt dele por ~105; esta folha inteira sai por ~70 tokens por plano. E o jeito
    barato de revisar 50 planos — abrir imagem solta so no que a folha acusar.
    """
    from PIL import Image, ImageDraw, ImageFont
    import textwrap
    try:
        f_tit = ImageFont.truetype(FONTE, 15)
        f_txt = ImageFont.truetype(FONTE.replace('-Bold', ''), 13)
    except Exception:
        f_tit = f_txt = ImageFont.load_default()
    itens = [pl for pl in planos if os.path.exists(f"{D}/img/p{pl['n']:02d}-a.png")]
    if not itens:
        return None
    alt_img = int(larg * 1312 / 736)
    alt_txt = 130
    cel = (larg, alt_img + alt_txt)
    linhas = (len(itens) + colunas - 1) // colunas
    folha = Image.new('RGB', (colunas * cel[0], linhas * cel[1]), (16, 16, 18))
    d = ImageDraw.Draw(folha)
    for i, pl in enumerate(itens):
        x, y = (i % colunas) * cel[0], (i // colunas) * cel[1]
        im = Image.open(f"{D}/img/p{pl['n']:02d}-a.png").resize((larg, alt_img))
        folha.paste(im, (x, y))
        tipo = pl.get('tipo_plano', 'acao')
        cab = (f"{pl['n']:02d} · {pl.get('enquadramento','')[:3]}/{pl.get('camera','')[:9]}"
               f" · {tipo}" + (f" · {pl['dur']}s" if pl.get('dur') else ''))
        d.text((x + 6, y + alt_img + 4), cab, font=f_tit, fill=(255, 190, 90))
        yy = y + alt_img + 24
        for lin in textwrap.wrap((pl.get('acao') or '')[:130], int(larg/7.6))[:3]:
            d.text((x + 6, yy), lin, font=f_txt, fill=(170, 170, 175)); yy += 15
        nar = (pl.get('narracao') or '').strip()
        if nar:
            for lin in textwrap.wrap('♪ ' + nar[:110], int(larg/7.6))[:3]:
                d.text((x + 6, yy), lin, font=f_txt, fill=(120, 200, 255)); yy += 15
    folha.save(dest, quality=88)
    print(f'   folha-roteiro: {len(itens)} planos em {linhas}x{colunas}')
    return dest
