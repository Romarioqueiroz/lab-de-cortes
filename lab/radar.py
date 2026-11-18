"""Radar de streamers: procura sozinho os clipes mais vistos e as lives novas dos streamers
cadastrados (Twitch, Kick, YouTube e outros sites do yt-dlp) e manda para o Lab cortar.

- Twitch e Kick: clipes da comunidade ordenados por visualizações (os "mais clipados").
- YouTube: lives recentes; o corte usa o gráfico "Mais repetidos" (heatmap) como sinal.
- Lives completas (qualquer plataforma): baixa a live e procura os melhores momentos.
"""
import re
import threading
import time
import traceback
import unicodedata
import uuid

from .utils import salvar_json

PLATAFORMAS = {"twitch": "Twitch", "kick": "Kick", "youtube": "YouTube", "outra": "Outra"}
FILTRO_GTA6 = "gta 6, gta vi, gta6, gtavi, grand theft auto vi, grand theft auto 6"
PERIODOS = {"24h": ("24hr", "day"), "7d": ("7d", "week"), "30d": ("30d", "month")}

PADRAO = {
    "ligado": False, "intervalo_min": 30, "filtro": FILTRO_GTA6, "periodo": "7d",
    "por_streamer": 3, "min_views": 0, "max_fila": 12,
    "streamers": [], "cfg_base": {}, "log": [], "ultima_rodada": 0, "proxima": 0,
    # descoberta automática de streamers
    "descobrir": True, "descobrir_plats": ["twitch", "kick", "youtube"], "idioma": "pt",
    "descobrir_max": 8, "descobrir_min_viewers": 20, "max_auto": 40, "termo_youtube": "GTA 6 ao vivo",
    "ignorados": [], "ultima_descoberta": 0,
}


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def bate_filtro(textos, filtro):
    termos = [_sem_acento(t.strip()) for t in (filtro or "").split(",") if t.strip()]
    if not termos:
        return True
    alvo = " | ".join(_sem_acento(t) for t in textos if t)
    return any(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", alvo) for t in termos)


def normalizar_usuario(texto, plataforma):
    """Aceita '@nome', 'nome' ou o link do canal. Retorna (usuario, plataforma, url_canal)."""
    t = (texto or "").strip()
    m = re.search(r"twitch\.tv/([\w]+)", t, re.I)
    if m:
        return m.group(1).lower(), "twitch", ""
    m = re.search(r"kick\.com/([\w-]+)", t, re.I)
    if m:
        return m.group(1).lower(), "kick", ""
    m = re.search(r"youtube\.com/(@[\w.\-]+|channel/[\w-]+|c/[\w.\-]+)", t, re.I)
    if m:
        return m.group(1).lstrip("@"), "youtube", f"https://www.youtube.com/{m.group(1)}"
    if t.startswith("http"):
        return t, "outra", t
    u = t.lstrip("@").strip()
    if plataforma == "twitch" or plataforma == "kick":
        u = u.lower()
    return u, plataforma, ""


class Radar:
    def __init__(self, gerente, pasta_dados):
        self.gerente = gerente
        self.arq = pasta_dados / "radar.json"
        self.dados = {**PADRAO}
        if self.arq.exists():
            import json
            try:
                self.dados.update(json.loads(self.arq.read_text(encoding="utf-8")))
            except ValueError:
                pass
        self.rodando = False
        self.trava = threading.Lock()
        threading.Thread(target=self._laco, daemon=True).start()

    # ------------------------------------------------------------------ estado
    def salvar(self):
        salvar_json(self.arq, self.dados)

    def log(self, msg):
        self.dados["log"] = (self.dados.get("log", []) + [time.strftime("%d/%m %H:%M ") + msg])[-60:]
        self.salvar()

    def resumo(self):
        return {**self.dados, "rodando": self.rodando, "agora": time.time()}

    def configurar(self, d):
        for k in ("ligado", "intervalo_min", "filtro", "periodo", "por_streamer", "min_views", "cfg_base",
                  "descobrir", "descobrir_plats", "idioma", "descobrir_max", "descobrir_min_viewers", "termo_youtube"):
            if k in d:
                self.dados[k] = d[k]
        self.dados["intervalo_min"] = max(10, int(self.dados["intervalo_min"] or 30))
        self.dados["por_streamer"] = max(1, min(10, int(self.dados["por_streamer"] or 3)))
        if d.get("ligado") and self.dados.get("proxima", 0) < time.time():
            self.dados["proxima"] = time.time() + 5  # liga e já verifica
        self.salvar()

    # ------------------------------------------------------------------ descoberta
    def descobrir_agora(self):
        threading.Thread(target=self.descobrir, daemon=True).start()

    def descobrir(self):
        from . import descobrir as D
        self.dados["ultima_descoberta"] = time.time()
        novos_total = 0
        for plat in self.dados.get("descobrir_plats") or []:
            if plat not in D.FUNCOES:
                continue
            auto_atuais = sum(1 for s in self.dados["streamers"] if s.get("auto"))
            if auto_atuais >= int(self.dados.get("max_auto", 40)):
                self.log(f"Limite de {self.dados['max_auto']} streamers descobertos atingido.")
                break
            try:
                kw = {"limite": int(self.dados.get("descobrir_max", 8)), "log": self.log}
                if plat == "youtube":
                    kw["termo"] = self.dados.get("termo_youtube") or "GTA 6 ao vivo"
                else:
                    kw["idioma"] = self.dados.get("idioma", "pt")
                achados = D.FUNCOES[plat](**kw)
            except Exception as e:
                self.log(f"Descoberta {PLATAFORMAS[plat]}: falhou ({str(e)[:140]})")
                continue
            novos = []
            minimo = int(self.dados.get("descobrir_min_viewers") or 0)
            for a in achados:
                chave = f"{plat}:{a['usuario'].lower()}"
                if chave in self.dados["ignorados"]:
                    continue
                if any(s["plataforma"] == plat and s["usuario"].lower() == a["usuario"].lower() for s in self.dados["streamers"]):
                    continue
                if (a.get("viewers") or 0) < minimo and not a.get("clip_views"):
                    continue
                self.dados["streamers"].append({
                    "id": uuid.uuid4().hex[:8], "usuario": a["usuario"], "nome": a.get("nome", a["usuario"]),
                    "plataforma": plat, "url": a.get("url", ""), "tipo": "lives" if plat == "youtube" else "clipes",
                    "ativo": True, "auto": True, "vistos": [], "ultima": 0, "total": 0,
                    "status": (f"descoberto ao vivo ({a['viewers']} assistindo)" if a.get("viewers")
                               else f"descoberto pelos clipes ({a.get('clip_views', 0)} views na semana)"),
                    "viewers": a.get("viewers") or 0,
                })
                novos.append(a.get("nome") or a["usuario"])
            novos_total += len(novos)
            self.log(f"Descoberta {PLATAFORMAS[plat]}: {len(achados)} jogando GTA 6, {len(novos)} novos"
                     + (": " + ", ".join(novos[:8]) if novos else "."))
        self.salvar()
        return novos_total

    def adicionar(self, texto, plataforma, tipo):
        usuario, plat, url = normalizar_usuario(texto, plataforma)
        if not usuario:
            raise ValueError("Digite o @ ou o link do streamer.")
        if plat not in PLATAFORMAS:
            raise ValueError("Plataforma inválida.")
        if plat == "outra" and not url:
            raise ValueError("Para 'Outra', cole o link do canal.")
        if any(s["usuario"].lower() == usuario.lower() and s["plataforma"] == plat for s in self.dados["streamers"]):
            raise ValueError("Esse streamer já está na lista.")
        if plat in ("youtube", "outra"):
            tipo = "lives"
        s = {"id": uuid.uuid4().hex[:8], "usuario": usuario, "plataforma": plat, "url": url,
             "tipo": tipo if tipo in ("clipes", "lives") else "clipes", "ativo": True,
             "vistos": [], "ultima": 0, "status": "aguardando a primeira verificação", "total": 0}
        self.dados["streamers"].append(s)
        self.salvar()
        return s

    def alterar(self, sid, d):
        s = self._s(sid)
        for k in ("ativo", "tipo"):
            if k in d:
                s[k] = d[k]
        self.salvar()

    def remover(self, sid):
        for s in self.dados["streamers"]:
            if s["id"] == sid and s.get("auto"):  # não descobrir de novo quem você removeu
                self.dados["ignorados"] = (self.dados["ignorados"] + [f"{s['plataforma']}:{s['usuario'].lower()}"])[-500:]
        self.dados["streamers"] = [s for s in self.dados["streamers"] if s["id"] != sid]
        self.salvar()

    def _s(self, sid):
        s = next((s for s in self.dados["streamers"] if s["id"] == sid), None)
        if not s:
            raise ValueError("Streamer não encontrado.")
        return s

    # ------------------------------------------------------------------ laço
    def _laco(self):
        while True:
            time.sleep(15)
            try:
                if self.dados.get("ligado") and time.time() >= self.dados.get("proxima", 0):
                    self.rodada()
            except Exception:
                traceback.print_exc()

    def verificar_agora(self, sid=None):
        threading.Thread(target=self.rodada, args=(sid,), daemon=True).start()

    def rodada(self, sid=None):
        if not self.trava.acquire(blocking=False):
            return
        self.rodando = True
        try:
            alvos = [s for s in self.dados["streamers"] if (s["id"] == sid if sid else s.get("ativo"))]
            if not sid:
                self.dados["ultima_rodada"] = time.time()
                self.dados["proxima"] = time.time() + 60 * int(self.dados["intervalo_min"])
                if self.dados.get("descobrir"):
                    self.descobrir()
                    alvos = [s for s in self.dados["streamers"] if s.get("ativo")]
                    # quem tem mais audiência é verificado primeiro
                    alvos.sort(key=lambda s: s.get("viewers", 0), reverse=True)
            self.salvar()
            for s in alvos:
                fila = sum(1 for j in self.gerente.jobs.values() if j["status"] in ("na fila", "processando"))
                if fila >= int(self.dados.get("max_fila", 12)):
                    self.log(f"Fila cheia ({fila} na fila). O resto fica para a próxima verificação.")
                    break
                self._verificar(s)
        finally:
            self.rodando = False
            self.trava.release()
            self.salvar()

    def _verificar(self, s):
        nome = f"@{s['usuario']} ({PLATAFORMAS[s['plataforma']]})"
        s["status"] = "verificando..."
        self.salvar()
        try:
            itens = self.buscar(s)
        except Exception as e:
            s["status"] = "erro: " + str(e)[:160]
            s["ultima"] = time.time()
            self.log(f"{nome}: não consegui buscar ({str(e)[:120]})")
            return
        novos = [i for i in itens if i["id"] not in s["vistos"]][: int(self.dados["por_streamer"])]
        for item in novos:
            self._enviar(s, item)
            s["vistos"] = (s["vistos"] + [item["id"]])[-800:]
        s["total"] = s.get("total", 0) + len(novos)
        s["ultima"] = time.time()
        tipo = "clipes" if s["tipo"] == "clipes" else "lives"
        s["status"] = f"{len(novos)} {tipo} novos enviados" if novos else "nada novo desta vez"
        self.log(f"{nome}: {len(itens)} encontrados, {len(novos)} novos enviados para cortar.")
        self.salvar()

    def _enviar(self, s, item):
        base = dict(self.dados.get("cfg_base") or {})
        cfg = {**base, "url": item["url"], "perfil": base.get("perfil", "gta6"),
               "manuais": "", "trecho_ini": "", "trecho_fim": "", "depois": "auto"}
        origem = {"usuario": s["usuario"], "plataforma": s["plataforma"], "views": item.get("views"),
                  "titulo": item.get("titulo", ""), "url": item["url"], "tipo": s["tipo"]}
        if s["tipo"] == "clipes":
            cfg["modo"] = "clipe"
            cfg["n_clipes"] = 1
        else:
            cfg["modo"] = "live"
            cfg["n_clipes"] = int(base.get("n_clipes") or 4)
        cfg["origem"] = origem
        self.gerente.criar(cfg)

    # ------------------------------------------------------------------ busca por plataforma
    def _listar(self, url, limite=40):
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
                               "playlistend": limite, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False) or {}
        return [e for e in (info.get("entries") or []) if e]

    def _detalhe(self, url):
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            return ydl.extract_info(url, download=False) or {}

    def buscar(self, s):
        """Retorna lista de itens {id, url, titulo, views}, do mais visto (clipes) ou mais novo (lives)."""
        plat, u, filtro = s["plataforma"], s["usuario"], self.dados["filtro"]
        periodo_tw, periodo_kick = PERIODOS.get(self.dados["periodo"], PERIODOS["7d"])
        min_views = int(self.dados.get("min_views") or 0)
        saida = []

        if s["tipo"] == "clipes" and plat in ("twitch", "kick"):
            url = (f"https://www.twitch.tv/{u}/clips?filter=clips&range={periodo_tw}" if plat == "twitch"
                   else f"https://kick.com/{u}/clips?sort=view&range={periodo_kick}")
            entradas = sorted(self._listar(url, 40), key=lambda e: e.get("view_count") or 0, reverse=True)
            checados = 0
            for e in entradas:
                views = e.get("view_count") or 0
                if views < min_views:
                    continue
                textos = [e.get("title", "")] + list(e.get("categories") or [])
                ok = bate_filtro(textos, filtro)
                if not ok and plat == "twitch" and checados < 12:
                    # a lista da Twitch não traz o jogo; consulta o clipe para ver a categoria
                    checados += 1
                    try:
                        d = self._detalhe(e["url"])
                        ok = bate_filtro([d.get("title", "")] + list(d.get("categories") or []), filtro)
                    except Exception:
                        ok = False
                if ok:
                    saida.append({"id": f"{plat}:{e.get('id') or e['url']}", "url": e["url"],
                                  "titulo": e.get("title", ""), "views": views})
            return saida

        # lives completas
        if plat == "twitch":
            url = f"https://www.twitch.tv/{u}/videos?filter=archives&sort=time"
        elif plat == "kick":
            url = f"https://kick.com/{u}/videos"
        elif plat == "youtube":
            url = (s.get("url") or (f"https://www.youtube.com/@{u}" if not u.startswith(("channel/", "c/")) else f"https://www.youtube.com/{u}")).rstrip("/") + "/streams"
        else:
            url = s["url"]
        for e in self._listar(url, 15):
            if e.get("live_status") in ("is_live", "is_upcoming", "post_live"):
                continue
            if not bate_filtro([e.get("title", "")] + list(e.get("categories") or []), filtro):
                continue
            link = e.get("url") or e.get("webpage_url")
            if link and not link.startswith("http"):
                link = f"https://www.youtube.com/watch?v={link}"
            saida.append({"id": f"{plat}:{e.get('id') or link}", "url": link,
                          "titulo": e.get("title", ""), "views": e.get("view_count")})
        return saida[:2]  # lives são longas: no máximo 2 por verificação
