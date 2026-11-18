"""Fila de trabalhos: baixa a live, encontra os destaques e renderiza os cortes."""
import os
import queue
import re
import threading
import time
import traceback
import uuid
from pathlib import Path

import numpy as np

from . import ai, audio, chat, descricao, highlights, perfis, voz
from .download import baixar, eh_arquivo_local
from .render import renderizar
from .transcribe import Transcritor
from .utils import info_video, salvar_json, seg_para_tempo, tempo_para_seg

RAIZ = Path(__file__).resolve().parent.parent
PASTA_TRABALHOS = RAIZ / "trabalhos"
HOP = 0.5

PADRAO = {
    "url": "", "n_clipes": 5, "dur_min": 20, "dur_max": 60,
    "marca": "", "cor": "#FFD400", "preset": "vibrante", "zoom": 1.08,
    "enquadramento": "completo", "legendas": True, "titulo": True, "barra": True,
    "modelo": "small", "idioma": "pt", "trecho_ini": "", "trecho_fim": "",
    "manuais": "", "cookies": "", "ia_chave": "", "ia_modelo": "claude-sonnet-4-5",
    "apagar_live": False,
    "usar_chat": True, "atraso_chat": 6, "peso_volume": 1.0, "peso_voz": 1.0, "peso_chat": 1.5,
    "peso_fala": 1.0,
    "perfil": "gta6", "hashtags": "", "gatilhos_extra": "",
    "depois": "revisar", "postar_em": [],
    "modo": "live", "origem": None, "peso_replay": 2.0,
}

OPCOES_RENDER = ("marca", "cor", "preset", "zoom", "enquadramento", "legendas", "titulo", "barra")


def _ler_manuais(texto, dur_padrao):
    saida = []
    for linha in (texto or "").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        partes = [p for p in linha.replace("–", "-").replace(" a ", "-").split("-") if p.strip()]
        ini = tempo_para_seg(partes[0])
        fim = tempo_para_seg(partes[1]) if len(partes) > 1 else None
        if ini is None:
            continue
        if fim is None or fim <= ini:
            ini, fim = max(0.0, ini - dur_padrao / 2), ini + dur_padrao / 2
        saida.append((ini, fim))
    return saida


