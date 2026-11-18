"""Gera o arquivo .ass com título, legendas palavra-a-palavra e marca d'água."""
import re

W, H = 1080, 1920


def cor_ass(hexa, alfa=0):
    h = (hexa or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alfa:02X}{b}{g}{r}".upper()


def _t(s):
    s = max(0.0, s)
    cs = int(round(s * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _limpar(txt):
    txt = txt.replace("\\", "").replace("{", "(").replace("}", ")")
    return re.sub(r"\s+", " ", txt).strip()


def _blocos(palavras, max_palavras=3, max_chars=18):
    blocos, atual = [], []
    for p in palavras:
        texto = _limpar(p["w"]).rstrip(",.;:").upper()
        if not texto:
            continue
        p = {**p, "w": texto}
        if atual:
            gap = p["i"] - atual[-1]["f"]
            chars = sum(len(x["w"]) + 1 for x in atual) + len(texto)
            fim_frase = atual[-1]["w"][-1:] in "!?"
            if len(atual) >= max_palavras or chars > max_chars or gap > 0.6 or fim_frase:
                blocos.append(atual)
                atual = []
        atual.append(p)
    if atual:
        blocos.append(atual)
    return blocos


def gerar_ass(caminho, palavras, dur, layout, titulo="", marca="", cor="#FFD400",
              legendas=True, mostrar_titulo=True):
    destaque = cor_ass(cor)
    topo, base = layout["top"], layout["bottom"]
    if layout["fh"] > 1500:  # vídeo já vertical: textos sobre o vídeo
        pos_titulo, alin_titulo = 170, 8
        pos_leg = 1300
    else:
        pos_titulo, alin_titulo = topo - 45, 2
        pos_leg = base + 70

    linhas = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Legenda,Arial Black,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        "-1,0,0,0,100,100,0,0,1,7,3,8,60,60,0,1",
        f"Style: Titulo,Arial Black,64,&H00111111,&H00111111,{destaque},{destaque},"
        "-1,0,0,0,100,100,0,0,3,18,0,2,90,90,0,1",
        "Style: Marca,Arial Black,58,&H30FFFFFF,&H30FFFFFF,&H70000000,&H00000000,"
        "-1,0,0,0,100,100,1,0,1,3,1,2,40,40,0,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    if mostrar_titulo and titulo.strip():
        linhas.append(
            f"Dialogue: 2,{_t(0)},{_t(dur)},Titulo,,0,0,0,,"
            f"{{\\an{alin_titulo}\\pos(540,{pos_titulo})}}{_limpar(titulo)}"
        )

    if marca.strip():
        linhas.append(f"Dialogue: 1,{_t(0)},{_t(dur)},Marca,,0,0,0,,{{\\an2\\pos(540,{H - 210})}}{_limpar(marca)}")

    if legendas:
        blocos = _blocos([p for p in palavras if p["f"] > 0 and p["i"] < dur])
        for bi, bloco in enumerate(blocos):
            prox = blocos[bi + 1][0]["i"] if bi + 1 < len(blocos) else dur
            fim_bloco = min(prox, bloco[-1]["f"] + 0.35, dur)
            for wi, p in enumerate(bloco):
                ini = max(0.0, p["i"])
                fim = bloco[wi + 1]["i"] if wi + 1 < len(bloco) else fim_bloco
                if fim - ini < 0.05:
                    fim = ini + 0.05
                partes = []
                for k, q in enumerate(bloco):
                    partes.append(f"{{\\c{destaque}}}{q['w']}{{\\c&H00FFFFFF&}}" if k == wi else q["w"])
                efeito = "\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)" if wi == 0 else ""
                linhas.append(
                    f"Dialogue: 3,{_t(ini)},{_t(fim)},Legenda,,0,0,0,,"
                    f"{{\\an8\\pos(540,{pos_leg}){efeito}}}" + " ".join(partes)
                )

    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
