"""Gera a legenda/descrição do post com hashtags (com IA, se houver chave, ou por modelo)."""
import re

from . import perfis


def _limpar_tag(t):
    t = t.strip()
    if not t:
        return ""
    if not t.startswith("#"):
        t = "#" + t
    return "#" + re.sub(r"[^\wÀ-ÿ]", "", t[1:])


def montar_hashtags(texto, perfil_nome, fixas="", extras_ia=(), limite=12):
    perfil = perfis.obter(perfil_nome)
    tags = []

    def add(t):
        t = _limpar_tag(t)
        if len(t) > 1 and t.lower() not in [x.lower() for x in tags]:
            tags.append(t)

    for t in re.split(r"[\s,]+", fixas or ""):
        add(t)
    baixo = (texto or "").lower()
    for chave, tag in perfil.get("hashtags_extra", {}).items():
        if chave in baixo:
            add(tag)
    for t in extras_ia or []:
        add(t)
    for t in perfil.get("hashtags_gerais", []):
        add(t)
    return tags[:limite]


def _capitalizar(titulo):
    t = (titulo or "").strip().rstrip(".")
    return t[:1].upper() + t[1:].lower() if t.isupper() else t


PLAT_NOME = {"twitch": "Twitch", "kick": "Kick", "youtube": "YouTube"}


def credito(origem):
    if not origem or not origem.get("usuario"):
        return ""
    plat = PLAT_NOME.get(origem.get("plataforma"), "")
    return f"🎥 Créditos: @{origem['usuario']}" + (f" ({plat})" if plat else "")


def gerar(titulo, texto, perfil_nome, fixas="", descricao_ia="", hashtags_ia=(), origem=None):
    perfil = perfis.obter(perfil_nome)
    partes = []
    if descricao_ia:
        partes.append(descricao_ia.strip())
    else:
        cab = _capitalizar(titulo) or "Olha esse momento da live"
        partes.append(f"{cab} 😱")
        frase = ""
        for s in re.split(r"(?<=[.!?])\s+", texto or ""):
            if 25 <= len(s) <= 140:
                frase = s.strip()
                break
        if frase:
            partes.append(f"“{frase}”")
    partes.append(credito(origem))
    partes.append(perfil.get("cta", ""))
    extra = ""
    if origem and origem.get("usuario") and re.fullmatch(r"[\w.]+", origem["usuario"]):
        extra = "#" + origem["usuario"].replace(".", "")
    tags = montar_hashtags(f"{titulo} {texto}", perfil_nome, fixas + " " + extra, hashtags_ia)
    return "\n\n".join(p for p in partes if p) + "\n\n" + " ".join(tags)
