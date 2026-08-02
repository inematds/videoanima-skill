"""Narracao local via inemavox (chatterbox), voz padrao `rachel`.

Reusa a revisao de diccao ja escrita em videos-agnes: antes do TTS, numeros/moeda
por extenso e abreviacoes de digitacao, porque o chatterbox le "R$60" como
"erre cifrao sessenta". Ela NAO corrige o portugues — so o que a locucao erra —
e imprime cada mudanca, para nada ser editado em silencio.
"""
import json, os, subprocess, sys, urllib.request, uuid

VOX = 'http://localhost:8010'
REFS = os.path.expanduser('~/projetos/timesmkt3/media/voice-refs')

sys.path.insert(0, os.path.expanduser('~/projetos/videos-agnes'))
try:
    from revisao import revisar          # noqa: F401  (reexportado para rodar.py)
except ImportError:                       # videos-agnes ausente: segue sem revisao
    def revisar(t):
        return t, []


def dur(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def narrar(dest, texto, voz='rachel'):
    ref = f'{REFS}/{voz}.wav'
    if not os.path.exists(ref):
        print(f'  voz "{voz}" nao existe em {REFS}')
        return None
    cfg = {'text': texto, 'engine': 'chatterbox', 'voice': voz, 'lang': 'pt'}
    b = '----inema' + uuid.uuid4().hex
    corpo = b''.join([
        f'--{b}\r\nContent-Disposition: form-data; name="config_json"\r\n\r\n{json.dumps(cfg)}\r\n'.encode(),
        f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{voz}.wav"\r\n'
        f'Content-Type: audio/wav\r\n\r\n'.encode() + open(ref, 'rb').read() + b'\r\n',
        f'--{b}--\r\n'.encode()])
    r = urllib.request.Request(f'{VOX}/api/jobs/tts/upload', data=corpo)
    r.add_header('Content-Type', f'multipart/form-data; boundary={b}')
    try:
        j = json.loads(urllib.request.urlopen(r, timeout=120).read())
    except Exception as e:
        print(f'  inemavox indisponivel ({str(e)[:70]}) — daemon em localhost:8010?')
        return None
    jid = j.get('job_id') or j.get('id')
    import time
    t0 = time.time()
    while time.time() - t0 < 900:
        d = json.loads(urllib.request.urlopen(f'{VOX}/api/jobs/{jid}', timeout=30).read())
        st = d.get('status')
        if st in ('completed', 'done', 'finished'):
            open(dest, 'wb').write(
                urllib.request.urlopen(f'{VOX}/api/jobs/{jid}/audio', timeout=180).read())
            return dur(dest)
        if st in ('failed', 'error'):
            return None
        time.sleep(5)
    return None
