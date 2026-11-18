# ✂ Lab de Cortes · Edição GTA 6 🌴

Cole o link de uma live (YouTube, Twitch, Kick ou qualquer site suportado pelo [yt-dlp](https://github.com/yt-dlp/yt-dlp)) e o Lab de Cortes:

1. **Baixa a live** (ou usa um arquivo de vídeo do seu PC)
2. **Encontra os melhores momentos** cruzando quatro sinais:
   - 💬 **chat**: momentos em que as mensagens por minuto disparam (reações como "KKKK", "CLIP", "????" e superchats pesam mais)
   - 🎙 **entonação da voz**: tom mais alto que o normal do streamer, mais variação, voz "gritada"
   - 🔊 **volume**: picos em relação ao último minuto
   - 🗣 **fala**: palavras e expressões de reação na transcrição
3. **Transcreve** cada momento com o Whisper (roda no seu PC, sem custo)
4. **Edita cada corte automaticamente**:
   - vertical **9:16** (TikTok, Reels, Shorts) com **fundo desfocado**
   - **zoom** leve e **ajuste de cor** (natural, vibrante, quente, frio, cinema)
   - **legendas animadas** palavra por palavra, com a palavra falada em destaque
   - **título/gancho** no topo
   - **marca d'água** com o seu @ e **barra de progresso**
   - áudio normalizado para redes sociais (-14 LUFS)
5. Mostra tudo numa página com player, nota de cada corte e o motivo da escolha
6. **Editor de corte**: ajuste início e fim (as legendas são refeitas), título, legendas e descrição
7. **Descrição com hashtags** pronta para cada corte (com IA opcional)
8. **Posta no TikTok e no Instagram (Reels)** pelas APIs oficiais, na hora ou automaticamente depois de cortar

### 📡 Radar de streamers (automático)
Na aba GTA 6, em **Streamers (automático)**, ligue o radar. Com **🔎 Descobrir streamers automaticamente**
ligado (padrão), o Lab procura sozinho quem está jogando GTA 6 — você não precisa digitar nenhum @:

| Plataforma | Como descobre |
|---|---|
| **Twitch** | diretório do jogo (quem está ao vivo, por audiência) + quem teve os clipes mais vistos da semana |
| **Kick** | lives em destaque na categoria GTA 6 |
| **YouTube** | busca de lives ao vivo ("GTA 6 ao vivo", dá para mudar) |

Filtra pelo idioma (Português por padrão) e por audiência mínima. Os descobertos aparecem com a etiqueta **AUTO**;
se remover um, ele não volta. Se quiser, ainda dá para adicionar um streamer específico pelo @.

Para cada streamer no radar, ele puxa:

| Plataforma | O que o radar puxa |
|---|---|
| **Twitch** | clipes mais vistos do período (24h, 7 dias ou 30 dias), só de GTA 6 (confere o jogo do clipe) — ou as lives completas |
| **Kick** | clipes mais vistos do período, só da categoria GTA 6 — ou as lives completas |
| **YouTube** | lives recentes com GTA 6 no título; os cortes priorizam os trechos **"mais repetidos"** pelos espectadores |
| **Outra** | qualquer canal/playlist suportado pelo yt-dlp (cole o link) |

Ligue o radar e ele verifica sozinho a cada X minutos (padrão 30), sem repetir clipe já feito.
Cada post leva os créditos do streamer (`🎥 Créditos: @streamer (Twitch)`) e a hashtag dele.
Os cortes usam a edição configurada em **Link manual** (cor, @, legendas, duração).

### 🏷 Trocar a marca d'água (até dos cortes já feitos)
- **Todos os cortes**: na barra "Marca d'água", digite o novo @ e clique em *Trocar em todos os cortes já feitos*.
  Os vídeos são refeitos com o novo @ e os próximos cortes (inclusive do radar) já saem com ele.
- **Só uma live**: botão **🏷 @** no card da live.
- **Só um corte**: campo *Marca d'água deste corte* no editor (✏ Editar).

Cortes já postados no TikTok/Instagram não mudam lá (as redes não deixam trocar o vídeo de um post).

### 🚀 Postar automático
O botão fica no topo da tela principal: ligue e marque TikTok e/ou Instagram. Vale para tudo
(radar e link manual). Desligado, os cortes esperam você revisar, editar e clicar em **📤 Postar**.

### Aba GTA 6
A aba principal é dedicada a lives de **GTA 6**: tema Vice City, pesos ajustados para gameplay (chat e voz contam mais que o barulho do jogo),
palavras-gatilho do jogo (polícia, estrelas, Lucia, Jason, Leonida, bug, glitch...), cor "vice", hashtags #GTA6 #GTAVI
e hashtags automáticas pelo assunto do corte. A aba **Lab geral** continua servindo para qualquer outra live.

Tudo roda **no seu computador**. Nada é enviado para servidores, exceto se você ativar a IA opcional.

---

## Instalação

### Windows

1. Instale o **Python 3.10+** em <https://www.python.org/downloads/> (marque **"Add python.exe to PATH"**).
2. Baixe este repositório (botão verde **Code → Download ZIP**) e extraia, ou `git clone`.
3. Dê dois cliques em **`iniciar.bat`**.
   - Se o FFmpeg não estiver instalado, o script instala pelo `winget`. Depois, feche e abra o `iniciar.bat` de novo.
   - Na primeira vez ele instala as dependências (alguns minutos).
4. O navegador abre sozinho em **http://127.0.0.1:5000**.

### macOS / Linux

```bash
# precisa de Python 3.10+ e FFmpeg (brew install ffmpeg / sudo apt install ffmpeg)
./iniciar.sh
```

---

## Como usar

1. Cole o link da live (ou o caminho de um arquivo, ex.: `C:\lives\minha_live.mp4`).
2. Escolha quantos cortes, a duração e o seu @.
3. Clique em **Gerar cortes** e acompanhe o progresso.
4. Assista aos cortes, ajuste o título se quiser e clique em **Aplicar título** para reeditar.
5. Clique em **Baixar** ou em **📁 Abrir pasta**. Os arquivos ficam em `trabalhos/<data>/clipes/`.

### Escolha dos momentos

Em **"O que conta para achar um bom momento"** você ajusta o peso de cada sinal (0 desliga).
O corte é montado com o **pico de reação a ~65% do vídeo**: dá tempo de mostrar o contexto antes da reação.
Cada corte mostra o motivo da escolha (ex.: `💬 160/min (5x)`, `🎙 muito alto`). Depois de pronto, um gráfico mostra a live inteira com os sinais e onde caiu cada corte.

- **Chat**: baixado automaticamente para YouTube (replay do chat) e Twitch (VODs). Para arquivo local, coloque ao lado do vídeo um `<mesmo nome>.live_chat.json` (formato do yt-dlp).
- **Atraso do chat**: o chat reage alguns segundos depois do momento (atraso da transmissão + tempo de digitar). O padrão é 6 s; aumente se a live tinha muito atraso.
- **Live de jogo com muito som**: baixe o peso do volume e suba o da voz e do chat.

### Dicas

- **Momentos que eu já sei**: se você lembra de um momento bom, coloque o horário (`1:23:45-1:24:30` ou só `1:23:45`). Ele entra junto com os automáticos.
- **Trecho da live**: em lives muito longas, baixe só uma parte (ex.: `1:00:00` até `3:00:00`) para economizar tempo e espaço.
- **Modelo de transcrição**: `small` é o equilíbrio. Sem placa de vídeo NVIDIA, use `base` ou `tiny` se estiver lento. Com GPU NVIDIA (CUDA), `medium` ou `large-v3` ficam bem melhores.
- **Enquadramento "Aproximado"** corta as laterais e deixa o vídeo maior na tela. É bom para lives de conversa (câmera no centro).
- **YouTube pedindo login** ("confirme que você não é um robô") ou live só para membros: em *Avançado → Cookies do navegador*, escolha o navegador onde você está logado.
- **Lives em andamento**: o ideal é usar o VOD depois que a live termina. Se a live ainda estiver no ar, o download só termina quando ela acabar.

### IA opcional (melhores escolhas e títulos)

Sem IA, o lab escolhe pelos picos de áudio e por palavras-chave da fala, e o título é a frase mais forte do trecho.
Com uma chave da API da Anthropic (<https://console.anthropic.com>), o Claude lê a transcrição dos candidatos, dá uma nota de potencial viral e escreve um título-gancho para cada um.
Coloque a chave em *Avançado* (fica salva só no seu navegador) ou na variável de ambiente `ANTHROPIC_API_KEY`. O custo é de poucos centavos por live.

---

## Como funciona

| Etapa | Arquivo | O que faz |
|---|---|---|
| Download | `lab/download.py` | yt-dlp, até 1080p, opcionalmente só um trecho |
| Áudio | `lab/audio.py` | extrai o áudio em 16 kHz e mede o volume a cada 0,5 s |
| Voz | `lab/voz.py` | altura (pitch), variação e brilho da voz a cada 0,5 s |
| Chat | `lab/chat.py` | replay do chat (YouTube via yt-dlp, Twitch via API do site) e mensagens por minuto com peso para reações |
| Destaques | `lab/highlights.py` | compara cada sinal com o normal da live, combina com os pesos escolhidos, acha os picos e ajusta início/fim nas pausas da fala |
| Transcrição | `lab/transcribe.py` | faster-whisper com tempo por palavra (só nos candidatos, para ser rápido) |
| IA | `lab/ai.py` | nota + título com o Claude (opcional) |
| Edição | `lab/render.py`, `lab/subtitles.py` | FFmpeg: 9:16, fundo desfocado, zoom, cor, legendas .ass, título, marca d'água, barra, loudnorm |
| Perfis | `lab/perfis.py` | GTA 6 e geral: pesos, gatilhos, hashtags, contexto da IA |
| Descrição | `lab/descricao.py` | legenda do post + hashtags |
| Contas | `lab/contas.py` | login TikTok (OAuth) e token do Instagram |
| Publicação | `lab/publicar.py` | envio em partes ao TikTok, Reels retomável no Instagram, fila e status |
| Interface | `app.py`, `templates/`, `static/` | servidor Flask local + página web |
| Retorno do login | `docs/callback.html` | página do GitHub Pages que repassa o login do TikTok para o seu PC |

Para mudar o visual das legendas (fonte, tamanho, posição), edite `lab/subtitles.py`. Para criar presets de cor, edite `PRESETS_COR` em `lab/render.py`.

## Postar no TikTok e no Instagram

Os tokens das contas ficam **só no seu PC**, na pasta `dados/` (que o `.gitignore` impede de subir para o GitHub).
O passo a passo completo está na aba **Contas** do app. Resumo:

### TikTok
1. Ative o **GitHub Pages** deste repositório: *Settings → Pages → Branch `main` / pasta `/docs`*.
   A página `docs/callback.html` recebe o login do TikTok e repassa para o programa no seu PC.
   Sua Redirect URI fica: `https://SEU-USUARIO.github.io/NOME-DO-REPO/callback.html`
2. Em <https://developers.tiktok.com>, crie um app com **Login Kit** e **Content Posting API**,
   escopos `user.info.basic`, `video.upload`, `video.publish`, e cadastre a Redirect URI acima.
3. Na aba **Contas**, cole o Client Key/Secret e a Redirect URI, e clique em **Conectar TikTok**.

Modos de envio:
- **Rascunho**: o vídeo chega no seu TikTok (notificações/rascunhos) e você toca em publicar. Funciona desde o começo.
- **Postar direto**: publica sozinho. ⚠ Enquanto o app não for aprovado na revisão do TikTok, posts diretos ficam **privados** (regra do TikTok).

### Instagram (Reels)
1. Conta **Profissional** (Criador ou Empresa) ligada a uma **Página do Facebook**.
2. Em <https://developers.facebook.com>, crie um app (tipo Empresa) com o produto **Instagram** (Login do Facebook para Empresas).
3. No **Graph API Explorer**, gere um token com `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `pages_read_engagement`, `business_management`.
4. Na aba **Contas**, cole App ID, App Secret e o token. O Lab troca por um token de **60 dias** (depois, gere outro).

## Direitos autorais

As edições deixam o corte com cara de conteúdo próprio e ajudam a não ser marcado como repost pelas plataformas, mas **não impedem reivindicações de direitos autorais** (o Content ID do YouTube, por exemplo, reconhece o áudio). Use com as suas próprias lives ou com streamers que autorizam canais de cortes, e mantenha os créditos que o Lab coloca na descrição.

## Requisitos

- Python 3.10+
- FFmpeg (com libass, que já vem nas builds comuns)
- Deno (o `iniciar.bat` instala; o yt-dlp usa para baixar do YouTube)
- ~2 GB livres por hora de live em 1080p
