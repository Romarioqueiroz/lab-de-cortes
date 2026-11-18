import glob
import os

from .utils import tempo_para_seg


def eh_arquivo_local(fonte):
    return os.path.isfile(fonte.strip().strip('"'))


def baixar(fonte, pasta, log, progresso, cookies_navegador="", trecho_ini=None, trecho_fim=None):
    """Baixa a live (YouTube, Twitch, Kick e outros sites do yt-dlp) ou usa um arquivo local.

    Retorna (caminho_do_video, titulo, deslocamento_em_segundos).
    """
    fonte = fonte.strip().strip('"')
    if eh_arquivo_local(fonte):
        log(f"Usando arquivo local: {fonte}")
        return os.path.abspath(fonte), os.path.splitext(os.path.basename(fonte))[0], 0.0

    import yt_dlp

    def gancho(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                progresso(d.get("downloaded_bytes", 0) / total)
            elif d.get("fragment_count"):
                progresso((d.get("fragment_index") or 0) / d["fragment_count"])

    opcoes = {
        "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(pasta, "live.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [gancho],
        "concurrent_fragment_downloads": 4,
        "retries": 10,
        "fragment_retries": 10,
    }
    if cookies_navegador:
        opcoes["cookiesfrombrowser"] = (cookies_navegador,)

    deslocamento = 0.0
    ini, fim = tempo_para_seg(trecho_ini), tempo_para_seg(trecho_fim)
    if ini is not None or fim is not None:
        ini = ini or 0.0
        opcoes["download_ranges"] = yt_dlp.utils.download_range_func(None, [(ini, fim or float("inf"))])
        deslocamento = ini
        log("Baixando só o trecho escolhido da live.")

    log("Baixando a live (isso pode demorar em lives longas)...")
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(fonte, download=True)
    titulo = (info or {}).get("title") or "live"
    if (info or {}).get("heatmap"):
        import json
        with open(os.path.join(pasta, "heatmap.json"), "w", encoding="utf-8") as f:
            json.dump(info["heatmap"], f)

    arquivos = [a for a in glob.glob(os.path.join(pasta, "live.*")) if not a.endswith((".part", ".ytdl"))]
    if not arquivos:
        raise RuntimeError("O download terminou mas o arquivo de vídeo não foi encontrado.")
    arquivos.sort(key=os.path.getsize, reverse=True)
    return arquivos[0], titulo, deslocamento
