"""Provedores de IMAGEM e VIDEO atras de uma interface unica.

IMAGEM  : agnes | inemaimg | kie
VIDEO   : agnes | klingai | kie

Contrato:
    imagem(dest, prompt, refs, size)     -> url publica (ou 'file://...' se local) | None
    video(dest, kf_a, kf_b, prompt, seg) -> dest | None      (kf_* = url ou data URI)

As armadilhas MEDIDAS de cada API moram no adaptador dela, nunca no nucleo —
sao especificas do provedor e nao devem contaminar quem so quer um keyframe.
"""
import base64, hashlib, json, os, re, subprocess, time, urllib.request, urllib.error

FPS = 24
SEED = 12345
from gramatica import NEGATIVO_VIDEO as NEGATIVO_PADRAO


# ------------------------------------------------------------------ utilidades
def _env(caminho, chave):
    try:
        for linha in open(os.path.expanduser(caminho)):
            linha = linha.strip()
            if linha.startswith(chave + '='):
                return linha.split('=', 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def chave(nome):
    """Le a key dos lugares canonicos. Nunca imprime o valor."""
    locais = {
        'AGNES_API_KEY': ['~/projetos/agnes-nei/.env', '~/projetos/openpcbotv2/.env'],
        'KIE_API_KEY':   ['~/projetos/wifi/.env', '~/projetos/openpcbotv2/.env'],
        'FAL_KEY':       ['~/projetos/wifi/.env', '~/projetos/openpcbotv2/.env'],
    }[nome]
    for c in locais:
        v = _env(c, nome)
        if v:
            return v
    raise RuntimeError(f'{nome} nao encontrada em {locais}')


def _post(url, body, headers, timeout=400):
    r = urllib.request.Request(url, data=json.dumps(body).encode())
    for k, v in headers.items():
        r.add_header(k, v)
    r.add_header('Content-Type', 'application/json')
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())


def _get(url, headers, timeout=120):
    r = urllib.request.Request(url)
    for k, v in headers.items():
        r.add_header(k, v)
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())


def _baixar(url, dest, timeout=300):
    open(dest, 'wb').write(urllib.request.urlopen(url, timeout=timeout).read())
    return dest


def data_uri(png):
    return 'data:image/png;base64,' + base64.b64encode(open(png, 'rb').read()).decode()


