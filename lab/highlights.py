"""Encontra os momentos mais fortes da live a partir do áudio e da fala."""
import re

import numpy as np

GATILHOS = [
    "kkk", "haha", "hahaha", "rsrs", "meu deus", "caramba", "caraca", "nossa", "não acredito",
    "nao acredito", "mano", "olha isso", "que isso", "gente", "sério", "serio", "incrível",
    "absurdo", "socorro", "eita", "vamo", "bora", "ganhei", "perdi", "clipa", "clip",
    "inacreditável", "loucura", "pqp", "puts", "uau", "nunca", "primeira vez", "segredo",
    "dica", "cuidado", "verdade", "polêmica", "briga", "olha só", "presta atenção",
]


def _media_movel(x, n):
    if n <= 1:
        return x.astype(np.float32)
    return np.convolve(x, np.ones(n) / n, mode="same").astype(np.float32)


def _mediana_movel(x, n):
    n = max(3, n | 1)
    if len(x) <= n:
        return np.full_like(x, np.median(x))
    pad = n // 2
    xp = np.pad(x, (pad, pad), mode="edge")
    janelas = np.lib.stride_tricks.sliding_window_view(xp, n)
    out = np.empty(len(x), np.float32)
    for i in range(0, len(x), 20000):
        out[i:i + 20000] = np.median(janelas[i:i + 20000], axis=1)
    return out


def _robusto(x):
    mad = np.median(np.abs(x - np.median(x))) * 1.4826
    return (x - np.median(x)) / (mad if mad > 1e-6 else (np.std(x) + 1e-6))


def excitacao(db, hop):
    """Volume: picos em relação ao que vinha acontecendo no último minuto."""
    curto = _media_movel(db, int(2 / hop))
    base = _mediana_movel(db, int(60 / hop))
    relativo = _robusto(curto - base)
    absoluto = _robusto(curto)
    nota = 0.7 * relativo + 0.3 * absoluto
    silencio = curto < (np.percentile(db, 15) + 3)
    nota[silencio] = np.minimum(nota[silencio], -2)
    return nota


def _preencher(x):
    x = x.astype(np.float32).copy()
    ruim = ~np.isfinite(x)
    if ruim.all():
        return np.zeros_like(x)
    x[ruim] = np.median(x[~ruim])
    return x


def sinal_voz(pros, hop):
    """Entonação: voz mais aguda que o normal do streamer, mais variação e mais 'gritada'.
    Usa escalas fixas (não z-score) para não exagerar variações pequenas de quem fala monótono."""
    st = pros["semitons"]
    fala = pros["fala"]
    if np.isfinite(st).sum() < 20:
        return np.zeros(len(st), np.float32)
    com_voz = fala > 0.15
    st_c = _preencher(st)
    base = _mediana_movel(st_c, int(120 / hop))
    altura = _media_movel(st_c - base, int(2 / hop)) / 2.0           # +2 semitons = 1 ponto
    var = _media_movel(pros["variacao"], int(2 / hop))
    ref_var = float(np.median(var[com_voz])) if com_voz.any() else float(np.median(var))
    variacao = (var - ref_var) / 1.0                                   # +1 semitom de oscilação = 1 ponto
    br = _preencher(np.where(com_voz, pros["brilho"], np.nan))
    br_base = _mediana_movel(br, int(120 / hop))
    brilho = _media_movel(br / (br_base + 1e-6) - 1, int(2 / hop)) / 0.15  # +15% de brilho = 1 ponto
    nota = 0.5 * altura + 0.3 * variacao + 0.2 * brilho
    sem_fala = _media_movel(fala, int(2 / hop)) < 0.15
    nota[sem_fala] = 0.0  # sem voz detectada (silêncio ou barulho cobrindo): neutro, não penaliza
    return nota.astype(np.float32)


def sinal_chat(pesos, hop):
    """Chat: quantas vezes acima do ritmo normal (últimos 2 min), em janelas de 10 s.
    Escala em "dobros": chat 2x mais rápido ≈ 1,5 ponto, 4x ≈ 3 pontos. A constante evita
    que poucas mensagens aleatórias em chats pequenos pareçam um pico."""
    if pesos.sum() < 30:
        return None
    janela = max(1, int(10 / hop))
    soma = _media_movel(pesos, janela) * janela
    base = _mediana_movel(soma, int(120 / hop))
    k = 5.0
    return (1.5 * np.log2((soma + k) / (base + k))).astype(np.float32)


def sinal_replay(heatmap, n, hop, deslocamento=0.0):
    """YouTube 'Mais repetidos': valor 0-1 por trecho. Vira pontos acima da mediana (pico máximo ≈ 4)."""
    if not heatmap:
        return None
    x = np.zeros(n, np.float32)
    for h in heatmap:
        a = int((float(h.get("start_time", 0)) - deslocamento) / hop)
        b = int((float(h.get("end_time", 0)) - deslocamento) / hop) + 1
        a, b = max(0, a), min(n, b)
        if b > a:
            x[a:b] = float(h.get("value") or 0)
    validos = x[x > 0]
    if len(validos) < 5:
        return None
    med, top = float(np.median(validos)), float(validos.max())
    return (4.0 * (x - med) / max(1e-6, top - med)).astype(np.float32)


