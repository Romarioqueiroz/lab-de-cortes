"""Análise de entonação: altura da voz (pitch), variação e "brilho" (voz gritada/empolgada).

Tudo em numpy, por blocos, para aguentar lives de várias horas sem estourar a memória.
"""
import numpy as np

SR = 16000
QUADRO = 640        # 40 ms
PASSO = 320         # 20 ms
LAG_MIN = SR // 450  # até ~450 Hz
LAG_MAX = SR // 70   # a partir de ~70 Hz
NFFT = 2048


def _analisar_trecho(x):
    """Retorna, por quadro de 20 ms: f0 (Hz ou nan), energia (dB), centroide espectral (Hz)."""
    if len(x) < QUADRO:
        return np.array([]), np.array([]), np.array([])
    quadros = np.lib.stride_tricks.sliding_window_view(x, QUADRO)[::PASSO]
    quadros = quadros - quadros.mean(axis=1, keepdims=True)
    janela = np.hanning(QUADRO).astype(np.float32)
    X = np.fft.rfft(quadros * janela, n=NFFT)
    P = (X.real ** 2 + X.imag ** 2).astype(np.float32)

    energia = 10 * np.log10(P.sum(axis=1) / NFFT + 1e-10)

    freqs = np.fft.rfftfreq(NFFT, 1 / SR).astype(np.float32)
    faixa = (freqs >= 80) & (freqs <= 6000)
    mag = np.sqrt(P[:, faixa])
    centroide = (mag * freqs[faixa]).sum(axis=1) / (mag.sum(axis=1) + 1e-9)

    ac = np.fft.irfft(P, n=NFFT)[:, :LAG_MAX + 2]
    ac = ac / (ac[:, :1] + 1e-9)
    trecho = ac[:, LAG_MIN:LAG_MAX + 1]
    # menor lag com pico >= 90% do máximo (evita erro de oitava para baixo)
    maximo = trecho.max(axis=1, keepdims=True)
    pico_local = np.zeros_like(trecho, dtype=bool)
    pico_local[:, 1:-1] = (trecho[:, 1:-1] >= trecho[:, :-2]) & (trecho[:, 1:-1] >= trecho[:, 2:])
    candidato = pico_local & (trecho >= 0.9 * maximo)
    idx = np.where(candidato.any(axis=1), candidato.argmax(axis=1), trecho.argmax(axis=1))
    forca = trecho[np.arange(len(idx)), idx]
    lag = (idx + LAG_MIN).astype(np.float32)
    # interpolação parabólica para refinar o lag
    i0 = np.clip(lag.astype(int), 1, LAG_MAX)
    a, b, c = ac[np.arange(len(i0)), i0 - 1], ac[np.arange(len(i0)), i0], ac[np.arange(len(i0)), i0 + 1]
    den = a - 2 * b + c
    ajuste = np.where(np.abs(den) > 1e-9, 0.5 * (a - c) / den, 0)
    f0 = SR / (lag + np.clip(ajuste, -1, 1))

    sonoro = (forca > 0.45) & (energia > np.percentile(energia, 95) - 35)
    f0 = np.where(sonoro, f0, np.nan)
    return f0, energia, centroide


def prosodia(pcm, hop=0.5, progresso=None):
    """Retorna dicionário com arrays (um valor a cada `hop` s): semitons, variacao, brilho, fala."""
    q_por_bloco = int(hop * SR / PASSO)
    n_blocos = len(pcm) // int(SR * hop)
    semitons = np.full(n_blocos, np.nan, np.float32)
    variacao = np.zeros(n_blocos, np.float32)
    brilho = np.zeros(n_blocos, np.float32)
    fala = np.zeros(n_blocos, np.float32)

    blocos_por_trecho = 120  # 60 s por vez
    amostras_trecho = int(blocos_por_trecho * hop * SR)
    for b0 in range(0, n_blocos, blocos_por_trecho):
        b1 = min(n_blocos, b0 + blocos_por_trecho)
        a0 = int(b0 * hop * SR)
        x = np.asarray(pcm[a0:a0 + amostras_trecho + QUADRO], dtype=np.float32) / 32768.0
        f0, _, cent = _analisar_trecho(x)
        st = 12 * np.log2(f0 / 100.0)  # semitons relativos a 100 Hz
        for k in range(b1 - b0):
            q0, q1 = k * q_por_bloco, (k + 1) * q_por_bloco
            s = st[q0:q1]
            s = s[~np.isnan(s)]
            if len(s):
                fala[b0 + k] = len(s) / max(1, q1 - q0)
                brilho[b0 + k] = float(np.mean(cent[q0:q1]))
            if len(s) >= 4:
                semitons[b0 + k] = float(np.median(s))
                variacao[b0 + k] = float(np.std(s))
        if progresso:
            progresso(b1 / max(1, n_blocos))
    return {"semitons": semitons, "variacao": variacao, "brilho": brilho, "fala": fala}
