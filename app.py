"""Lab de Cortes — abra http://127.0.0.1:5000 depois de iniciar."""
import os
import subprocess
import sys
import threading
import webbrowser

from flask import Flask, abort, jsonify, render_template, request, send_file, send_from_directory

from lab import perfis
from lab.contas import PASTA_DADOS, Contas, ErroAPI
from lab.descricao import gerar as gerar_descricao
from lab.pipeline import PADRAO, PASTA_TRABALHOS, Gerenciador
from lab.publicar import Publicador
from lab.radar import PLATAFORMAS, Radar
from lab.utils import salvar_json
from lab.render import PRESETS_COR

app = Flask(__name__)
gerente = Gerenciador()
contas = Contas()
publicador = Publicador(contas, gerente, PASTA_DADOS)
gerente.ao_terminar = publicador.ao_terminar
radar = Radar(gerente, PASTA_DADOS)

# ---- botão "postar automático" (vale para o modo manual e para o radar)
ARQ_AUTO = PASTA_DADOS / "auto_postar.json"


def ler_auto():
    import json
    try:
        return json.loads(ARQ_AUTO.read_text(encoding="utf-8"))
    except Exception:
        return {"ativo": False, "redes": []}


gerente.config_auto = ler_auto


def erro(msg, codigo=400):
    return jsonify({"erro": str(msg)}), codigo


@app.errorhandler(ErroAPI)
def _erro_api(e):
    return erro(e)


@app.get("/")
def inicio():
    perfis_front = {k: {"nome": v["nome"], "padrao": v["padrao"], "gatilhos": v["gatilhos"],
                        "hashtags_gerais": v["hashtags_gerais"]} for k, v in perfis.PERFIS.items()}
    return render_template("index.html", padrao=PADRAO, presets=list(PRESETS_COR), perfis=perfis_front)


# ------------------------------------------------------------------ trabalhos
@app.get("/api/jobs")
def listar():
    return jsonify(gerente.listar())


@app.post("/api/jobs")
def criar():
    cfg = request.get_json(force=True) or {}
    if not str(cfg.get("url", "")).strip():
        return erro("Cole o link da live ou o caminho de um arquivo de vídeo.")
    return jsonify(gerente.criar(cfg))


@app.get("/api/jobs/<jid>")
def obter(jid):
    job = gerente.obter(jid)
    return jsonify(job) if job else erro("não encontrado", 404)


@app.post("/api/jobs/<jid>/clipes/<int:n>/reeditar")
def reeditar(jid, n):
    if not gerente.obter(jid):
        abort(404)
    gerente.rerenderizar(jid, n, str((request.get_json(force=True) or {}).get("titulo", "")).strip())
    return jsonify({"ok": True})


@app.post("/api/jobs/<jid>/clipes/<int:n>/editar")
def editar(jid, n):
    if not gerente.obter(jid):
        abort(404)
    dados = request.get_json(force=True) or {}
    permitidos = {k: dados[k] for k in ("titulo", "descricao", "inicio", "fim", "legendas", "mostrar_titulo", "marca") if k in dados}
    gerente.editar(jid, n, permitidos)
    return jsonify({"ok": True})


@app.post("/api/jobs/<jid>/clipes/<int:n>/descricao")
def nova_descricao(jid, n):
    job = gerente.obter(jid) or abort(404)
    c = next((c for c in job["clipes"] if c["n"] == n), None) or abort(404)
    d = request.get_json(force=True) or {}
    return jsonify({"descricao": gerar_descricao(d.get("titulo", c["titulo"]), c.get("texto", ""),
                                                 job.get("perfil", "gta6"), job["cfg"].get("hashtags", ""))})


@app.get("/fonte/<jid>")
def fonte(jid):
    job = gerente.obter(jid) or abort(404)
    caminho = (job.get("fonte") or {}).get("arquivo")
    if not caminho or not os.path.isfile(caminho):
        abort(404)
    return send_file(caminho, conditional=True)


@app.post("/api/jobs/<jid>/abrir-pasta")
def abrir_pasta(jid):
    pasta = PASTA_TRABALHOS / jid / "clipes"
    if not pasta.exists():
        pasta = PASTA_TRABALHOS / jid
    if sys.platform.startswith("win"):
        os.startfile(pasta)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(pasta)])
    else:
        subprocess.Popen(["xdg-open", str(pasta)])
    return jsonify({"ok": True})


@app.get("/arquivos/<jid>/<path:caminho>")
def arquivos(jid, caminho):
    return send_from_directory(PASTA_TRABALHOS / jid, caminho, conditional=True)


# ------------------------------------------------------------------ contas
@app.get("/api/contas")
def contas_resumo():
    return jsonify(contas.resumo())


@app.post("/api/contas/tiktok/config")
def tiktok_config():
    d = request.get_json(force=True) or {}
    contas.tiktok_configurar(d.get("client_key", ""), d.get("client_secret", ""), d.get("redirect_uri", ""))
    return jsonify(contas.resumo())


@app.post("/api/contas/tiktok/padroes")
def tiktok_padroes():
    d = request.get_json(force=True) or {}
    contas.tiktok_padroes(d.get("modo"), d.get("privacidade"))
    return jsonify(contas.resumo())


@app.get("/api/contas/tiktok/login")
def tiktok_login():
    return jsonify({"url": contas.tiktok_url_login()})


@app.get("/contas/tiktok/callback")
def tiktok_callback():
    if request.args.get("error"):
        return render_template("callback.html", ok=False, msg=request.args.get("error_description") or request.args["error"])
    try:
        u = contas.tiktok_trocar_codigo(request.args.get("code", ""), request.args.get("state"))
        return render_template("callback.html", ok=True, msg=f"TikTok conectado: {u.get('display_name', '')}")
    except ErroAPI as e:
        return render_template("callback.html", ok=False, msg=str(e))


