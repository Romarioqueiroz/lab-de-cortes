"""Baixa o replay do chat da live e transforma em um sinal de "agitação do chat".

- YouTube: replay do chat via yt-dlp (lives que tiveram chat ao vivo).
- Twitch: comentários do VOD via API GraphQL pública do site.
- Também aceita um arquivo `<nome do vídeo>.live_chat.json` (formato do yt-dlp) ao lado do vídeo local.
"""
import glob
import json
import os
import re
import time
import urllib.request

import numpy as np

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

# mensagens que indicam reação forte valem mais
REACAO = re.compile(
    r"(k{3,}|(ha){2,}|(rs){2,}|kek|lul|omegalul|pog|clip|clipa|\?{3,}|!{3,}|"
    r"meu deus|caralh|caramba|nossa|wtf|lmao|lol|😂|🤣|😱|🔥|💀|monka|pepelaugh|sadge|"
    r"face-with-tears-of-joy|rolling-on-the-floor|skull|fire)", re.I)
CLIP = re.compile(r"\bclip|clipa|corta isso|cortem", re.I)


def peso_mensagem(texto, superchat=False):
    p = 1.0
    if REACAO.search(texto or ""):
        p += 1.0
    if CLIP.search(texto or ""):
        p += 2.0
    letras = [c for c in (texto or "") if c.isalpha()]
    if len(letras) >= 4 and sum(c.isupper() for c in letras) / len(letras) > 0.8:
        p += 0.5
    if superchat:
        p += 3.0
    return p


# ---------------------------------------------------------------- YouTube
def _texto_runs(runs):
    partes = []
    for r in runs or []:
        if "text" in r:
            partes.append(r["text"])
        elif "emoji" in r:
            atalhos = r["emoji"].get("shortcuts") or [""]
            partes.append(atalhos[0])
    return "".join(partes)


def ler_chat_youtube(caminho):
    msgs = []
    with open(caminho, encoding="utf-8", errors="replace") as f:
        for linha in f:
            try:
                obj = json.loads(linha)
            except ValueError:
                continue
            r = obj.get("replayChatItemAction") or {}
            try:
                t = int(r.get("videoOffsetTimeMsec", -1)) / 1000.0
            except (TypeError, ValueError):
                continue
            if t < 0:
                continue
            for a in r.get("actions", []):
                item = (a.get("addChatItemAction") or {}).get("item") or {}
                if "liveChatTextMessageRenderer" in item:
                    txt = _texto_runs(item["liveChatTextMessageRenderer"].get("message", {}).get("runs"))
                    msgs.append((t, txt, False))
                elif "liveChatPaidMessageRenderer" in item:
                    txt = _texto_runs(item["liveChatPaidMessageRenderer"].get("message", {}).get("runs"))
                    msgs.append((t, txt, True))
    return msgs


def _youtube(url, pasta, log, cookies):
    import yt_dlp
    opcoes = {
        "skip_download": True, "writesubtitles": True, "subtitleslangs": ["live_chat"],
        "outtmpl": os.path.join(pasta, "chat.%(ext)s"), "quiet": True, "no_warnings": True, "noplaylist": True,
    }
    if cookies:
        opcoes["cookiesfrombrowser"] = (cookies,)
    log("Baixando o replay do chat do YouTube (lives longas podem levar alguns minutos)...")
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        ydl.download([url])
    arqs = glob.glob(os.path.join(pasta, "chat*.live_chat.json"))
    if not arqs:
        log("Esta live não tem replay de chat disponível.")
        return []
    return ler_chat_youtube(arqs[0])


# ---------------------------------------------------------------- Twitch
TWITCH_CID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
TWITCH_HASH = "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"


def _gql(variaveis):
    corpo = [{
        "operationName": "VideoCommentsByOffsetOrCursor", "variables": variaveis,
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": TWITCH_HASH}},
    }]
    req = urllib.request.Request(
        "https://gql.twitch.tv/gql", data=json.dumps(corpo).encode(),
        headers={"Client-Id": TWITCH_CID, "User-Agent": UA, "Content-Type": "text/plain;charset=UTF-8"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))[0]


def _twitch(video_id, log):
    log("Baixando o chat do VOD da Twitch...")
    msgs, vistos = [], set()
    cursor, offset, paginas, ultimo_t = None, 0, 0, 0.0
    while paginas < 20000:
        variaveis = {"videoID": video_id}
        if cursor:
            variaveis["cursor"] = cursor
        else:
            variaveis["contentOffsetSeconds"] = int(offset)
        resp = None
        for tentativa in range(3):
            try:
                resp = _gql(variaveis)
                break
            except Exception:
                time.sleep(1.5 * (tentativa + 1))
        if resp is None or resp.get("errors"):
            if cursor:  # cursor recusado: segue por tempo
                cursor, offset = None, ultimo_t + 1
                continue
            break
        comentarios = (((resp.get("data") or {}).get("video") or {}).get("comments")) or {}
        arestas = comentarios.get("edges") or []
        if not arestas:
            break
        novos = 0
        for e in arestas:
            n = e.get("node") or {}
            if n.get("id") in vistos:
                continue
            vistos.add(n.get("id"))
            novos += 1
            t = float(n.get("contentOffsetSeconds") or 0)
            ultimo_t = max(ultimo_t, t)
            txt = "".join((f.get("text") or "") for f in ((n.get("message") or {}).get("fragments") or []))
            msgs.append((t, txt, False))
        paginas += 1
        if paginas % 100 == 0:
            log(f"Chat: {len(msgs)} mensagens lidas (até {int(ultimo_t // 60)} min da live)...")
        if not (comentarios.get("pageInfo") or {}).get("hasNextPage"):
            break
        cursor = arestas[-1].get("cursor")
        if not cursor:
            offset = ultimo_t + (1 if novos else 5)
    return msgs


# ---------------------------------------------------------------- geral
def obter_mensagens(fonte, pasta, log, cookies="", video_local=None):
    """Retorna lista de (segundos, texto, superchat). Lista vazia se não houver chat."""
    fonte = fonte.strip().strip('"')
    try:
        if video_local and os.path.isfile(fonte):
            base = os.path.splitext(fonte)[0]
            for cand in (base + ".live_chat.json", base + ".pt.live_chat.json"):
                if os.path.isfile(cand):
                    log("Usando o chat do arquivo " + os.path.basename(cand))
                    return ler_chat_youtube(cand)
            log("Arquivo local sem chat ao lado (opcional: <nome>.live_chat.json).")
            return []
        if re.search(r"(youtube\.com|youtu\.be)", fonte, re.I):
            return _youtube(fonte, pasta, log, cookies)
        m = re.search(r"twitch\.tv/(?:\w+/)?videos?/(\d+)", fonte, re.I)
        if m:
            return _twitch(m.group(1), log)
        log("Chat automático disponível só para YouTube e Twitch. Seguindo sem o chat.")
    except Exception as e:
        log(f"Não consegui baixar o chat ({str(e)[:150]}). Seguindo sem ele.")
    return []


def sinal_chat(msgs, n_blocos, hop, deslocamento=0.0, atraso=6.0):
    """Mensagens (com peso) por bloco de `hop` segundos, já recuadas pelo atraso de reação do chat."""
    pesos = np.zeros(n_blocos, np.float32)
    contagem = np.zeros(n_blocos, np.float32)
    for t, txt, sc in msgs:
        i = int((t - deslocamento - atraso) / hop)
        if 0 <= i < n_blocos:
            pesos[i] += peso_mensagem(txt, sc)
            contagem[i] += 1
    return pesos, contagem
