"""Transcrição com faster-whisper (com marcação de tempo por palavra)."""


class Transcritor:
    def __init__(self, nome, log):
        self.nome = nome
        self.log = log
        self.modelo = None
        self.cpu = False

    def _carregar(self, forcar_cpu=False):
        from faster_whisper import WhisperModel
        if not forcar_cpu:
            try:
                self.modelo = WhisperModel(self.nome, device="auto", compute_type="auto")
                return
            except Exception as e:  # sem GPU/CUDA
                self.log(f"GPU indisponível ({str(e)[:80]}), usando CPU.")
        self.modelo = WhisperModel(self.nome, device="cpu", compute_type="int8")
        self.cpu = True

    def transcrever(self, audio, deslocamento, idioma="pt"):
        if self.modelo is None:
            self.log(f"Carregando modelo de transcrição '{self.nome}' (na 1ª vez ele é baixado)...")
            self._carregar()
        try:
            return self._rodar(audio, deslocamento, idioma)
        except RuntimeError as e:
            msg = str(e).lower()
            if not self.cpu and any(k in msg for k in ("cuda", "cublas", "cudnn")):
                self.log("Falha na GPU, refazendo na CPU.")
                self._carregar(forcar_cpu=True)
                return self._rodar(audio, deslocamento, idioma)
            raise

    def _rodar(self, audio, deslocamento, idioma):
        segs, _ = self.modelo.transcribe(
            audio, language=idioma or None, word_timestamps=True, vad_filter=True,
            beam_size=3, condition_on_previous_text=False,
        )
        saida = []
        for s in segs:
            palavras = [
                {"w": w.word.strip(), "i": round(w.start + deslocamento, 2), "f": round(w.end + deslocamento, 2)}
                for w in (s.words or []) if w.word.strip()
            ]
            saida.append({
                "i": round(s.start + deslocamento, 2), "f": round(s.end + deslocamento, 2),
                "texto": s.text.strip(), "palavras": palavras,
            })
        return saida
