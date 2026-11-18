"""Avaliação opcional dos cortes com a API do Claude (precisa de chave da Anthropic)."""
import json
import urllib.request

PROMPT = """Você é editor de cortes virais para TikTok, Reels e Shorts. Contexto: {contexto}
Abaixo estão trechos candidatos de uma live (transcrição automática, pode ter erros).
Para cada trecho:
- "nota": 0 a 10 para o potencial de viralizar como corte isolado (humor, reação forte, polêmica,
  história com começo e fim, descoberta, frase marcante);
- "titulo": gancho curto em português (máx. 7 palavras, sem emojis, sem aspas), que dê vontade
  de assistir sem entregar o final;
- "descricao": legenda do post em português, 1 ou 2 frases curtas, tom de criador de conteúdo,
  pode ter 1 ou 2 emojis, termine com uma pergunta para gerar comentários. Sem hashtags aqui;
- "hashtags": lista com 3 a 5 hashtags específicas do trecho (sem repetir as genéricas).

Responda SOMENTE com JSON no formato:
[{{"id": 1, "nota": 7.5, "titulo": "...", "descricao": "...", "hashtags": ["#..."]}}]

TRECHOS:
"""


def avaliar(candidatos, chave, modelo, log, contexto="lives em geral"):
    blocos = []
    for c in candidatos:
        texto = " ".join(s["texto"] for s in c.get("segs", []))[:1500] or "(sem fala detectada)"
        blocos.append(f"[id {c['id']}] ({c['f'] - c['i']:.0f}s): {texto}")
    corpo = {
        "model": modelo,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": PROMPT.format(contexto=contexto) + "\n\n".join(blocos)}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read().decode("utf-8"))
        texto = "".join(b.get("text", "") for b in resp.get("content", []))
        dados = json.loads(texto[texto.index("["): texto.rindex("]") + 1])
        saida = {}
        for d in dados:
            saida[int(d["id"])] = {
                "nota": float(d.get("nota", 0)),
                "titulo": str(d.get("titulo", "")).strip(),
                "descricao": str(d.get("descricao", "")).strip(),
                "hashtags": [str(h) for h in (d.get("hashtags") or [])][:6],
            }
        return saida
    except Exception as e:
        log(f"Avaliação com IA falhou ({str(e)[:120]}). Seguindo com a análise automática.")
        return {}
