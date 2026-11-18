"""Fila de publicações no TikTok (Content Posting API) e no Instagram (Reels, upload retomável)."""
import os
import queue
import threading
import time
import traceback
import uuid

from .contas import GRAPH, TIKTOK_API, ErroAPI, http
from .utils import salvar_json

ARQ_NOME = "publicacoes.json"
ESPERA = 5  # segundos entre consultas de status


class Publicador:
    def __init__(self, contas, gerente, pasta_dados):
        self.contas = contas
        self.gerente = gerente
        self.arq = pasta_dados / ARQ_NOME
        self.fila = queue.Queue()
        self.posts = []
        if self.arq.exists():
            import json
            try:
                self.posts = json.loads(self.arq.read_text(encoding="utf-8"))
            except ValueError:
                self.posts = []
            for p in self.posts:
                if p["status"] in ("na fila", "enviando", "processando"):
                    p["status"], p["msg"] = "erro", "Interrompido (o programa foi fechado)."
        threading.Thread(target=self._trabalhador, daemon=True).start()

    def _salvar(self):
        salvar_json(self.arq, self.posts)

    def listar(self):
        return sorted(self.posts, key=lambda p: p["criado"], reverse=True)

    # ------------------------------------------------------------------
    def agendar(self, job, clipe, plataforma, legenda, opcoes=None):
        opcoes = dict(opcoes or {})
        tk = self.contas.dados.get("tiktok", {})
        if plataforma == "tiktok":
            opcoes.setdefault("modo", tk.get("padrao_modo", "rascunho"))
            opcoes.setdefault("privacidade", tk.get("padrao_privacidade", "SELF_ONLY"))
        post = {
            "id": uuid.uuid4().hex[:10], "criado": time.time(), "job": job["id"], "n": clipe["n"],
            "plataforma": plataforma, "titulo": clipe.get("titulo", ""), "legenda": legenda,
            "opcoes": opcoes, "status": "na fila", "msg": "", "link": "",
            "arquivo": clipe["arquivo"],
        }
        self.posts.append(post)
        clipe.setdefault("posts", {})[plataforma] = {"id": post["id"], "status": "na fila"}
        self._salvar()
        self.gerente._salvar(job)
        self.fila.put(post["id"])
        return post

    def ao_terminar(self, job, clipe, plataformas):
        for p in plataformas:
            self.agendar(job, clipe, p, clipe.get("descricao", ""))

    # ------------------------------------------------------------------
    def _status(self, post, status, msg="", link=None):
        post["status"], post["msg"] = status, msg
        if link:
            post["link"] = link
        job = self.gerente.obter(post["job"])
        if job:
            for c in job["clipes"]:
                if c["n"] == post["n"]:
                    c.setdefault("posts", {})[post["plataforma"]] = {
                        "id": post["id"], "status": status, "msg": msg, "link": post.get("link", "")}
            self.gerente._salvar(job)
        self._salvar()

    def _trabalhador(self):
        while True:
            pid = self.fila.get()
            post = next((p for p in self.posts if p["id"] == pid), None)
            if not post:
                continue
            caminho = self.gerente.caminho_clipe(post["job"], post["arquivo"])
            try:
                if not caminho or not os.path.isfile(caminho):
                    raise ErroAPI("Arquivo do corte não encontrado.")
                if post["plataforma"] == "tiktok":
                    self._tiktok(post, caminho)
                else:
                    self._instagram(post, caminho)
            except Exception as e:
                traceback.print_exc()
                self._status(post, "erro", str(e)[:400])

    # ------------------------------------------------------------------ TikTok
    def _tiktok(self, post, caminho):
        op = post["opcoes"]
        token = self.contas.tiktok_token()
        auth = {"Authorization": f"Bearer {token}"}
        tamanho = os.path.getsize(caminho)
        if tamanho <= 64 * 1024 * 1024:
            pedaco, total = tamanho, 1
        else:
            pedaco = 32 * 1024 * 1024
            total = tamanho // pedaco
        fonte = {"source": "FILE_UPLOAD", "video_size": tamanho, "chunk_size": pedaco, "total_chunk_count": total}

        self._status(post, "enviando", "Preparando envio ao TikTok...")
        if op.get("modo") == "direto":
            criador = self.contas.tiktok_criador()
            opcoes_priv = criador.get("privacy_level_options") or ["SELF_ONLY"]
            priv = op.get("privacidade") if op.get("privacidade") in opcoes_priv else opcoes_priv[-1]
            corpo = {
                "post_info": {
                    "title": post["legenda"][:2200], "privacy_level": priv,
                    "disable_comment": not op.get("comentarios", True),
                    "disable_duet": not op.get("dueto", True), "disable_stitch": not op.get("stitch", True),
                    "video_cover_timestamp_ms": 1000,
                },
                "source_info": fonte,
            }
            r = http("POST", f"{TIKTOK_API}/v2/post/publish/video/init/", json_body=corpo, headers=auth)
        else:
            r = http("POST", f"{TIKTOK_API}/v2/post/publish/inbox/video/init/",
                     json_body={"source_info": fonte}, headers=auth)
        dados = r.get("data") or {}
        if (r.get("error") or {}).get("code", "ok") != "ok" or not dados.get("upload_url"):
            raise ErroAPI(f"TikTok recusou: {(r.get('error') or {}).get('message') or r}")
        publish_id, url = dados["publish_id"], dados["upload_url"]

        with open(caminho, "rb") as f:
            for k in range(total):
                inicio = k * pedaco
                fim = tamanho - 1 if k == total - 1 else inicio + pedaco - 1
                f.seek(inicio)
                bloco = f.read(fim - inicio + 1)
                self._status(post, "enviando", f"Enviando vídeo ({k + 1}/{total})...")
                http("PUT", url, bruto=bloco, timeout=600, headers={
                    "Content-Type": "video/mp4", "Content-Length": str(len(bloco)),
                    "Content-Range": f"bytes {inicio}-{fim}/{tamanho}",
                })

        self._status(post, "processando", "TikTok processando o vídeo...")
        for _ in range(120):
            time.sleep(ESPERA)
            st = http("POST", f"{TIKTOK_API}/v2/post/publish/status/fetch/",
                      json_body={"publish_id": publish_id}, headers={"Authorization": f"Bearer {self.contas.tiktok_token()}"})
            d = st.get("data") or {}
            s = d.get("status", "")
            if s == "PUBLISH_COMPLETE":
                ids = d.get("publicaly_available_post_id") or d.get("publicly_available_post_id") or []
                return self._status(post, "publicado", "Publicado no TikTok.",
                                    f"https://www.tiktok.com/video/{ids[0]}" if ids else None)
            if s == "SEND_TO_USER_INBOX":
                return self._status(post, "rascunho", "Enviado! Abra o TikTok: o vídeo está nas notificações/rascunhos para você postar.")
            if s == "FAILED":
                raise ErroAPI(f"TikTok falhou: {d.get('fail_reason', 'motivo desconhecido')}")
        raise ErroAPI("TikTok demorou demais para processar. Confira o app.")

    # ------------------------------------------------------------------ Instagram
    def _instagram(self, post, caminho):
        ig = self.contas.dados.get("instagram", {})
        if not (ig.get("token") and ig.get("ig_user_id")):
            raise ErroAPI("Instagram não conectado. Vá na aba Contas.")
        if ig.get("expira") and time.time() > ig["expira"]:
            raise ErroAPI("O token do Instagram expirou. Gere um novo e conecte de novo na aba Contas.")
        base = f"{GRAPH}/{ig.get('versao', 'v23.0')}"
        auth = {"Authorization": f"OAuth {ig['token']}"}
        op = post["opcoes"]

        self._status(post, "enviando", "Criando o Reels no Instagram...")
        r = http("POST", f"{base}/{ig['ig_user_id']}/media", headers=auth, json_body={
            "media_type": "REELS", "upload_type": "resumable", "caption": post["legenda"][:2200],
            "share_to_feed": bool(op.get("feed", True)),
        })
        cont_id, uri = r.get("id"), r.get("uri")
        if not cont_id or not uri:
            raise ErroAPI(f"Instagram não criou o Reels: {r}")

        tamanho = os.path.getsize(caminho)
        self._status(post, "enviando", "Enviando o vídeo ao Instagram...")
        with open(caminho, "rb") as f:
            http("POST", uri, bruto=f.read(), timeout=900,
                 headers={**auth, "offset": "0", "file_size": str(tamanho), "Content-Type": "application/octet-stream"})

        self._status(post, "processando", "Instagram processando o vídeo...")
        for _ in range(120):
            time.sleep(ESPERA)
            st = http("GET", f"{base}/{cont_id}", dados={"fields": "status_code,status"}, headers=auth)
            code = st.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise ErroAPI(f"Instagram recusou o vídeo: {st.get('status', code)}")
        else:
            raise ErroAPI("Instagram demorou demais para processar o vídeo.")

        pub = http("POST", f"{base}/{ig['ig_user_id']}/media_publish", headers=auth,
                   json_body={"creation_id": cont_id})
        link = None
        try:
            link = http("GET", f"{base}/{pub['id']}", dados={"fields": "permalink"}, headers=auth).get("permalink")
        except Exception:
            pass
        self._status(post, "publicado", "Publicado no Instagram.", link)