def normalizar(x):
    """Os sinais já saem em escala própria (≈ desvios acima do normal); aqui só limita os extremos."""
    return np.clip(np.asarray(x, np.float32), -3, 6)


def combinar(sinais, n):
    """sinais: lista de (array, peso). Mistura a média ponderada (vários sinais juntos)
    com o sinal mais forte do momento (um pico enorme em um só sinal também conta)."""
    comps, pesos = [], []
    for arr, peso in sinais:
        if arr is None or peso <= 0:
            continue
        a = np.zeros(n, np.float32)
        m = min(n, len(arr))
        a[:m] = np.clip(arr[:m], -3, 6)
        comps.append(a)
        pesos.append(float(peso))
    if not comps:
        return np.zeros(n, np.float32)
    pesos = np.array(pesos, np.float32)
    pilha = np.stack(comps)
    media = (pilha * pesos[:, None]).sum(axis=0) / pesos.sum()
    maior = (pilha * (pesos / pesos.mean())[:, None]).max(axis=0)
    return 0.6 * media + 0.4 * maior


def candidatos(curva, hop, duracao, quantidade, ini=0.0, fim=None, excluir=(), pos_pico=0.65):
    """Acha os picos da curva combinada e monta janelas com o pico a ~65% do corte
    (contexto antes, reação depois), sem sobreposição."""
    if len(curva) == 0 or quantidade <= 0:
        return []
    suave = _media_movel(curva, max(1, int(3 / hop))).astype(np.float64)
    n = len(suave)
    antes, depois = pos_pico * duracao, (1 - pos_pico) * duracao
    mascara = np.full(n, -np.inf)
    a = int(max(0.0, ini) / hop)
    b = n if fim is None else min(n, int(fim / hop))
    mascara[a:b] = suave[a:b]
    borda = int(3 / hop)  # ignora o comecinho e o finalzinho (artefatos de borda)
    mascara[:borda] = -np.inf
    mascara[max(0, n - borda):] = -np.inf
    for (ei, ef) in excluir:
        x0 = max(0, int((ei - depois) / hop))
        x1 = min(n, int((ef + antes) / hop) + 1)
        mascara[x0:x1] = -np.inf
    L = int(duracao / hop)
    saida = []
    for _ in range(quantidade):
        p = int(np.argmax(mascara))
        if not np.isfinite(mascara[p]):
            break
        t = p * hop
        i = max(0.0, t - antes)
        saida.append({"i": i, "f": i + duracao, "pico": t, "nota_sinais": float(suave[p])})
        mascara[max(0, p - L):p + L] = -np.inf
    return saida


def nota_texto(texto, dur, extras=()):
    t = texto.lower()
    acertos = sum(t.count(g) for g in GATILHOS) + sum(t.count(g) for g in extras)
    exclam = texto.count("!") + 0.5 * texto.count("?")
    palavras = len(texto.split())
    pps = palavras / max(dur, 1)
    nota = 1.5 * acertos + 0.7 * exclam + min(pps, 4.0)
    if pps < 0.4:
        nota -= 1.5
    return nota


def ajustar_limites(c, segs, dmin, dmax, dur_total):
    """Começa e termina o corte em pausas da fala, sem perder o pico de reação."""
    s, e = c["i"], c["f"]
    pico = c.get("pico", (s + e) / 2)
    dentro = [x for x in segs if x["f"] > s + 0.3 and x["i"] < e - 0.3]
    if dentro:
        ns = max(dentro[0]["i"] - 0.25, s - 5)
        ne = min(dentro[-1]["f"] + 0.4, e + 5)
    else:
        ns, ne = s, e
    ne = max(ne, min(pico + 3, e + 5))
    if ne - ns > dmax:
        ns = max(ns, ne - dmax)
        inicios = [x["i"] - 0.25 for x in segs if ns <= x["i"] - 0.25 <= min(pico - 2, ns + 4)]
        if inicios:
            ns = min(inicios)
        if ne - ns > dmax:
            fins = [x["f"] + 0.4 for x in segs if max(ns + dmin, pico + 2) <= x["f"] + 0.4 <= ns + dmax]
            ne = max(fins) if fins else ns + dmax
    if ne - ns < dmin:
        falta = dmin - (ne - ns)
        ns, ne = ns - falta * 0.5, ne + falta * 0.5
    ns = max(0.0, ns)
    if dur_total:
        ne = min(dur_total, ne)
    c["i"], c["f"] = round(ns, 2), round(ne, 2)
    return c


def titulo_automatico(segs, max_palavras=7, extras=()):
    if not segs:
        return ""
    melhor = max(segs, key=lambda x: nota_texto(x["texto"], max(0.5, x["f"] - x["i"]), extras))
    palavras = re.sub(r"\s+", " ", melhor["texto"]).strip().split(" ")
    titulo = " ".join(palavras[:max_palavras]).strip(" ,.;:-")
    if len(palavras) > max_palavras:
        titulo += "..."
    return titulo.upper()
