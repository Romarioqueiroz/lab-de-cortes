"""Conexão com as contas do TikTok e do Instagram (tokens ficam só no seu PC, em dados/contas.json)."""
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .utils import salvar_json

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "dados"
ARQ = PASTA_DADOS / "contas.json"

TIKTOK_AUTH = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_API = os.environ.get("LAB_TIKTOK_API", "https://open.tiktokapis.com")
GRAPH = os.environ.get("LAB_GRAPH", "https://graph.facebook.com")
TIKTOK_ESCOPOS = "user.info.basic,video.publish,video.upload"


class ErroAPI(RuntimeError):
    pass


def http(metodo, url, dados=None, headers=None, json_body=None, form=None, bruto=None, timeout=120):
    headers = dict(headers or {})
    corpo = None
    if json_body is not None:
        corpo = json.dumps(json_body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json; charset=UTF-8")
    elif form is not None:
        corpo = urllib.parse.urlencode(form).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif bruto is not None:
        corpo = bruto
    if dados:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(dados)
    req = urllib.request.Request(url, data=corpo, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(txt)
        except ValueError:
            raise ErroAPI(f"HTTP {e.code}: {txt[:300]}")
        err = j.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or err.get("error_user_msg") or err.get("code")
        else:
            msg = j.get("error_description") or err or txt[:300]
        raise ErroAPI(f"HTTP {e.code}: {msg}")
    try:
        return json.loads(txt) if txt.strip() else {}
    except ValueError:
        return {"_texto": txt}


class Contas:
    def __init__(self):
        PASTA_DADOS.mkdir(exist_ok=True)
        self.dados = {"tiktok": {}, "instagram": {}}
        if ARQ.exists():
            try:
                self.dados.update(json.loads(ARQ.read_text(encoding="utf-8")))
            except ValueError:
                pass
        self._estado_oauth = {}

    def salvar(self):
        salvar_json(ARQ, self.dados)

    # ------------------------------------------------------------------ resumo (sem segredos)
    def resumo(self):
        tk, ig = self.dados.get("tiktok", {}), self.dados.get("instagram", {})
        return {
            "tiktok": {
                "configurado": bool(tk.get("client_key")),
                "conectado": bool(tk.get("refresh_token")),
                "nome": (tk.get("usuario") or {}).get("display_name", ""),
                "avatar": (tk.get("usuario") or {}).get("avatar_url", ""),
                "client_key": tk.get("client_key", ""),
                "redirect_uri": tk.get("redirect_uri", ""),
                "refresh_expira": tk.get("refresh_expira", 0),
                "padrao_modo": tk.get("padrao_modo", "rascunho"),
                "padrao_privacidade": tk.get("padrao_privacidade", "SELF_ONLY"),
            },
            "instagram": {
                "conectado": bool(ig.get("token") and ig.get("ig_user_id")),
                "nome": ig.get("username", ""),
                "pagina": ig.get("page_name", ""),
                "app_id": ig.get("app_id", ""),
                "versao": ig.get("versao", "v23.0"),
                "expira": ig.get("expira", 0),
                "contas": ig.get("contas", []),
            },
        }

    # ------------------------------------------------------------------ TikTok
    def tiktok_configurar(self, client_key, client_secret, redirect_uri):
        tk = self.dados.setdefault("tiktok", {})
        tk["client_key"] = client_key.strip()
        if client_secret.strip():
            tk["client_secret"] = client_secret.strip()
        tk["redirect_uri"] = redirect_uri.strip()
        self.salvar()

    def tiktok_padroes(self, modo=None, privacidade=None):
        tk = self.dados.setdefault("tiktok", {})
        if modo:
            tk["padrao_modo"] = modo
        if privacidade:
            tk["padrao_privacidade"] = privacidade
        self.salvar()

    def tiktok_url_login(self):
        tk = self.dados.get("tiktok", {})
        if not (tk.get("client_key") and tk.get("redirect_uri")):
            raise ErroAPI("Preencha o Client Key, o Client Secret e a Redirect URI primeiro.")
        estado = secrets.token_urlsafe(16)
        self._estado_oauth[estado] = time.time()
        q = urllib.parse.urlencode({
            "client_key": tk["client_key"], "response_type": "code", "scope": TIKTOK_ESCOPOS,
            "redirect_uri": tk["redirect_uri"], "state": estado,
        })
        return f"{TIKTOK_AUTH}?{q}"

    def tiktok_trocar_codigo(self, codigo, estado=None):
        if estado is not None and estado not in self._estado_oauth:
            raise ErroAPI("Login expirado ou de outra sessão. Clique em 'Conectar TikTok' de novo.")
        self._estado_oauth.pop(estado, None)
        tk = self.dados.get("tiktok", {})
        r = http("POST", f"{TIKTOK_API}/v2/oauth/token/", form={
            "client_key": tk["client_key"], "client_secret": tk.get("client_secret", ""),
            "code": urllib.parse.unquote(codigo), "grant_type": "authorization_code",
            "redirect_uri": tk["redirect_uri"],
        })
        self._tiktok_guardar_token(r)
        try:
            info = http("GET", f"{TIKTOK_API}/v2/user/info/", dados={"fields": "open_id,display_name,avatar_url"},
                        headers={"Authorization": f"Bearer {tk['access_token']}"})
            tk["usuario"] = (info.get("data") or {}).get("user", {})
        except ErroAPI:
            tk["usuario"] = {"display_name": "conta conectada"}
        self.salvar()
        return tk["usuario"]

    def _tiktok_guardar_token(self, r):
        if "access_token" not in r:
            raise ErroAPI(f"TikTok recusou o login: {r.get('error_description') or r.get('error') or r}")
        tk = self.dados["tiktok"]
        agora = time.time()
        tk["access_token"] = r["access_token"]
        tk["expira"] = agora + int(r.get("expires_in", 86400)) - 120
        if r.get("refresh_token"):
            tk["refresh_token"] = r["refresh_token"]
            tk["refresh_expira"] = agora + int(r.get("refresh_expires_in", 31536000))
        tk["open_id"] = r.get("open_id", tk.get("open_id"))
        self.salvar()

    def tiktok_token(self):
        tk = self.dados.get("tiktok", {})
        if not tk.get("refresh_token"):
            raise ErroAPI("TikTok não conectado. Vá na aba Contas.")
        if time.time() > tk.get("expira", 0):
            r = http("POST", f"{TIKTOK_API}/v2/oauth/token/", form={
                "client_key": tk["client_key"], "client_secret": tk.get("client_secret", ""),
                "grant_type": "refresh_token", "refresh_token": tk["refresh_token"],
            })
            self._tiktok_guardar_token(r)
        return tk["access_token"]

    def tiktok_criador(self):
        r = http("POST", f"{TIKTOK_API}/v2/post/publish/creator_info/query/", json_body={},
                 headers={"Authorization": f"Bearer {self.tiktok_token()}"})
        return r.get("data") or {}

    def tiktok_desconectar(self):
        tk = self.dados.get("tiktok", {})
        for k in ("access_token", "refresh_token", "expira", "refresh_expira", "usuario", "open_id"):
            tk.pop(k, None)
        self.salvar()

    # ------------------------------------------------------------------ Instagram (Facebook Login for Business)
    def instagram_conectar(self, app_id, app_secret, token, versao="v23.0", ig_user_id=""):
        ig = self.dados.setdefault("instagram", {})
        ig["app_id"], ig["versao"] = app_id.strip(), (versao or "v23.0").strip()
        if app_secret.strip():
            ig["app_secret"] = app_secret.strip()
        base = f"{GRAPH}/{ig['versao']}"
        token = token.strip()
        expira = time.time() + 3600
        if ig.get("app_secret") and ig.get("app_id"):
            r = http("GET", f"{base}/oauth/access_token", dados={
                "grant_type": "fb_exchange_token", "client_id": ig["app_id"],
                "client_secret": ig["app_secret"], "fb_exchange_token": token,
            })
            token = r.get("access_token", token)
            expira = time.time() + int(r.get("expires_in", 60 * 86400))
        r = http("GET", f"{base}/me/accounts", dados={
            "fields": "name,instagram_business_account{id,username}", "access_token": token, "limit": 50,
        })
        contas = [
            {"pagina": p.get("name", ""), "id": p["instagram_business_account"]["id"],
             "username": p["instagram_business_account"].get("username", "")}
            for p in r.get("data", []) if p.get("instagram_business_account")
        ]
        if not contas:
            raise ErroAPI("Nenhuma conta profissional do Instagram ligada às suas Páginas do Facebook foi "
                          "encontrada. Confira se o Instagram é Profissional e está ligado a uma Página, e "
                          "se o token tem as permissões pedidas.")
        escolhida = next((c for c in contas if c["id"] == ig_user_id), contas[0])
        ig.update({"token": token, "expira": expira, "contas": contas, "ig_user_id": escolhida["id"],
                   "username": escolhida["username"], "page_name": escolhida["pagina"]})
        self.salvar()
        return escolhida

    def instagram_escolher(self, ig_user_id):
        ig = self.dados.get("instagram", {})
        c = next((c for c in ig.get("contas", []) if c["id"] == ig_user_id), None)
        if c:
            ig.update({"ig_user_id": c["id"], "username": c["username"], "page_name": c["pagina"]})
            self.salvar()

    def instagram_desconectar(self):
        ig = self.dados.get("instagram", {})
        for k in ("token", "expira", "contas", "ig_user_id", "username", "page_name"):
            ig.pop(k, None)
        self.salvar()
