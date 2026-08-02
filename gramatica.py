"""Gramatica cinematografica destilada de doc/analise-estilo-fbvideo.md.

O documento e a decupagem plano-a-plano de um video que funcionou. O que transfere
NAO e a forma daquele anuncio (apresentador, card de workshop, "clique em saiba mais"),
e sim o VOCABULARIO por plano — enquadramento, angulo, movimento de camera, velocidade,
duracao — mais o ritmo de corte e as camadas de look/texto/audio.

Aqui esse vocabulario vira: (a) fragmentos de prompt em ingles para o gerador de imagem,
(b) descricao de movimento para o gerador de video, (c) numeros de ritmo para validacao.
"""

# ---------------------------------------------------------------- enquadramento
# §2 do doc usa 4 escalas. Elas mudam o que a imagem PRECISA conter.
ENQUADRAMENTO = {
    'detalhe':  'extreme close-up detail shot, tight framing on the single subject detail',
    # MEDIDO: dizer "head and shoulders, face fills the frame" PEDE um rosto — num
    # close de objeto (a mochila caindo, plano 11 de montanha-leao) o gerador inventa
    # uma pessoa que a acao nao tem. A escala tem que falar de enquadramento, nao de
    # anatomia; quem poe gente no quadro e a acao.
    'close':    'close-up shot, the subject fills much of the frame, tight framing',
    'medio':    'medium shot, subject from the waist up, environment readable behind',
    'geral':    'wide establishing shot, full figures small in a large landscape',
}

# ---------------------------------------------------------------- angulo
ANGULO = {
    'nivel':          'eye-level camera',
    'plongee':        'high angle camera looking down at the subject',
    'contra-plongee': 'low angle camera looking up at the subject, sky behind',
    'rente-ao-chao':  'ground-level camera almost touching the ground',
}

# ---------------------------------------------------------------- camera
# Vira texto do prompt de VIDEO (o par de keyframes ja carrega o resto).
# from/to descreve o que muda entre keyframe A e B — e por isso que dois
# keyframes bastam: o movimento e a diferenca entre eles.
# MEDIDO (pos-mortem de montanha-leao): a dica do keyframe B ia para o gerador em
# PORTUGUES e falando da nossa convencao ("B desloca o enquadramento"). O modelo nao
# tem como agir sobre isso — e na Agnes prompt em PT ainda cai no filtro (400). Pior:
# ela so descrevia CAMERA. Com o sujeito na mesma pose nas duas pontas, nao ha o que
# interpolar e o clipe sai parado (8 de 20 planos abaixo de 2,0 de movimento).
# Agora a dica vai em INGLES e fala primeiro do SUJEITO, depois da camera.
CAMERA = {
    'estatico':    ('locked-off static camera, no camera movement',
                    'the camera has not moved at all, but the subject has clearly '
                    'continued the action and is now in a visibly different pose'),
    'pan':         ('smooth horizontal pan following the action',
                    'the subject has moved further along its path and the framing has '
                    'shifted sideways to follow it'),
    'tilt':        ('vertical tilt revealing the scene',
                    'the framing has tilted up or down to reveal more of the scene, and '
                    'the subject has continued moving'),
    'tracking':    ('tracking shot moving with the subject, camera travels alongside',
                    'the subject has travelled forward through the scene, mid-stride, '
                    'the background clearly further along'),
    'tracking-traseiro': ('tracking shot from behind the subject, following',
                    'seen from behind, the subject is further away down the path, '
                    'mid-stride'),
    'zoom-in':     ('slow push-in, camera creeps closer',
                    'the framing is noticeably tighter on the subject, which has also '
                    'shifted its pose'),
    'zoom-punch':  ('sudden aggressive zoom punch-in for impact',
                    'the framing is much tighter, filling the frame with the subject at '
                    'the peak of the action'),
    'handheld':    ('subtle handheld camera, slight organic shake',
                    'the camera has drifted slightly and the subject has clearly '
                    'continued the action into a different pose'),
}

# Negative prompt de VIDEO. Padrao da industria contra o defeito que nos pegou: os
# templates oficiais do LTX-2 trazem "still frame, frames" e o do Wan 2.2 traz
# 静态 / 画面静止 / 静止不动的画面 (estatico / imagem parada / quadro imovel).
NEGATIVO_VIDEO = ('still frame, static image, motionless, frozen, no motion, slideshow, '
                  'photograph, morphing, warping, distorted anatomy, extra limbs, '
                  'blurry, low quality, watermark, subtitles, text overlay')

# ---------------------------------------------------------------- velocidade
# §4: speed ramp nos pulos, slow motion nos momentos emocionais.
# Aplicado na montagem (ffmpeg setpts), nao no gerador.
VELOCIDADE = {
    'normal':     1.0,
    'slow':       0.5,     # slow motion pleno
    'speed-ramp': 0.65,    # entra normal, desacelera no impacto
}

# ---------------------------------------------------------------- ritmo (§3)
# Numeros medidos no video de referencia. Servem de sanidade, nao de camisa de forca.
RITMO = {
    'media_por_plano': 3.7,
    'minimo_util': 1.0,       # abaixo disso o espectador nao le o plano
    'maximo_sem_cortar': 19.0,  # so cabe em plano expositivo (falante em cena)
    'curva': 'cadenciado (narrativa) -> expositivo (fala direta) -> montagem rapida (clima)',
}