class Gerenciador:
    def __init__(self):
        PASTA_TRABALHOS.mkdir(exist_ok=True)
        self.jobs = {}
        self.trava = threading.Lock()
        self.fila = queue.Queue()
        self._trans = {}
        self.ao_terminar = None  # callback(job, clipe, redes) para postar
        self.config_auto = lambda: {"ativo": False, "redes": []}  # botão "postar automático" da tela
        self._carregar_existentes()
        threading.Thread(target=self._trabalhador, daemon=True).start()

    # ---------- estado ----------
    def _carregar_existentes(self):
        import json
        for arq in PASTA_TRABALHOS.glob("*/job.json"):
            try:
                job = json.loads(arq.read_text(encoding="utf-8"))
            except Exception:
                continue
            if job.get("status") in ("na fila", "processando"):
                job["status"] = "erro"
                job["erro"] = "Interrompido (o programa foi fechado durante o processamento)."
            self.jobs[job["id"]] = job

    def _salvar(self, job):
        salvar_json(PASTA_TRABALHOS / job["id"] / "job.json", job)

    def listar(self):
        with self.trava:
            jobs = sorted(self.jobs.values(), key=lambda j: j["criado"], reverse=True)
            return [{k: v for k, v in j.items() if k != "log"} | {"log": j["log"][-1:]} for j in jobs]

    def obter(self, jid):
        return self.jobs.get(jid)

    def caminho_clipe(self, jid, arquivo):
        return str(PASTA_TRABALHOS / jid / arquivo)

    def criar(self, cfg):
        base = {**PADRAO, **perfis.obter(cfg.get("perfil", PADRAO["perfil"]))["padrao"]}
        cfg = {**base, **{k: v for k, v in cfg.items() if k in PADRAO}}
        if not cfg["ia_chave"]:
            cfg["ia_chave"] = os.environ.get("ANTHROPIC_API_KEY", "")
        jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        (PASTA_TRABALHOS / jid).mkdir(parents=True)
        job = {
            "id": jid, "criado": time.time(), "cfg": {**cfg, "ia_chave": "***" if cfg["ia_chave"] else ""},
            "status": "na fila", "etapa": "Aguardando", "progresso": 0, "log": [], "clipes": [],
            "fonte": {"titulo": cfg["url"]}, "erro": "", "perfil": cfg["perfil"],
            "origem": cfg.get("origem"), "modo": cfg.get("modo", "live"),
        }
        with self.trava:
            self.jobs[jid] = job
        self._salvar(job)
        self.fila.put(("novo", jid, cfg))
        return job

    def transcritor(self, nome, log):
        if nome not in self._trans:
            self._trans[nome] = Transcritor(nome, log)
        self._trans[nome].log = log
        return self._trans[nome]

    def editar(self, jid, n, dados):
        """dados: titulo, descricao, inicio, fim (segundos no vídeo baixado), legendas, mostrar_titulo."""
        job = self.jobs[jid]
        clipe = next(c for c in job["clipes"] if c["n"] == n)
        if "descricao" in dados:
            clipe["descricao"] = str(dados["descricao"])
        precisa = any(k in dados for k in ("titulo", "inicio", "fim", "legendas", "mostrar_titulo", "marca", "forcar"))
        if precisa:
            clipe["status"] = "na fila"
            self.fila.put(("editar", jid, {"n": n, **dados}))
        self._salvar(job)

    def trocar_marca(self, marca, jid=None):
        """Troca o @ da marca d'água e refaz os cortes já prontos (de uma live ou de todas)."""
        refeitos, sem_fonte = 0, 0
        for job in list(self.jobs.values()):
            if jid and job["id"] != jid:
                continue
            if job.get("status") in ("na fila", "processando"):
                job["marca_pendente"] = marca  # aplicada quando os cortes forem editados
                continue
            if job.get("status") != "concluido":
                continue
            job.setdefault("cfg_render", {k: job["cfg"].get(k) for k in OPCOES_RENDER})["marca"] = marca
            video = (job.get("fonte") or {}).get("arquivo")
            tem_fonte = bool(video and os.path.isfile(video))
            for c in job["clipes"]:
                c.get("opcoes", {}).pop("marca", None)
                if tem_fonte:
                    c["status"] = "na fila"
                    self.fila.put(("editar", job["id"], {"n": c["n"], "forcar": True}))
                    refeitos += 1
                else:
                    sem_fonte += 1
            self._salvar(job)
        return {"refeitos": refeitos, "sem_fonte": sem_fonte}

    def rerenderizar(self, jid, n, titulo):
        self.editar(jid, n, {"titulo": titulo})

    # ---------- execução ----------
    def _trabalhador(self):
        while True:
            tipo, jid, dados = self.fila.get()
            job = self.jobs.get(jid)
            if not job:
                continue
            if tipo != "novo":
                try:
                    self._refazer(job, dados)
                except Exception as e:
                    traceback.print_exc()
                    for c in job["clipes"]:
                        if c["n"] == dados["n"]:
                            c["status"] = "pronto"
                    job["log"].append("ERRO ao reeditar: " + str(e)[-400:])
                    self._salvar(job)
                continue
            try:
                self._executar(job, dados)
            except Exception as e:
                traceback.print_exc()
                job["status"], job["erro"] = "erro", str(e)[-1500:]
                job["log"].append("ERRO: " + str(e)[-400:])
                self._salvar(job)

    def _executar(self, job, cfg):
        pasta = PASTA_TRABALHOS / job["id"]
        job["status"] = "processando"
        perfil = perfis.obter(cfg["perfil"])
        extras = list(perfil["gatilhos"]) + [g.strip().lower() for g in str(cfg["gatilhos_extra"]).split(",") if g.strip()]

        def log(msg):
            job["log"].append(time.strftime("%H:%M:%S ") + msg)
            self._salvar(job)

        def etapa(nome, p):
            job["etapa"], job["progresso"] = nome, round(p, 1)
            self._salvar(job)

        # 1. download
        etapa("Baixando a live", 1)
        ultimo = [0.0]

        def prog_dl(f):
            if f - ultimo[0] > 0.01:
                ultimo[0] = f
                job["progresso"] = round(1 + 24 * f, 1)

        video, titulo_live, deslocamento = baixar(
            cfg["url"], str(pasta), log, prog_dl, cfg["cookies"], cfg["trecho_ini"], cfg["trecho_fim"])
        info = info_video(video)
        job["fonte"] = {"titulo": titulo_live, "duracao": info["dur"], "arquivo": video,
                        "resolucao": f"{info['w']}x{info['h']}"}
        log(f"Vídeo pronto: {titulo_live} ({seg_para_tempo(info['dur'])}, {info['w']}x{info['h']}).")

        # 2. sinais: volume, entonação da voz e chat
        etapa("Analisando o volume do áudio", 26)
        pcm_arq = str(pasta / "audio.pcm")
        audio.extrair_pcm(video, pcm_arq)
        pcm = audio.carregar(pcm_arq)
        db = audio.energia_db(pcm, HOP)
        n = len(db)
        s_volume = highlights.excitacao(db, HOP)

        s_voz = None
        if float(cfg["peso_voz"]) > 0:
            etapa("Analisando a entonação da voz", 27)
            pros = voz.prosodia(pcm, HOP, lambda f: job.__setitem__("progresso", round(27 + 4 * f, 1)))
            s_voz = highlights.sinal_voz(pros, HOP)

        local = eh_arquivo_local(cfg["url"])
        s_chat, chat_cont = None, None
        if cfg["usar_chat"] and float(cfg["peso_chat"]) > 0:
            etapa("Lendo o chat da live", 31)
            msgs = chat.obter_mensagens(cfg["url"], str(pasta), log, cfg["cookies"], video_local=local)
            if msgs:
                pesos, chat_cont = chat.sinal_chat(msgs, n, HOP, deslocamento, float(cfg["atraso_chat"]))
                s_chat = highlights.sinal_chat(pesos, HOP)
                log(f"Chat: {int(chat_cont.sum())} mensagens no período analisado.")
                if s_chat is None:
                    log("Chat com poucas mensagens, ele vai pesar pouco na escolha.")

        s_replay = None
        arq_heat = pasta / "heatmap.json"
        if arq_heat.exists() and float(cfg["peso_replay"]) > 0:
            import json as _json
            s_replay = highlights.sinal_replay(_json.loads(arq_heat.read_text(encoding="utf-8")), n, HOP, deslocamento)
            if s_replay is not None:
                log("Usando o gráfico 'Mais repetidos' do YouTube.")

        curva = highlights.combinar([
            (s_replay, float(cfg["peso_replay"])),
            (s_volume, float(cfg["peso_volume"])),
            (s_voz, float(cfg["peso_voz"])),
            (s_chat, float(cfg["peso_chat"])),
        ], n)
        usados = [nome for nome, s_, pk in (("mais repetidos", s_replay, "peso_replay"),
                                            ("volume", s_volume, "peso_volume"), ("voz", s_voz, "peso_voz"),
                                            ("chat", s_chat, "peso_chat")) if s_ is not None and float(cfg[pk]) > 0]
        log("Sinais usados: " + (", ".join(usados) or "nenhum"))

        def _media_em(sinal, t0, t1):
            if sinal is None:
                return None
            x = highlights.normalizar(sinal)[max(0, int(t0 / HOP)):max(int(t0 / HOP) + 1, int(t1 / HOP))]
            return round(float(np.mean(x)), 1) if len(x) else None

        def _chat_por_min(t0, t1):
            if chat_cont is None:
                return None
            i0, i1 = max(0, int(t0 / HOP)), max(int(t0 / HOP) + 1, int(t1 / HOP))
            janela = float(chat_cont[i0:i1].sum()) / max(1e-6, (i1 - i0) * HOP / 60)
            normal = float(np.median(chat_cont)) / (HOP / 60) or float(np.mean(chat_cont)) / (HOP / 60)
            return {"por_min": round(janela), "vezes": round(janela / normal, 1) if normal > 0 else None}

        # linha do tempo para o gráfico (1 ponto a cada 2 s)
        def _reduzir(x, k=4):
            if x is None:
                return None
            x = highlights.normalizar(x)
            m = len(x) // k * k
            return [round(float(v), 2) for v in x[:m].reshape(-1, k).max(axis=1)] if m else []

        salvar_json(pasta / "linha.json", {
            "passo": HOP * 4, "deslocamento": deslocamento, "total": _reduzir(curva),
            "volume": _reduzir(s_volume), "voz": _reduzir(s_voz), "chat": _reduzir(s_chat),
            "replay": _reduzir(s_replay),
        })

        # 3. candidatos
        dmin, dmax = float(cfg["dur_min"]), float(cfg["dur_max"])
        dmin, dmax = min(dmin, dmax), max(dmin, dmax)
        alvo = (dmin + dmax) / 2
        n_auto = max(0, int(cfg["n_clipes"]))
        lim_ini = (tempo_para_seg(cfg["trecho_ini"]) or 0.0) if local else 0.0
        lim_fim = tempo_para_seg(cfg["trecho_fim"]) if local else None

        manuais = [(max(0.0, a - deslocamento), b - deslocamento)
                   for a, b in _ler_manuais(cfg["manuais"], alvo)]
        cands = [{"i": a, "f": min(b, info["dur"]), "manual": True, "nota_sinais": 0.0, "pico": (a + b) / 2}
                 for a, b in manuais]
        if cfg.get("modo") == "clipe":
            if info["dur"] <= dmax * 1.3:
                # clipe curto: usa o clipe inteiro
                cands = [{"i": 0.0, "f": info["dur"], "manual": True, "nota_sinais": 0.0, "pico": info["dur"] * 0.6}]
                n_auto = 0
            else:
                n_auto = 1
            log("Modo clipe: " + ("usando o clipe inteiro." if not n_auto else "clipe longo, procurando o melhor trecho."))
        if n_auto:
            auto = highlights.candidatos(curva, HOP, alvo, max(n_auto * 3, n_auto + 3),
                                         lim_ini, lim_fim, excluir=manuais)
            for c in auto:
                c["manual"] = False
            cands += auto
        if not cands:
            raise RuntimeError("Nenhum momento encontrado. Verifique o trecho escolhido ou a duração da live.")
        for k, c in enumerate(cands, 1):
            c["id"] = k
        log(f"{len(cands)} momentos candidatos encontrados ({len(manuais)} manuais).")

        # 4. transcrição dos candidatos
        trans = self.transcritor(cfg["modelo"], log)
        for k, c in enumerate(cands):
            etapa(f"Transcrevendo momento {k + 1} de {len(cands)}", 30 + 35 * k / len(cands))
            a0 = max(0.0, c["i"] - 6)
            trecho = audio.trecho(pcm, a0, c["f"] + 6)
            c["segs"] = trans.transcrever(trecho, a0, cfg["idioma"]) if len(trecho) else []
            if not c["manual"]:
                highlights.ajustar_limites(c, c["segs"], dmin, dmax, info["dur"])
            c["segs"] = [s for s in c["segs"] if s["f"] > c["i"] and s["i"] < c["f"]]
            c["texto"] = " ".join(s["texto"] for s in c["segs"])

        # 5. pontuação
        etapa("Escolhendo os melhores momentos", 66)
        auto = [c for c in cands if not c["manual"]]
        if auto:
            # escalas absolutas (0-10): diferenças pequenas não viram diferenças enormes
            pf = 0.6 * max(0.0, float(cfg["peso_fala"]))
            for c in auto:
                s10 = min(10.0, max(0.0, 2.0 * c["nota_sinais"]))
                t10 = min(10.0, max(0.0, 1.5 * highlights.nota_texto(c["texto"], c["f"] - c["i"], extras)))
                c["nota"] = round((s10 + pf * t10) / (1 + pf), 1)
        origem = cfg.get("origem") or {}
        for c in cands:
            t0, t1 = c["pico"] - 6, c["pico"] + 4
            c["motivos"] = {
                "volume": _media_em(s_volume, t0, t1), "voz": _media_em(s_voz, t0, t1),
                "chat": _chat_por_min(c["pico"] - 10, c["pico"] + 10),
                "replay": _media_em(s_replay, t0, t1),
                "views": origem.get("views"),
                "fala": round(highlights.nota_texto(c["texto"], c["f"] - c["i"], extras), 1),
                "pico_no_corte": round(c["pico"] - c["i"], 1),
            }
        for c in cands:
            c.setdefault("nota", 10.0)
            c["titulo"] = highlights.titulo_automatico(c["segs"], extras=extras)
            if cfg.get("modo") == "clipe" and origem.get("titulo"):
                pal = re.sub(r"\s+", " ", origem["titulo"]).strip().split(" ")
                c["titulo"] = (" ".join(pal[:8]) + ("..." if len(pal) > 8 else "")).upper()
            c["ia"] = {}

        chave = cfg["ia_chave"]
        if chave and auto:
            log("Pedindo para a IA avaliar os momentos e criar títulos...")
            res = ai.avaliar(cands, chave, cfg["ia_modelo"], log, perfil["contexto_ia"])
            for c in cands:
                if c["id"] in res:
                    r = res[c["id"]]
                    c["ia"] = r
                    if not c["manual"]:
                        c["nota"] = round(0.7 * r["nota"] + 0.3 * c["nota"], 1)
                    if r["titulo"]:
                        c["titulo"] = r["titulo"].upper()

        for c in sorted(auto, key=lambda c: c["nota"], reverse=True):
            log(f"  candidato {seg_para_tempo(c['pico'] + deslocamento)}: nota {c['nota']} "
                f"(sinais {c['nota_sinais']:.2f}, fala {c['motivos']['fala']})")
        escolhidos = [c for c in cands if c["manual"]]
        escolhidos += sorted(auto, key=lambda c: c["nota"], reverse=True)[:n_auto]
        escolhidos.sort(key=lambda c: (-c["nota"] if not c["manual"] else -11, c["i"]))
        log(f"{len(escolhidos)} cortes selecionados. Renderizando...")

        # 6. renderização
        if job.get("marca_pendente") is not None:
            cfg["marca"] = job.pop("marca_pendente")
        pasta_clipes = pasta / "clipes"
        for k, c in enumerate(escolhidos, 1):
            etapa(f"Editando corte {k} de {len(escolhidos)}", 68 + 31 * (k - 1) / len(escolhidos))
            palavras = [{"w": p["w"], "i": round(p["i"] - c["i"], 2), "f": round(p["f"] - c["i"], 2)}
                        for s in c["segs"] for p in s["palavras"] if c["i"] <= p["i"] < c["f"]]
            nome = f"corte_{k:02d}.mp4"
            clipe = {
                "n": k, "arquivo": f"clipes/{nome}", "inicio": c["i"], "fim": c["f"],
                "na_live": f"{seg_para_tempo(c['i'] + deslocamento)} – {seg_para_tempo(c['f'] + deslocamento)}",
                "duracao": round(c["f"] - c["i"], 1), "nota": c["nota"], "manual": c["manual"],
                "titulo": c["titulo"], "texto": c["texto"], "palavras": palavras, "motivos": c["motivos"],
                "descricao": descricao.gerar(c["titulo"], c["texto"], cfg["perfil"], cfg["hashtags"],
                                             c["ia"].get("descricao", ""), c["ia"].get("hashtags", ()), origem),
                "opcoes": {}, "posts": {},
                "status": "editando", "versao": 1,
            }
            job["clipes"].append(clipe)
            if job.get("marca_pendente") is not None:
                cfg["marca"] = job.pop("marca_pendente")
                for anterior in job["clipes"][:-1]:  # refaz os que já saíram com o @ antigo
                    self.fila.put(("editar", job["id"], {"n": anterior["n"], "forcar": True}))
            renderizar(video, c["i"], c["f"] - c["i"], str(pasta_clipes), nome, info, cfg, palavras, c["titulo"])
            clipe["status"] = "pronto"
            log(f"Corte {k} pronto ({clipe['na_live']}).")

        job["cfg_render"] = {k: cfg[k] for k in OPCOES_RENDER}
        job["deslocamento"] = deslocamento
        del pcm
        try:
            os.remove(pcm_arq)
        except OSError:
            pass
        if cfg.get("apagar_live") and not local:
            try:
                os.remove(video)
                job["fonte"]["arquivo"] = ""
                log("Arquivo da live apagado para liberar espaço (não será possível reeditar).")
            except OSError:
                pass
        job["status"], job["etapa"], job["progresso"] = "concluido", "Concluído", 100
        log("Tudo pronto!")
        if cfg.get("depois") == "postar" and cfg.get("postar_em"):
            redes = list(cfg["postar_em"])
        else:
            auto = self.config_auto() or {}
            redes = list(auto.get("redes") or []) if auto.get("ativo") else []
        if redes and self.ao_terminar:
            log("Postando automaticamente em: " + ", ".join(redes))
            for clipe in job["clipes"]:
                self.ao_terminar(job, clipe, redes)

    def _refazer(self, job, dados):
        video = job["fonte"].get("arquivo")
        clipe = next(c for c in job["clipes"] if c["n"] == dados["n"])
        if not video or not os.path.isfile(video):
            raise RuntimeError("O arquivo da live não existe mais, não dá para reeditar este corte.")
        clipe["status"] = "editando"
        self._salvar(job)
        info = info_video(video)

        if "titulo" in dados:
            clipe["titulo"] = str(dados["titulo"]).strip()
        for k in ("legendas", "mostrar_titulo"):
            if k in dados:
                clipe.setdefault("opcoes", {})[k] = bool(dados[k])
        if "marca" in dados:
            clipe.setdefault("opcoes", {})["marca"] = str(dados["marca"]).strip()

        ini = float(dados.get("inicio", clipe["inicio"]))
        fim = float(dados.get("fim", clipe["fim"]))
        ini, fim = max(0.0, min(ini, fim - 1)), min(info["dur"] or fim, max(fim, ini + 1))
        if abs(ini - clipe["inicio"]) > 0.05 or abs(fim - clipe["fim"]) > 0.05:
            # novo trecho: transcreve de novo para as legendas baterem
            log = lambda m: job["log"].append(time.strftime("%H:%M:%S ") + m)
            modelo = (job.get("cfg") or {}).get("modelo", "small")
            idioma = (job.get("cfg") or {}).get("idioma", "pt")
            trecho = audio.trecho_de_video(video, ini, fim)
            segs = self.transcritor(modelo, log).transcrever(trecho, ini, idioma) if len(trecho) else []
            clipe["palavras"] = [{"w": p["w"], "i": round(p["i"] - ini, 2), "f": round(p["f"] - ini, 2)}
                                 for s_ in segs for p in s_["palavras"] if ini <= p["i"] < fim]
            clipe["texto"] = " ".join(s_["texto"] for s_ in segs)
            clipe["inicio"], clipe["fim"] = round(ini, 2), round(fim, 2)
            clipe["duracao"] = round(fim - ini, 1)
            d = job.get("deslocamento", 0.0)
            clipe["na_live"] = f"{seg_para_tempo(ini + d)} – {seg_para_tempo(fim + d)}"

        cfg = {**job.get("cfg_render", job["cfg"])}
        op = clipe.get("opcoes", {})
        if "legendas" in op:
            cfg["legendas"] = op["legendas"]
        if "mostrar_titulo" in op:
            cfg["titulo"] = op["mostrar_titulo"]
        if "marca" in op:
            cfg["marca"] = op["marca"]
        pasta = PASTA_TRABALHOS / job["id"] / "clipes"
        renderizar(video, clipe["inicio"], clipe["fim"] - clipe["inicio"], str(pasta),
                   os.path.basename(clipe["arquivo"]), info, cfg, clipe["palavras"], clipe["titulo"])
        clipe["status"], clipe["versao"] = "pronto", clipe.get("versao", 1) + 1
        job["log"].append(time.strftime("%H:%M:%S ") + f"Corte {clipe['n']} reeditado.")
        self._salvar(job)
