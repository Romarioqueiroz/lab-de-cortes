"""Descobre sozinho quem está jogando GTA 6 em cada plataforma (sem precisar digitar o @).

- Twitch: diretório do jogo (quem está ao vivo, por audiência) e clipes mais vistos do jogo.
- Kick: lives em destaque filtradas pela categoria do jogo.
- YouTube: busca por lives ao vivo com o termo do jogo.
Cada função retorna lista de {usuario, nome, plataforma, viewers, idioma, url}.
"""
import json
import re
import urllib.request

from .chat import TWITCH_CID, UA

TWITCH_JOGO = "Grand Theft Auto VI"


# ---------------------------------------------------------------- utilitários
def _gql_twitch(query):
    req = urllib.request.Request(
        "https://gql.twitch.tv/gql", data=json.dumps({"query": query}).encode(),
        headers={"Client-Id": TWITCH_CID, "User-Agent": UA, "Content-Type": "text/plain;charset=UTF-8"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    if d.get("errors"):
        raise RuntimeError("Twitch: " + "; ".join(e.get("message", "") for e in d["errors"])[:200])
    return d.get("data") or {}


def _json_kick(url):
    """Kick fica atrás do Cloudflare: usa a imitação de navegador do yt-dlp (curl_cffi)."""
    import yt_dlp
    from yt_dlp.networking import Request
    from yt_dlp.networking.impersonate import ImpersonateTarget
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        try:
            resp = ydl.urlopen(Request(url, headers={"Accept": "application/json"},
                                       extensions={"impersonate": ImpersonateTarget()}))
        except Exception as e:
            if "impersonat" in str(e).lower():
                raise RuntimeError("Kick precisa do componente curl_cffi (rode o iniciar.bat de novo).")
            raise
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------- Twitch
def twitch(idioma="pt", limite=10, jogo=TWITCH_JOGO, log=print):
    achados = {}
    q_lives = (
        'query { game(name: "%s") { streams(first: 100) { edges { node { viewersCount title '
        'broadcaster { login displayName broadcastSettings { language } } } } } } }' % jogo
    )
    try:
        dados = _gql_twitch(q_lives)
    except RuntimeError:
        # versão mais simples (sem idioma), caso o campo mude
        dados = _gql_twitch(q_lives.replace(" broadcastSettings { language }", ""))
    for e in (((dados.get("game") or {}).get("streams") or {}).get("edges") or []):
        n = e.get("node") or {}
        b = n.get("broadcaster") or {}
        lang = ((b.get("broadcastSettings") or {}).get("language") or "").lower()
        if not b.get("login") or (idioma and lang and not lang.startswith(idioma.lower())):
            continue
        achados[b["login"].lower()] = {"usuario": b["login"].lower(), "nome": b.get("displayName") or b["login"],
                                       "plataforma": "twitch", "viewers": n.get("viewersCount") or 0, "idioma": lang}
    # clipes mais vistos do jogo na semana: acha quem não está ao vivo agora
    try:
        q_clipes = ('query { game(name: "%s") { clips(first: 100, criteria: { period: LAST_WEEK }) { edges { node { '
                    'viewCount language broadcaster { login displayName } } } } } }' % jogo)
        dados = _gql_twitch(q_clipes)
        for e in (((dados.get("game") or {}).get("clips") or {}).get("edges") or []):
            n = e.get("node") or {}
            b = n.get("broadcaster") or {}
            lang = (n.get("language") or "").lower()
            if not b.get("login") or (idioma and lang and not lang.startswith(idioma.lower())):
                continue
            atual = achados.setdefault(b["login"].lower(), {
                "usuario": b["login"].lower(), "nome": b.get("displayName") or b["login"],
                "plataforma": "twitch", "viewers": 0, "idioma": lang})
            atual["clip_views"] = atual.get("clip_views", 0) + (n.get("viewCount") or 0)
    except Exception as e:
        log(f"Twitch: clipes do jogo indisponíveis ({str(e)[:80]}), usando só quem está ao vivo.")
    lista = sorted(achados.values(), key=lambda x: (x.get("clip_views", 0) + 20 * x["viewers"]), reverse=True)
    return lista[:limite]


# ---------------------------------------------------------------- Kick
def _bate_jogo(nome):
    n = (nome or "").lower()
    return bool(re.search(r"grand theft auto (vi|6)\b|\bgta ?(vi|6)\b", n))


def kick(idioma="pt", limite=10, log=print):
    achados = {}
    url = f"https://kick.com/stream/featured-livestreams/{idioma or 'en'}"
    for _ in range(8):  # até 8 páginas
        d = _json_kick(url)
        for s in d.get("data") or []:
            cats = [c.get("name", "") for c in (s.get("categories") or [])]
            canal = s.get("channel") or {}
            slug = canal.get("slug")
            if not slug or not any(_bate_jogo(c) for c in cats):
                continue
            achados[slug] = {"usuario": slug, "nome": (canal.get("user") or {}).get("username") or slug,
                             "plataforma": "kick", "viewers": s.get("viewer_count") or 0,
                             "idioma": s.get("language") or idioma}
        url = d.get("next_page_url")
        if not url or len(achados) >= limite * 2:
            break
    return sorted(achados.values(), key=lambda x: x["viewers"], reverse=True)[:limite]


# ---------------------------------------------------------------- YouTube
def youtube(termo="GTA 6 ao vivo", limite=10, log=print):
    import urllib.parse
    import yt_dlp
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(termo) + "&sp=EgJAAQ%253D%253D"
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
                           "playlistend": 40, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False) or {}
    achados = {}
    for e in info.get("entries") or []:
        if not e or not _bate_jogo(e.get("title", "")):
            continue
        cid = e.get("channel_id")
        if not cid:
            continue
        handle = (e.get("uploader_id") or "").lstrip("@") if str(e.get("uploader_id", "")).startswith("@") else ""
        usuario = handle or f"channel/{cid}"
        achados.setdefault(cid, {
            "usuario": usuario, "nome": e.get("channel") or e.get("uploader") or usuario, "plataforma": "youtube",
            "viewers": e.get("concurrent_view_count") or e.get("view_count") or 0, "idioma": "",
            "url": f"https://www.youtube.com/{'@' + handle if handle else 'channel/' + cid}",
        })
    return sorted(achados.values(), key=lambda x: x["viewers"] or 0, reverse=True)[:limite]


FUNCOES = {"twitch": twitch, "kick": kick, "youtube": youtube}