@app.post("/api/contas/tiktok/codigo")
def tiktok_codigo():
    codigo = str((request.get_json(force=True) or {}).get("codigo", "")).strip()
    if "code=" in codigo:  # colou a URL inteira
        from urllib.parse import parse_qs, urlparse
        codigo = (parse_qs(urlparse(codigo).query).get("code") or [""])[0]
    contas.tiktok_trocar_codigo(codigo)
    return jsonify(contas.resumo())


@app.get("/api/contas/tiktok/criador")
def tiktok_criador():
    return jsonify(contas.tiktok_criador())


@app.post("/api/contas/tiktok/desconectar")
def tiktok_desconectar():
    contas.tiktok_desconectar()
    return jsonify(contas.resumo())


@app.post("/api/contas/instagram")
def instagram_conectar():
    d = request.get_json(force=True) or {}
    contas.instagram_conectar(d.get("app_id", ""), d.get("app_secret", ""), d.get("token", ""),
                              d.get("versao", "v23.0"))
    return jsonify(contas.resumo())


@app.post("/api/contas/instagram/escolher")
def instagram_escolher():
    contas.instagram_escolher(str((request.get_json(force=True) or {}).get("id", "")))
    return jsonify(contas.resumo())


@app.post("/api/contas/instagram/desconectar")
def instagram_desconectar():
    contas.instagram_desconectar()
    return jsonify(contas.resumo())


# ------------------------------------------------------------------ postar automático
@app.get("/api/auto")
def auto_ler():
    return jsonify(ler_auto())


@app.post("/api/auto")
def auto_salvar():
    d = request.get_json(force=True) or {}
    redes = [r for r in d.get("redes", []) if r in ("tiktok", "instagram")]
    resumo = contas.resumo()
    faltando = [r for r in redes if not resumo[r]["conectado"]]
    if d.get("ativo") and faltando:
        return erro("Conecte " + " e ".join("TikTok" if r == "tiktok" else "Instagram" for r in faltando) + " primeiro.")
    if d.get("ativo") and not redes:
        return erro("Marque TikTok e/ou Instagram.")
    dados = {"ativo": bool(d.get("ativo")), "redes": redes}
    salvar_json(ARQ_AUTO, dados)
    return jsonify(dados)


# ------------------------------------------------------------------ radar de streamers
@app.get("/api/radar")
def radar_ler():
    r = radar.resumo()
    r.pop("cfg_base", None)
    r["streamers"] = [{k: v for k, v in st.items() if k != "vistos"} for st in r["streamers"]]
    r["plataformas"] = PLATAFORMAS
    return jsonify(r)


@app.post("/api/radar/config")
def radar_config():
    radar.configurar(request.get_json(force=True) or {})
    return radar_ler()


@app.post("/api/radar/streamers")
def radar_add():
    d = request.get_json(force=True) or {}
    try:
        radar.adicionar(d.get("usuario", ""), d.get("plataforma", "twitch"), d.get("tipo", "clipes"))
    except ValueError as e:
        return erro(e)
    return radar_ler()


@app.post("/api/radar/streamers/<sid>")
def radar_alterar(sid):
    try:
        radar.alterar(sid, request.get_json(force=True) or {})
    except ValueError as e:
        return erro(e)
    return radar_ler()


@app.delete("/api/radar/streamers/<sid>")
def radar_remover(sid):
    radar.remover(sid)
    return radar_ler()


@app.post("/api/radar/descobrir")
def radar_descobrir():
    radar.descobrir_agora()
    return jsonify({"ok": True})


@app.post("/api/marca")
def trocar_marca():
    d = request.get_json(force=True) or {}
    marca = str(d.get("marca", "")).strip()
    res = gerente.trocar_marca(marca, d.get("job"))
    if not d.get("job"):  # vale também para os próximos cortes do radar
        base = dict(radar.dados.get("cfg_base") or {})
        base["marca"] = marca
        radar.configurar({"cfg_base": base})
    return jsonify(res)


@app.post("/api/radar/verificar")
def radar_verificar():
    radar.verificar_agora((request.get_json(force=True) or {}).get("id"))
    return jsonify({"ok": True})


# ------------------------------------------------------------------ publicações
@app.get("/api/publicacoes")
def publicacoes():
    return jsonify(publicador.listar())


@app.post("/api/jobs/<jid>/clipes/<int:n>/postar")
def postar(jid, n):
    job = gerente.obter(jid) or abort(404)
    clipe = next((c for c in job["clipes"] if c["n"] == n), None) or abort(404)
    if clipe.get("status") != "pronto":
        return erro("Espere o corte terminar de editar.")
    d = request.get_json(force=True) or {}
    legenda = str(d.get("legenda") or clipe.get("descricao", ""))
    clipe["descricao"] = legenda
    resumo = contas.resumo()
    feitos = []
    for plat in d.get("plataformas", []):
        if plat not in ("tiktok", "instagram"):
            continue
        if not resumo[plat]["conectado"]:
            return erro(f"Conecte o {'TikTok' if plat == 'tiktok' else 'Instagram'} na aba Contas primeiro.")
        feitos.append(publicador.agendar(job, clipe, plat, legenda, (d.get("opcoes") or {}).get(plat)))
    if not feitos:
        return erro("Escolha pelo menos uma rede.")
    return jsonify({"ok": True, "posts": feitos})


if __name__ == "__main__":
    porta = int(os.environ.get("PORTA", 5000))
    if "--sem-navegador" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{porta}")).start()
    print(f"\n  Lab de Cortes rodando em http://127.0.0.1:{porta}  (Ctrl+C para sair)\n")
    app.run(host="127.0.0.1", port=porta, debug=False, threaded=True)
