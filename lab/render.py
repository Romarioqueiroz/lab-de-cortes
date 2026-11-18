"""Monta o vídeo vertical 9:16 com fundo desfocado, zoom, cor, legendas, título e barra."""
import os

from .subtitles import gerar_ass
from .utils import ffmpeg_bin, rodar

PRESETS_COR = {
    "nenhum": "null",
    "natural": "eq=contrast=1.05:saturation=1.12",
    "vibrante": "eq=contrast=1.10:saturation=1.35:brightness=0.02",
    "quente": "eq=contrast=1.06:saturation=1.15,colorbalance=rs=0.06:gs=0.02:bs=-0.06",
    "frio": "eq=contrast=1.06:saturation=1.05,colorbalance=rs=-0.05:bs=0.07",
    "vice": "eq=contrast=1.12:saturation=1.4:brightness=0.01,colorbalance=rs=-0.03:bs=0.07:rh=0.07:bh=0.04",
    "cinema": "eq=contrast=1.15:saturation=0.9:gamma=0.95,colorbalance=rs=0.04:bs=-0.03:rh=-0.03:bh=0.05",
}


def calcular_layout(w, h, zoom=1.08, enquadramento="completo"):
    zoom = max(1.0, min(float(zoom or 1.0), 2.0))
    cw, ch = w / zoom, h / zoom
    if enquadramento == "aproximado" and cw / ch > 4 / 3:
        cw = ch * 4 / 3
    cw, ch = int(cw) // 2 * 2, int(ch) // 2 * 2
    ar = cw / ch
    fw, fh = 1080, int(round(1080 / ar / 2)) * 2
    if fh > 1920:
        fh = 1920
        fw = int(round(1920 * ar / 2)) * 2
    top = (1920 - fh) // 2
    return {"cw": cw, "ch": ch, "fw": fw, "fh": fh, "top": top, "bottom": top + fh}


def renderizar(video, ini, dur, pasta, nome_saida, info, cfg, palavras_rel, titulo):
    os.makedirs(pasta, exist_ok=True)
    nome_ass = os.path.splitext(nome_saida)[0] + ".ass"
    lay = calcular_layout(info["w"], info["h"], cfg.get("zoom", 1.08), cfg.get("enquadramento", "completo"))
    gerar_ass(
        os.path.join(pasta, nome_ass), palavras_rel, dur, lay,
        titulo=titulo, marca=cfg.get("marca", ""), cor=cfg.get("cor", "#FFD400"),
        legendas=cfg.get("legendas", True), mostrar_titulo=cfg.get("titulo", True),
    )
    cor = PRESETS_COR.get(cfg.get("preset", "vibrante"), "null")
    fundo = ("scale=270:480:force_original_aspect_ratio=increase,crop=270:480,"
             "boxblur=12:3,scale=1080:1920,setsar=1,eq=brightness=-0.12:saturation=1.2")
    frente = f"crop={lay['cw']}:{lay['ch']},scale={lay['fw']}:{lay['fh']},setsar=1,{cor}"
    fc = (f"[0:v]split=2[a][b];[a]{fundo}[bg];[b]{frente}[fg];"
          f"[bg][fg]overlay=(W-w)/2:{lay['top']}[v1];[v1]ass={nome_ass}[v2]")
    if cfg.get("barra", True):
        hexa = (cfg.get("cor") or "#FFD400").lstrip("#")
        fc += (f";color=c=0x{hexa}:s=1080x14:r=30[bar];"
               f"[v2][bar]overlay=x='-w+w*t/{dur:.3f}':y=H-14:shortest=1[v]")
    else:
        fc += ";[v2]null[v]"

    cmd = [
        ffmpeg_bin(), "-y", "-v", "error", "-ss", f"{ini:.3f}", "-t", f"{dur:.3f}",
        "-i", os.path.abspath(video), "-filter_complex", fc,
        "-map", "[v]", "-map", "0:a?", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", nome_saida,
    ]
    rodar(cmd, cwd=pasta)
    return os.path.join(pasta, nome_saida)
