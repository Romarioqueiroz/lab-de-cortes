import numpy as np

from .utils import ffmpeg_bin, rodar

SR = 16000


def extrair_pcm(video, destino):
    rodar([ffmpeg_bin(), "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(SR),
           "-f", "s16le", "-acodec", "pcm_s16le", destino])


def carregar(destino):
    return np.memmap(destino, dtype=np.int16, mode="r")


def energia_db(pcm, hop=0.5):
    """Volume (dB) a cada `hop` segundos, calculado em blocos para não estourar a memória."""
    bloco = int(SR * hop)
    n = len(pcm) // bloco
    saida = np.empty(n, np.float32)
    passo = 2000
    for i in range(0, n, passo):
        j = min(n, i + passo)
        x = np.asarray(pcm[i * bloco:j * bloco], dtype=np.float32).reshape(j - i, bloco) / 32768.0
        saida[i:j] = 10 * np.log10(np.mean(x * x, axis=1) + 1e-10)
    return saida


def trecho(pcm, ini, fim):
    a = max(0, int(ini * SR))
    b = min(len(pcm), int(fim * SR))
    return np.asarray(pcm[a:b], dtype=np.float32) / 32768.0


def trecho_de_video(video, ini, fim):
    """Extrai só um pedaço do áudio direto do vídeo (usado ao reeditar um corte)."""
    import subprocess
    from .utils import SEM_JANELA
    p = subprocess.run(
        [ffmpeg_bin(), "-v", "error", "-ss", f"{max(0.0, ini):.3f}", "-t", f"{max(0.1, fim - ini):.3f}",
         "-i", video, "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True, creationflags=SEM_JANELA,
    )
    return np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
