import json
import os
import re
import shutil
import subprocess
import threading
import time

SEM_JANELA = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def ffmpeg_bin():
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_bin():
    return shutil.which("ffprobe") or "ffprobe"


def rodar(cmd, cwd=None):
    p = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", creationflags=SEM_JANELA,
    )
    if p.returncode != 0:
        raise RuntimeError(f"Falha ao executar {os.path.basename(cmd[0])}:\n{p.stderr[-2500:]}")
    return p


def info_video(caminho):
    p = rodar([
        ffprobe_bin(), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration", "-of", "json", caminho,
    ])
    d = json.loads(p.stdout)
    st = (d.get("streams") or [{}])[0]
    return {
        "w": int(st.get("width") or 1920),
        "h": int(st.get("height") or 1080),
        "dur": float(d.get("format", {}).get("duration") or 0),
    }


def tempo_para_seg(txt):
    """Aceita '1:23:45', '83:12', '4512', '1h23m45s'. Retorna segundos ou None."""
    if txt is None:
        return None
    t = str(txt).strip().lower()
    if not t:
        return None
    m = re.fullmatch(r"(?:(\d+)h)?\s*(?:(\d+)m(?:in)?)?\s*(?:(\d+(?:[.,]\d+)?)s)?", t)
    if m and any(m.groups()):
        h, mi, s = m.groups()
        return int(h or 0) * 3600 + int(mi or 0) * 60 + float((s or "0").replace(",", "."))
    partes = t.replace(",", ".").split(":")
    try:
        valores = [float(p) for p in partes]
    except ValueError:
        return None
    seg = 0.0
    for v in valores:
        seg = seg * 60 + v
    return seg


def seg_para_tempo(s):
    s = max(0, int(round(s)))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


_TRAVA_JSON = threading.Lock()


def salvar_json(caminho, dados):
    with _TRAVA_JSON:
        tmp = f"{caminho}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=1)
        for tentativa in range(5):  # no Windows o arquivo pode estar aberto por um instante
            try:
                os.replace(tmp, caminho)
                return
            except PermissionError:
                time.sleep(0.1)