# ---------------------------------------------------------------- look (§5)
# Look e por BLOCO, nao por plano — e o que da unidade a sequencia.
LOOKS = {
    'sertao-golden-hour': ('warm orange and amber palette, low golden-hour sun, high contrast, '
                           'dusty haze, cinematic film grain'),
    'intimista-estudio':  ('soft key light with cool blue rim from behind, dark low-noise '
                           'background, shallow depth of field'),
    'showcase-saturado':  ('high saturation, punchy modern 3D animation look, crisp rim light'),
    'noturno-frio':       ('cool blue night palette, moonlight key, deep shadows, soft mist'),
    'neutro-cinema':      ('naturalistic cinematic color, soft key light, restrained saturation'),
}


def prompt_de_imagem(plano, personagens, look, refs_usadas):
    """Monta o prompt em INGLES de um keyframe.

    Ordem importa: acao -> enquadramento -> angulo -> look. O descritor de estilo vem
    por ultimo e so com termos ESTETICOS (luz/cor/render). Termos anatomicos no estilo
    ("expressive eyes", "fur") injetam personagem em plano de paisagem — erro medido.
    """
    partes = [plano['acao'].strip().rstrip('.') + '.']
    partes.append(ENQUADRAMENTO[plano['enquadramento']] + '.')
    partes.append(ANGULO[plano['angulo']] + '.')
    # A descricao textual do personagem entra SEMPRE, com ou sem referencia. Antes ela
    # era descartada quando havia ref (`and not refs_usadas`) — e a referencia sozinha
    # nao trava identidade (medido no README do videos-agnes: "o rosto muda"). Era a
    # causa da inconsistencia de figurino e do porte do cao oscilando.
    for pid in plano.get('refs', []):
        if pid in personagens:
            partes.append(personagens[pid].strip().rstrip('.') + '.')
    if refs_usadas:
        partes.append('Keep exactly the same characters as in the reference images: '
                      'same faces, same hair, same clothes, same proportions.')
    partes.append('Exactly one of each character, one head each, natural anatomy.')
    partes.append(LOOKS.get(look, look) + '.')
    return ' '.join(partes)


def prompt_de_video(plano):
    """Descreve para o gerador o movimento entre os keyframes A e B.

    Estrutura copiada do template oficial de image-to-video do LTX-2: acao continua
    primeiro, o que MUDA no meio do plano, e so entao a camera. O nosso prompt antigo
    tinha ~30 palavras e nenhuma frase sobre o sujeito se mover — o modelo entregava
    a foto de volta.
    """
    mov, _ = CAMERA[plano['camera']]
    partes = [plano['acao'].strip().rstrip('.') + '.']
    fim = (plano.get('acao_b') or '').strip().rstrip('.')
    if fim:
        # o "para onde vai" e o que da ao gerador um caminho a percorrer
        partes.append(f'Through the shot the action continues: {fim}.')
    partes.append(f'{mov}.')
    partes.append('Continuous fluid motion from the first frame to the last, the '
                  'subject moves the whole time, animated film movement, '
                  'consistent characters and style.')
    if plano.get('velocidade') == 'slow':
        partes.append('Deliberate, weighty slow motion.')
    elif plano.get('velocidade') == 'speed-ramp':
        partes.append('The motion accelerates and then snaps into impact.')
    return ' '.join(partes)


def dica_keyframe_b(plano):
    """O que precisa MUDAR do keyframe A para o B.

    Prioridade para o `acao_b` escrito na decupagem (o fim do gesto daquele plano);
    a dica de camera e o fallback generico. Em INGLES — vai direto para o gerador.
    """
    fim = (plano.get('acao_b') or '').strip().rstrip('.')
    if fim:
        return f'{fim}, and {CAMERA[plano["camera"]][1]}'
    return CAMERA[plano['camera']][1]


def validar_ritmo(planos):
    """Devolve avisos (nao erros) sobre o ritmo — §3 do doc."""
    avisos = []
    if not planos:
        return ['decupagem sem planos']
    durs = [p['dur'] for p in planos]
    media = sum(durs) / len(durs)
    if media > 6:
        avisos.append(f'media {media:.1f}s/plano — arrastado (referencia: {RITMO["media_por_plano"]}s). '
                      'Cortar mais ou encurtar planos.')
    if media < 2:
        avisos.append(f'media {media:.1f}s/plano — frenetico; so funciona em bloco de montagem.')
    for p in planos:
        if p['dur'] < RITMO['minimo_util']:
            avisos.append(f"plano {p['n']}: {p['dur']}s e curto demais para ser lido.")
        if p['dur'] > RITMO['maximo_sem_cortar']:
            avisos.append(f"plano {p['n']}: {p['dur']}s sem corte — so se houver fala direta em cena.")
    if len({p['enquadramento'] for p in planos}) < 2:
        avisos.append('todos os planos na mesma escala — alternar detalhe/close/medio/geral '
                      'e o que cria ritmo visual (§2).')
    return avisos