def dur(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


# =================================================================== IMAGEM ===
def img_agnes(dest, prompt, refs=None, size='736x1312', tentativas=5):
    """Agnes agnes-image-2.1-flash — US$ 0.

    Medido (~70 chamadas, ~/projetos/agnes-nei/NOTAS-API.md):
    prompt em ingles (PT cai no filtro -> 400); `size` em PIXELS porque `ratio` e
    ignorado em img2img; no maximo 2 refs (5 viram confete); ~34% de 503 -> backoff;
    a URL de saida e temporaria, entao baixa na hora.
    """
    if refs and len(refs) > 2:
        refs = refs[:2]
    body = {'model': 'agnes-image-2.1-flash', 'prompt': prompt,
            'size': size, 'extra_body': {'response_format': 'url'}}
    if refs:
        body['extra_body']['image'] = refs
    h = {'Authorization': 'Bearer ' + chave('AGNES_API_KEY')}
    for t in range(1, tentativas + 1):
        try:
            d = _post('https://apihub.agnes-ai.com/v1/images/generations', body, h)
            u = d['data'][0]['url']
            _baixar(u, dest, 180)
            return u
        except Exception as e:
            print(f'    agnes img falha {t}: {str(e)[:90]}', flush=True)
            time.sleep(4 * t)
    return None


def img_inemaimg(dest, prompt, refs=None, size='736x1312', modelo='flux2-klein', base='http://localhost:8000'):
    """Servidor local (DGX). Custo zero e sem rate limit, mas exige o container no ar.

    Vantagem real sobre a Agnes: aceita imagens de referencia com LoRA
    (`qwen-edit-2511` + lora `face-swap`/`multiple-angles`), que segura identidade
    de personagem melhor do que img2img sem seed. Se houver refs, troca para o
    modelo de edicao automaticamente.
    """
    w, h = (int(x) for x in size.split('x'))
    # Seed derivada do PROMPT, nao constante: com seed fixa, apagar um keyframe ruim e
    # rodar de novo devolve a MESMA imagem — o retry vira ilusao de retry. Assim o
    # resultado continua reproduzivel (mesmo prompt -> mesma imagem) e mexer numa
    # palavra da acao e o que re-sorteia o plano.
    seed = int(hashlib.sha1(f'{prompt}|{size}'.encode()).hexdigest()[:8], 16)
    body = {'model': modelo, 'prompt': prompt, 'width': w, 'height': h, 'seed': seed}
    if refs:
        # o servidor espera as referencias como PNG em base64 CRU (sem prefixo data:).
        # As nossas chegam como 'file://...' (local) ou http (outro provedor) — converte.
        b64 = []
        for r in refs[:2]:
            try:
                if r.startswith('file://'):
                    dados = open(r[7:], 'rb').read()
                elif r.startswith('data:'):
                    b64.append(r.split(',', 1)[1]); continue
                else:
                    dados = urllib.request.urlopen(r, timeout=120).read()
                b64.append(base64.b64encode(dados).decode())
            except Exception as e:
                print(f'    ref ignorada ({str(e)[:60]})', flush=True)
        if b64:
            # flux2-klein aceita ate 4 referencias NATIVAMENTE. Trocar para qwen-edit
            # aqui faria o servidor descarregar e recarregar o modelo a cada imagem
            # que tem ou nao tem referencia — inviavel numa sequencia de 20 planos.
            body['images'] = b64
    try:
        d = _post(f'{base}/generate', body, {}, timeout=600)
    except Exception as e:
        print(f'    inemaimg falhou: {str(e)[:120]}', flush=True)
        print(f'    (servidor no ar? `cd ~/projetos/inemaimg && docker compose up -d`)', flush=True)
        return None
    b64 = d.get('image') or (d.get('images') or [None])[0]
    if not b64:
        return None
    open(dest, 'wb').write(base64.b64decode(b64))
    return 'file://' + os.path.abspath(dest)


def img_kie(dest, prompt, refs=None, size='736x1312', modelo='nano-banana-2'):
    """kie.ai — createTask + polling em recordInfo (shape confirmado em call site local).

    Aceita `aspect_ratio` (nao pixels). Custo ~US$0,02-0,09/imagem.
    """
    ratio = _ratio(size)
    body = {'model': modelo, 'input': {'prompt': prompt, 'aspect_ratio': ratio}}
    if refs:
        body['input']['image_urls'] = [r for r in refs if r.startswith('http')][:2]
    h = {'Authorization': 'Bearer ' + chave('KIE_API_KEY')}
    try:
        j = _post('https://api.kie.ai/api/v1/jobs/createTask', body, h)
    except Exception as e:
        print(f'    kie img createTask: {str(e)[:120]}', flush=True)
        return None
    tid = (j.get('data') or {}).get('taskId') or j.get('taskId')
    if not tid:
        return None
    u = _kie_poll(tid, h, limite=600)
    return _baixar(u, dest) and u if u else None


def _kie_poll(task_id, headers, limite=1200):
    t0 = time.time()
    while time.time() - t0 < limite:
        try:
            d = _get(f'https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}', headers)
            d = d.get('data', d)
            st = str(d.get('state') or d.get('status') or '').upper()
            if st in ('SUCCESS', 'COMPLETED', 'DONE'):
                res = d.get('resultJson')
                res = json.loads(res) if isinstance(res, str) else (res or {})
                return (res.get('resultUrls') or res.get('urls') or [None])[0]
            if st in ('FAILED', 'FAIL', 'ERROR'):
                print(f'    kie falhou: {json.dumps(d)[:160]}', flush=True)
                return None
        except Exception:
            pass
        time.sleep(6)
    return None


def _ratio(size):
    w, h = (int(x) for x in size.split('x'))
    for r, v in (('9:16', 9 / 16), ('16:9', 16 / 9), ('1:1', 1.0), ('4:3', 4 / 3), ('3:4', 3 / 4)):
        if abs(w / h - v) < 0.08:
            return r
    return '9:16'


# ==================================================================== VIDEO ===
def _frames(seg):
    """Agnes: 8n+1, teto 441 (18.4s @24fps)."""
    n = round((seg * FPS - 1) / 8)
    return max(9, min(441, int(n * 8 + 1)))


def agnes_submit(kf_a, kf_b, prompt, seg, negativo=None, tentativas=4):
    """So SUBMETE o clipe e devolve o video_id (a Agnes e assincrona).

    Separado de `agnes_colher` para permitir LOTE: com o laco serial
    (submete -> espera -> submete) cada clipe custava 170s de parede, dos quais
    ~140s eram espera ociosa. Submetendo todos e colhendo depois, o tempo de
    parede cai para o teto do rate limit + a geracao do ultimo lote.
    """
    body = {'model': 'agnes-video-v2.0', 'prompt': prompt,
            'num_frames': _frames(seg), 'frame_rate': FPS, 'seed': SEED,
            'width': 736, 'height': 1312,
            'negative_prompt': negativo or NEGATIVO_PADRAO,
            'extra_body': {'image': [kf_a, kf_b], 'mode': 'keyframes'}}
    h = {'Authorization': 'Bearer ' + chave('AGNES_API_KEY')}
    for t in range(1, tentativas + 1):
        try:
            d = _post('https://apihub.agnes-ai.com/v1/videos', body, h, timeout=300)
            return d.get('video_id') or d.get('task_id') or d.get('id')
        except urllib.error.HTTPError as e:
            print(f'    agnes submit HTTP {e.code}', flush=True)
            time.sleep(70 if e.code == 429 else 6 * t)
        except Exception as e:
            print(f'    agnes submit: {str(e)[:90]}', flush=True)
            time.sleep(6 * t)
    return None


def agnes_estado(vid, dest):
    """Consulta UMA vez. -> 'pronto' (ja baixado) | 'erro' | 'esperando'.

    O polling tambem tem rate limit proprio (medido no videos-agnes), entao quem
    chama espaca as consultas — nunca consultar em rajada.
    """
    h = {'Authorization': 'Bearer ' + chave('AGNES_API_KEY')}
    try:
        d = _get('https://apihub.agnes-ai.com/agnesapi?video_id=' + vid, h)
    except Exception:
        return 'esperando'
    st = d.get('status')
    if st == 'completed':
        u = d.get('url') or (d.get('data') or [{}])[0].get('url') or d.get('video_url')
        if not u:
            return 'erro'
        try:
            _baixar(u, dest)
            return 'pronto'
        except Exception as e:
            print(f'    agnes download: {str(e)[:80]}', flush=True)
            return 'erro'
    return 'erro' if st == 'failed' else 'esperando'


def vid_agnes(dest, kf_a, kf_b, prompt, seg, tentativas=4, negativo=None):
    """Agnes agnes-video-v2.0 em modo keyframes [A, B] — US$ 0. Caminho serial.

    Rate limit REAL de 5 req/min (429) na criacao E no polling. O `size` da resposta
    mente (pede 736x1312, entrega arredondado): medir com ffprobe se importar.
    """
    vid = agnes_submit(kf_a, kf_b, prompt, seg, negativo, tentativas)
    if not vid:
        return None
    t0 = time.time()
    while time.time() - t0 < 1800:
        e = agnes_estado(vid, dest)
        if e == 'pronto':
            return dest
        if e == 'erro':
            return None
        time.sleep(12)
    return None


def vid_klingai(dest, kf_a, kf_b, prompt, seg,
                endpoint='fal-ai/kling-video/v3/4k/image-to-video'):
    """Kling — roteado por fal.ai.

    NAO existe key propria de Kling nesta maquina; o acesso e via fal.ai (`FAL_KEY`),
    que e um dos caminhos oficiais (fal / kie / Replicate / Freepik). Ele anima UMA
    imagem (start_image_url), entao o keyframe B nao e usado: entra so como descricao
    de para onde a cena vai. Duracao 3-15s. ~US$0,076-0,217/s conforme o tier.
    """
    seg = max(3, min(15, round(seg)))
    body = {'prompt': prompt, 'start_image_url': kf_a,
            'duration': seg, 'aspect_ratio': '9:16'}
    h = {'Authorization': 'Key ' + chave('FAL_KEY')}
    try:
        j = _post(f'https://queue.fal.run/{endpoint}', body, h, timeout=300)
    except Exception as e:
        print(f'    kling/fal submit: {str(e)[:140]}', flush=True)
        return None
    status_url = j.get('status_url')
    resp_url = j.get('response_url')
    if not status_url:
        return None
    t0 = time.time()
    while time.time() - t0 < 1800:
        try:
            d = _get(status_url, h)
            st = str(d.get('status', '')).upper()
            if st == 'COMPLETED':
                r = _get(resp_url, h)
                u = ((r.get('video') or {}).get('url')
                     or (r.get('videos') or [{}])[0].get('url'))
                return _baixar(u, dest) if u else None
            if st in ('FAILED', 'ERROR'):
                print(f'    kling/fal falhou: {json.dumps(d)[:160]}', flush=True)
                return None
        except Exception:
            pass
        time.sleep(10)
    return None


def vid_kling(dest, kf_a, kf_b, prompt, seg, modelo='kling-video-v3_0',
              resolucao='720p'):
    """Kling DIRETO pela assinatura do usuario (CLI `kling`), sem fal no meio.

    MEDIDO em `kling who_am_i` (conta 3422648, Pro/SVIP) — a lista de ARGUMENTOS
    engana; o que decide e a lista de INPUTS de cada modelo:
      v3_0_turbo : so `first_image`  -> sem frame final (passar --tailImage da
                   HTTP 400 "Duplicate input 'first_image'")
      v2_5/v2_6  : tem `tail_image`, mas duracao so 5 ou 10s
      v3_0       : tem `tail_image` E duracao livre 3-15s  <- unico que serve
    O keyframe B nao e enfeite: sem ele o movimento de camera vira so texto no
    prompt e a gramatica A->B (dica_keyframe_b) se perde.

    Arquivo local vai direto (o CLI sobe sozinho) — nao precisa de URL publica.
    720p por regra do usuario: 1080p/4k so sob pedido explicito.
    """
    seg = max(3, min(15, round(seg)))
    cmd = ['kling', 'image_to_video', '--image', kf_a]
    if kf_b and os.path.exists(kf_b):
        cmd += ['--tailImage', kf_b]
    cmd += ['--model', modelo, '--duration', str(seg), '--resolution', resolucao,
            '--poll', '600', prompt]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500)
    except subprocess.TimeoutExpired:
        print('    kling: timeout no poll', flush=True)
        return None
    saida = r.stdout + r.stderr
    # o job e PAGO e nao cancela: guardar a resposta crua antes de parsear, senao
    # um parse quebrado perde o generation_id e os creditos junto (regra do repo
    # klingai-nei).
    open(dest + '.kling.json', 'w').write(saida)
    u = None
    for m in re.finditer(r'https?://[^\s"\'<>\\]+', saida):
        if any(e in m.group(0).lower() for e in ('.mp4', 'video')):
            u = m.group(0).rstrip('.,')
    if not u:
        print(f'    kling sem url (resposta em {dest}.kling.json)', flush=True)
        return None
    try:
        return _baixar(u, dest, 600)      # as URLs do Kling expiram em 24h
    except Exception as e:
        print(f'    kling download: {str(e)[:90]}', flush=True)
        return None


