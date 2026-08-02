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
    da = dur(ap) if os.path.exists(ap) else 0
    alvo = max(dv, da + 0.4, pl['dur'])

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
    # §7: SFX do plano. Ja baixados em D/audio por rodar.py — aqui e so mixagem,
    # nunca rede: montagem que baixa arquivo trava o filme por causa de um efeito.
    sfx = [s for s in _sfx_do_plano(D, pl) if os.path.exists(s['arq'])]
    entradas, ramos, nomes = [], [], []
    if da:
        entradas += ['-i', ap]
        ramos.append(f'[{len(entradas)//2}:a]apad=pad_dur={max(0, alvo-da):.2f},'
                     f'atrim=0:{alvo:.2f},asetpts=PTS-STARTPTS[voz]')
        nomes.append('[voz]')
    for i, s in enumerate(sfx):
        entradas += ['-i', s['arq']]
        # adelay posiciona o efeito no beat; o efeito acompanha o plano, nao o filme
        ramos.append(f"[{len(entradas)//2}:a]volume={s['vol']},"
                     f"adelay={int(s['em']*1000)}|{int(s['em']*1000)},"
                     f"atrim=0:{alvo:.2f},asetpts=PTS-STARTPTS[s{i}]")
        nomes.append(f'[s{i}]')
    if nomes:
        fc += ';' + ';'.join(ramos)
        if len(nomes) > 1:
            # normalize=0: sem isso o amix DIVIDE o volume da voz pelo numero de
            # entradas, e cada SFX adicionado deixa a narracao mais baixa.
            fc += (f";{''.join(nomes)}amix=inputs={len(nomes)}:duration=first:"
                   f"normalize=0[a]")
        else:
            fc += f';{nomes[0]}anull[a]'
        cmd = ['ffmpeg', '-loglevel', 'error', '-i', vp, *entradas,
               '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-t', f'{alvo:.2f}']
    else:
        cmd = ['ffmpeg', '-loglevel', 'error', '-i', vp, '-f', 'lavfi',
               '-i', 'anullsrc=r=44100:cl=stereo', '-filter_complex', fc,
               '-map', '[v]', '-map', '1:a', '-t', f'{alvo:.2f}']
    cmd += ['-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p',
            '-r', '30', '-c:a', 'aac', '-y', out]
    return out if _sh(cmd) else None


def montar(D, planos, spec, base, vdir=None):
    # tmp por PROVEDOR: dois runs simultaneos (agnes e kling) escreviam p07.mp4 no
    # mesmo lugar e um levava o clipe do outro para o filme final.
    T = f'{D}/tmp-{os.path.basename(vdir or "video")}'
    os.makedirs(T, exist_ok=True)
    size = spec.get('formato', {}).get('size', '736x1312')
    partes = [p for p in (_plano(D, pl, T, size, vdir) for pl in planos) if p]
    if not partes:
        return None
    lst = f'{T}/lista.txt'
    open(lst, 'w').write('\n'.join(f"file '{p}'" for p in partes))
    bruto = f'{T}/bruto.mp4'
    _sh(['ffmpeg', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
         '-c:v', 'libx264', '-crf', '22', '-preset', 'medium', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '160k', '-y', bruto])

    final = f'{D}/{base}.mp4'
    trilha = spec.get('audio', {}).get('trilha')
    # MEDIDO: sem normalizar, o filme sai a -30,7 LUFS integrado — plataforma social
    # entrega perto de -14, entao no celular fica quase inaudivel. TTS e SFX chegam
    # cada um num nivel; so o passo final ve o programa inteiro e pode nivelar.
    LOUD = 'loudnorm=I=-14:TP=-1.5:LRA=11'
    if trilha and os.path.exists(trilha):
        # §7: a trilha existe para carregar emocao, nao para disputar com a voz.
        # sidechaincompress abaixa a musica sozinha quando ha locucao.
        _sh(['ffmpeg', '-loglevel', 'error', '-i', bruto, '-stream_loop', '-1', '-i', trilha,
             '-filter_complex',
             '[1:a]volume=0.28[m];[0:a]asplit=2[voz][key];'
             '[m][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];'
             f'[voz][duck]amix=inputs=2:duration=first:dropout_transition=0,{LOUD}[a]',
             '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k',
             '-movflags', '+faststart', '-shortest', '-y', final])
    else:
        _sh(['ffmpeg', '-loglevel', 'error', '-i', bruto, '-af', LOUD,
             '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k',
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