def vid_kie(dest, kf_a, kf_b, prompt, seg, modelo='veo3_fast'):
    """kie.ai como hub de video (veo3_fast, veo3, sora2, kling, wan...).

    Mesmo fluxo createTask/recordInfo da imagem. image-to-video a partir de UM frame.
    Veo3 Fast ~US$0,40/clipe; Veo3 ~US$2; Sora2 ~US$0,15/10s.
    """
    body = {'model': modelo, 'input': {'prompt': prompt, 'aspect_ratio': '9:16',
                                       'image_urls': [kf_a] if kf_a.startswith('http') else []}}
    h = {'Authorization': 'Bearer ' + chave('KIE_API_KEY')}
    try:
        j = _post('https://api.kie.ai/api/v1/jobs/createTask', body, h)
    except Exception as e:
        print(f'    kie vid createTask: {str(e)[:140]}', flush=True)
        return None
    tid = (j.get('data') or {}).get('taskId') or j.get('taskId')
    if not tid:
        return None
    u = _kie_poll(tid, h, limite=1800)
    return _baixar(u, dest) if u else None


# ================================================================== registro ==
IMAGEM = {'agnes': img_agnes, 'inemaimg': img_inemaimg, 'kie': img_kie}
VIDEO = {'agnes': vid_agnes, 'kling': vid_kling, 'klingai': vid_klingai, 'kie': vid_kie}

# Custo estimado, para o preview antes de gastar. Fonte: wiki cerebro-vip.
CUSTO_IMG = {'agnes': 0.0, 'inemaimg': 0.0, 'kie': 0.05}          # US$ por imagem
# 'kling' = assinatura Pro/SVIP do usuario: consome CREDITOS do plano, nao dolar
# avulso — por isso 0.0 aqui; o preview de custo nao mede credito.
CUSTO_VID_SEG = {'agnes': 0.0, 'kling': 0.0, 'klingai': 0.076, 'kie': 0.05}
PRECISA_URL_PUBLICA = {'klingai', 'kie'}   # nao aceitam data URI de keyframe
PRECISA_ARQUIVO_LOCAL = {'kling'}          # CLI: recebe caminho e sobe sozinho
RATE_LIMIT_VID = {'agnes': (4, 65)}        # (clipes, pausa_seg)
# Kling Pro/SVIP: sem limite de tarefas concorrentes (README klingai-nei)
