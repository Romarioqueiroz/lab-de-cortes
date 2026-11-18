// =====================================================================  Lab de Cortes — front-end
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const form = $("#form");
const listaJobs = $("#jobs");
const cards = {};            // id do job -> elemento
const abertos = new Set();   // jobs com log aberto
const detalhes = {};         // id -> job completo (último recebido)
let perfil = "gta6";
let contas = null;
let pubsAtivas = 0;

const PRIV = {
  PUBLIC_TO_EVERYONE: "Todo mundo", FOLLOWER_OF_CREATOR: "Seguidores",
  MUTUAL_FOLLOW_FRIENDS: "Amigos", SELF_ONLY: "Só eu",
};

async function api(url, corpo, metodo) {
  const op = corpo === undefined ? { method: metodo || "GET" }
    : { method: metodo || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) };
  const r = await fetch(url, op);
  let d = {};
  try { d = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error(d.erro || `Erro ${r.status}`);
  return d;
}

function hms(s, dec = false) {
  s = Math.max(0, s || 0);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  const seg = dec ? x.toFixed(1).padStart(4, "0") : String(Math.floor(x)).padStart(2, "0");
  return `${h}:${String(m).padStart(2, "0")}:${seg}`;
}
function fmtDur(s) {
  s = Math.round(s || 0);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return (h ? h + "h" : "") + String(m).padStart(h ? 2 : 1, "0") + "m" + String(x).padStart(2, "0") + "s";
}
function guardar(chave, valor) { try { localStorage.setItem(chave, JSON.stringify(valor)); } catch (e) {} }
function ler(chave) { try { return JSON.parse(localStorage.getItem(chave) || "null"); } catch (e) { return null; } }

// =====================================================================  abas
function irPara(aba) {
  $$(".abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === aba));
  const lab = aba === "gta6" || aba === "geral";
  $("#aba-lab").hidden = !lab;
  $("#aba-contas").hidden = aba !== "contas";
  $("#aba-pubs").hidden = aba !== "pubs";
  $("#hero-gta6").hidden = aba !== "gta6";
  document.body.className = aba === "geral" || aba === "contas" || aba === "pubs" ? "tema-geral" : "tema-gta6";
  if (aba === "contas" || aba === "pubs") document.body.className = perfil === "gta6" ? "tema-gta6" : "tema-geral";
  if (lab && aba !== perfil) { salvarForm(); perfil = aba; carregarForm(); atualizar(); }
  if (aba === "contas") carregarContas();
  if (aba === "pubs") carregarPubs();
  guardar("labdecortes.aba", aba);
}
$$(".abas button").forEach((b) => (b.onclick = () => irPara(b.dataset.aba)));

// =====================================================================  contagem GTA 6
function contagem() {
  const alvo = new Date(2026, 10, 19, 0, 0, 0); // 19/11/2026, horário local
  const falta = alvo - new Date();
  const el = $("#contagem");
  if (falta <= 0) { el.innerHTML = "🔥 <b>GTA 6 já está disponível</b> — hora de cortar as lives!"; return; }
  const d = Math.floor(falta / 864e5), h = Math.floor((falta % 864e5) / 36e5), m = Math.floor((falta % 36e5) / 6e4);
  el.innerHTML = `⏳ Lançamento 19/11/2026 · faltam <b>${d ? d + "d " : ""}${h}h ${String(m).padStart(2, "0")}m</b>`;
}

// =====================================================================  formulário
function padroesPerfil() {
  return { ...window.PADRAO, ...(window.PERFIS[perfil]?.padrao || {}) };
}

function carregarForm() {
  const salvo = ler("labdecortes.cfg." + perfil) || {};
  const ia = ler("labdecortes.ia") || {};
  const cfg = { ...padroesPerfil(), ...salvo, ...ia, url: "", manuais: "", trecho_ini: "", trecho_fim: "" };
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "radio") el.checked = cfg[el.name] === el.value;
    else if (el.name === "postar_tiktok") el.checked = (cfg.postar_em || []).includes("tiktok");
    else if (el.name === "postar_instagram") el.checked = (cfg.postar_em || []).includes("instagram");
    else if (!(el.name in cfg)) continue;
    else if (el.type === "checkbox") el.checked = !!cfg[el.name];
    else el.value = cfg[el.name];
  }
  $("#form-titulo").textContent = perfil === "gta6" ? "Nova live de GTA 6" : "Nova live";
  const chips = $("#gatilhos-chips");
  chips.innerHTML = "";
  const gat = window.PERFIS[perfil]?.gatilhos || [];
  $("#gatilhos-box").hidden = !gat.length;
  gat.slice(0, 40).forEach((g) => { const s = document.createElement("span"); s.textContent = g; chips.appendChild(s); });
  atualizarZoom(); atualizarPesos(); atualizarDepois();
  const mg = $("#marca-global"); if (mg && document.activeElement !== mg) mg.value = form.marca.value;
}

function lerForm() {
  const cfg = { perfil, postar_em: [] };
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "radio") { if (el.checked) cfg[el.name] = el.value; }
    else if (el.name === "postar_tiktok") { if (el.checked) cfg.postar_em.push("tiktok"); }
    else if (el.name === "postar_instagram") { if (el.checked) cfg.postar_em.push("instagram"); }
    else if (el.type === "checkbox") cfg[el.name] = el.checked;
    else if (el.type === "number" || el.type === "range") cfg[el.name] = Number(el.value);
    else cfg[el.name] = el.value.trim();
  }
  return cfg;
}

function salvarForm() {
  const { url, manuais, trecho_ini, trecho_fim, ia_chave, ia_modelo, ...resto } = lerForm();
  guardar("labdecortes.cfg." + perfil, resto);
  guardar("labdecortes.ia", { ia_chave, ia_modelo });
}

function atualizarZoom() { $("#zoomv").textContent = Math.round((form.zoom.value - 1) * 100) + "%"; }
function atualizarPesos() {
  for (const lab of $$(".pesos label")) {
    const v = Number($("input", lab).value);
    $("output", lab).textContent = v === 0 ? "desligado" : String(v).replace(".", ",") + "x";
  }
}
function atualizarDepois() { pintarAuto(); }
form.zoom.addEventListener("input", atualizarZoom);
$$(".pesos input").forEach((el) => el.addEventListener("input", atualizarPesos));
form.addEventListener("change", () => { salvarForm(); enviarCfgBase(); });

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  salvarForm();
  const cfg = lerForm();
  const msg = $("#msg");
  msg.className = "msg";
  msg.textContent = "Enviando...";
  try {
    await api("/api/jobs", cfg);
    msg.textContent = "Na fila! Acompanhe o progresso ao lado.";
    form.url.value = "";
    atualizar();
  } catch (e) { msg.className = "msg erro"; msg.textContent = e.message; }
});

// =====================================================================  trabalhos e cortes
function criarCard(job) {
  const el = $("#tpl-job").content.firstElementChild.cloneNode(true);
  el.dataset.id = job.id;
  $(".abrir", el).onclick = () => api(`/api/jobs/${job.id}/abrir-pasta`, {});
  $(".trocar-marca", el).onclick = async () => {
    const atual = detalhes[job.id]?.cfg_render?.marca ?? form.marca.value;
    const nova = prompt("Novo @ da marca d'água para os cortes desta live:", atual || "");
    if (nova === null) return;
    try { const r = await trocarMarca(nova, job.id); if (r.sem_fonte) alertaLeve(`${r.sem_fonte} cortes não têm mais o vídeo original.`); }
    catch (e) { alertaLeve(e.message); }
  };
  $(".log-btn", el).onclick = () => {
    const pre = $(".log", el);
    pre.hidden = !pre.hidden;
    pre.hidden ? abertos.delete(job.id) : abertos.add(job.id);
    atualizar();
  };
  el._clipes = {};
  return el;
}

function criarClipe(job, c) {
  const el = $("#tpl-clipe").content.firstElementChild.cloneNode(true);
  $(".editar", el).onclick = () => abrirEditor(detalhes[job.id], c.n);
  $(".postar", el).onclick = () => abrirPostar(detalhes[job.id], c.n);
  return el;
}

const PLAT = { twitch: "Twitch", kick: "Kick", youtube: "YouTube", outra: "Outra" };
const numero = (n) => (n >= 1e6 ? (n / 1e6).toFixed(1).replace(".", ",") + " mi" : n >= 1e3 ? (n / 1e3).toFixed(1).replace(".", ",") + " mil" : String(n));
const NIVEL = (v) => (v >= 2 ? "muito alto" : v >= 1 ? "alto" : v >= 0.3 ? "acima do normal" : "normal");
const ST_POST = { "na fila": "⏳ na fila", enviando: "⬆ enviando", processando: "⚙ processando", publicado: "✅ publicado", rascunho: "📥 nos rascunhos", erro: "⚠ erro" };

function atualizarClipe(el, job, c) {
  const src = `/arquivos/${job.id}/${c.arquivo}?v=${c.versao || 1}`;
  const video = $("video", el);
  const pronto = c.status === "pronto";
  el.classList.toggle("ocupado", !pronto);
  if (pronto && video.dataset.src !== src) { video.src = src; video.dataset.src = src; }
  $(".clipe-num", el).textContent = c.n;
  const a = $(".baixar", el);
  a.href = src;
  a.setAttribute("download", `${(c.titulo || "corte").slice(0, 40).replace(/[^\w\- ]+/g, "")} ${c.n}.mp4`.trim());
  $(".nota", el).textContent = c.manual ? "manual" : `nota ${c.nota}`;
  $(".na-live", el).textContent = `${c.na_live} · ${c.duracao}s`;
  $(".clipe-titulo", el).textContent = c.titulo || "(sem título)";
  $(".editar", el).disabled = !pronto;
  $(".postar", el).disabled = !pronto;

  const m = c.motivos;
  const caixaM = $(".motivos", el);
  const chave = JSON.stringify(m || {});
  if (caixaM.dataset.k !== chave) {
    caixaM.dataset.k = chave;
    caixaM.innerHTML = "";
    const chip = (txt, forte, dica) => {
      const s = document.createElement("span");
      s.textContent = txt; s.title = dica; if (forte) s.className = "forte";
      caixaM.appendChild(s);
    };
    if (m) {
      if (m.views) chip(`👁 ${numero(m.views)} views`, m.views >= 1000, "Visualizações do clipe original");
      if (m.replay != null) chip("🔁 " + NIVEL(m.replay), m.replay >= 1, "Trecho mais repetido pelos espectadores (YouTube)");
      if (m.volume != null) chip("🔊 " + NIVEL(m.volume), m.volume >= 1, "Volume em relação ao resto da live");
      if (m.voz != null) chip("🎙 " + NIVEL(m.voz), m.voz >= 1, "Entonação da voz");
      if (m.chat) chip(`💬 ${m.chat.por_min}/min` + (m.chat.vezes ? ` (${m.chat.vezes}x)` : ""), (m.chat.vezes || 0) >= 2, "Mensagens por minuto no chat perto do pico");
    }
  }
  const caixaP = $(".posts", el);
  const chaveP = JSON.stringify(c.posts || {});
  if (caixaP.dataset.k !== chaveP) {
    caixaP.dataset.k = chaveP;
    caixaP.innerHTML = "";
    for (const [rede, p] of Object.entries(c.posts || {})) {
      const s = document.createElement(p.link ? "a" : "span");
      const nome = rede === "tiktok" ? "TikTok" : "Instagram";
      s.textContent = `${nome}: ${ST_POST[p.status] || p.status}`;
      s.title = p.msg || "";
      if (p.link) { s.href = p.link; s.target = "_blank"; const w = document.createElement("span"); w.className = p.status; w.appendChild(s); caixaP.appendChild(w); }
      else { s.className = p.status; caixaP.appendChild(s); }
    }
  }
}

function atualizarCard(el, job) {
  $(".job-titulo", el).textContent = job.fonte?.titulo || job.cfg?.url || job.id;
  const partes = [new Date(job.criado * 1000).toLocaleString("pt-BR")];
  if (job.fonte?.duracao) partes.push(fmtDur(job.fonte.duracao));
  if (job.fonte?.resolucao) partes.push(job.fonte.resolucao);
  if (job.origem?.usuario) {
    const o = job.origem;
    partes.unshift(`📡 @${o.usuario} · ${PLAT[o.plataforma] || o.plataforma}` + (o.views ? ` · ${numero(o.views)} views` : "") + (o.tipo === "clipes" ? " · clipe" : " · live"));
  }
  $(".job-meta", el).textContent = partes.join(" · ");
  $(".preench", el).style.width = (job.progresso || 0) + "%";
  el.classList.toggle("erro", job.status === "erro");
  el.classList.toggle("feito", job.status === "concluido");
  const ultimo = (job.log || []).slice(-1)[0] || "";
  $(".etapa", el).textContent =
    job.status === "erro" ? "Erro: " + job.erro
    : job.status === "concluido" ? `Concluído · ${job.clipes.length} cortes`
    : `${job.etapa} (${Math.round(job.progresso)}%)` + (ultimo ? " — " + ultimo.replace(/^\d\d:\d\d:\d\d /, "") : "");
  if (abertos.has(job.id)) $(".log", el).textContent = (job.log || []).join("\n");
  if (job.status === "concluido" && !el._linha) carregarLinha(el, job);
  const caixa = $(".clipes", el);
  for (const c of job.clipes || []) {
    let ce = el._clipes[c.n];
    if (!ce) { ce = el._clipes[c.n] = criarClipe(job, c); caixa.appendChild(ce); }
    atualizarClipe(ce, job, c);
  }
  if (el._linha && el._linha !== "carregando") { el._linhaClipes = job.clipes; el._redesenhar?.(); }
}

async function atualizar() {
  let jobs;
  try { jobs = await api("/api/jobs"); } catch (e) { return; }
  const meus = jobs.filter((j) => (j.perfil || "geral") === perfil);
  for (const resumo of meus) {
    let el = cards[resumo.id];
    if (!el) el = cards[resumo.id] = criarCard(resumo);
    let job = resumo;
    if (resumo.status !== "na fila" || abertos.has(resumo.id)) {
      try { job = await api(`/api/jobs/${resumo.id}`); } catch (e) {}
    }
    detalhes[job.id] = job;
    atualizarCard(el, job);
  }
  const atual = $$(":scope > .job", listaJobs).map((e) => e.dataset.id).join();
  if (atual !== meus.map((j) => j.id).join()) {
    listaJobs.innerHTML = "";
    meus.forEach((j) => listaJobs.appendChild(cards[j.id]));
  }
  if (!meus.length) {
    listaJobs.innerHTML = `<div class="vazio">${perfil === "gta6"
      ? "🌴 Nenhum corte de GTA 6 ainda.<br>Cole o link de uma live de GTA 6 e clique em <b>Gerar cortes</b>."
      : "Nenhum corte ainda. Cole um link e clique em <b>Gerar cortes</b>."}</div>`;
  }
}

// ---------------------------------------------------------------------  linha do tempo
async function carregarLinha(el, job) {
  el._linha = "carregando";
  try {
    const r = await fetch(`/arquivos/${job.id}/linha.json`);
    if (!r.ok) return;
    el._linha = await r.json();
  } catch (e) { return; }
  el._linhaClipes = job.clipes;
  const box = $(".linha-tempo", el);
  box.hidden = false;
  const cv = $("canvas", box);
  el._redesenhar = () => desenharLinha(cv, el._linha, el._linhaClipes);
  el._redesenhar();
  new ResizeObserver(el._redesenhar).observe(cv);
  cv.addEventListener("mousemove", (ev) => {
    const L = el._linha, n = (L.total || []).length;
    const x = (ev.offsetX / cv.clientWidth) * n * L.passo + (L.deslocamento || 0);
    $(".lt-hora", box).textContent = hms(x);
  });
}

function desenharLinha(cv, L, clipes) {
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (!W) return;
  cv.width = W * dpr; cv.height = H * dpr;
  const g = cv.getContext("2d");
  g.scale(dpr, dpr);
  const n = (L.total || []).length;
  if (!n) return;
  const dur = n * L.passo;
  const est = getComputedStyle(document.body);
  const cDest = est.getPropertyValue("--destaque").trim() || "#ffd400";
  const cVerde = est.getPropertyValue("--verde").trim() || "#2ecc71";
  const y = (v) => H - 6 - ((Math.max(-3, Math.min(6, v)) + 3) / 9) * (H - 12);
  for (const c of clipes || []) {
    const x0 = (c.inicio / dur) * W, x1 = (c.fim / dur) * W;
    g.globalAlpha = 0.28; g.fillStyle = cVerde; g.fillRect(x0, 0, Math.max(2, x1 - x0), H);
    g.globalAlpha = 1; g.font = "bold 11px system-ui"; g.fillText(c.n, x0 + 2, 12);
  }
  const linha = (dados, cor, larg) => {
    if (!dados || !dados.length) return;
    g.strokeStyle = cor; g.lineWidth = larg; g.beginPath();
    const passo = Math.max(1, Math.floor(dados.length / W));
    for (let i = 0; i < dados.length; i += passo) {
      let v = -Infinity;
      for (let k = i; k < Math.min(dados.length, i + passo); k++) v = Math.max(v, dados[k]);
      const x = (i / dados.length) * W;
      i === 0 ? g.moveTo(x, y(v)) : g.lineTo(x, y(v));
    }
    g.stroke();
  };
  linha(L.volume, "rgba(139,147,165,.55)", 1);
  linha(L.voz, "rgba(255,95,162,.75)", 1);
  linha(L.chat, "rgba(78,168,255,.85)", 1);
  linha(L.replay, "rgba(255,179,71,.9)", 1.2);
  linha(L.total, cDest, 1.8);
}

// =====================================================================  modais
function abrirModal(id) { $(id).hidden = false; }
function fecharModal(id) {
  $(id).hidden = true;
  $$("video", $(id)).forEach((v) => v.pause());
}
$$(".modal").forEach((m) => {
  m.addEventListener("click", (ev) => { if (ev.target === m || ev.target.closest("[data-fechar]")) fecharModal("#" + m.id); });
});
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") $$(".modal").forEach((m) => !m.hidden && fecharModal("#" + m.id)); });

// ---------------------------------------------------------------------  editor
const ed = { job: null, c: null, ini: 0, fim: 0, jmin: 0, jmax: 0, temFonte: true };
const edVideo = $("#ed-video");

function abrirEditor(job, n) {
  const c = job.clipes.find((x) => x.n === n);
  Object.assign(ed, { job, c, ini: c.inicio, fim: c.fim });
  const dur = job.fonte?.duracao || c.fim + 60;
  ed.jmin = Math.max(0, c.inicio - 30);
  ed.jmax = Math.min(dur, c.fim + 30);
  $(".ed-n", $("#modal-editar")).textContent = `#${c.n}`;
  $("#ed-titulo").value = c.titulo || "";
  $("#ed-desc").value = c.descricao || "";
  const base = job.cfg_render || job.cfg || {};
  $("#ed-legendas").checked = c.opcoes?.legendas ?? base.legendas ?? true;
  $("#ed-mostrar-titulo").checked = c.opcoes?.mostrar_titulo ?? base.titulo ?? true;
  $("#ed-marca").value = c.opcoes?.marca ?? base.marca ?? "";
  for (const r of [$("#ed-r-ini"), $("#ed-r-fim")]) { r.min = ed.jmin; r.max = ed.jmax; }
  ed.temFonte = true;
  $(".ed-sem-fonte").hidden = true;
  edVideo.hidden = false; $("#ed-trilha").hidden = false; $(".ed-tempos").hidden = false;
  edVideo.src = `/fonte/${job.id}`;
  edVideo.onloadedmetadata = () => { edVideo.currentTime = ed.ini; };
  edVideo.onerror = () => {
    ed.temFonte = false;
    edVideo.hidden = true; $("#ed-trilha").hidden = true; $(".ed-tempos").hidden = true;
    $(".ed-sem-fonte").hidden = false;
  };
  edAtualizar();
  contarDesc("#ed-desc", "#ed-cont");
  abrirModal("#modal-editar");
}

function edAtualizar() {
  const span = ed.jmax - ed.jmin || 1;
  $("#ed-r-ini").value = ed.ini; $("#ed-r-fim").value = ed.fim;
  const sel = $(".ed-sel");
  sel.style.left = ((ed.ini - ed.jmin) / span) * 100 + "%";
  sel.style.width = ((ed.fim - ed.ini) / span) * 100 + "%";
  const d = ed.job?.deslocamento || 0;
  $("#ed-t-ini").textContent = hms(ed.ini + d, true);
  $("#ed-t-fim").textContent = hms(ed.fim + d, true);
  $("#ed-dur").textContent = (ed.fim - ed.ini).toFixed(1).replace(".", ",") + "s";
  edCabeca();
}
function edCabeca() {
  const span = ed.jmax - ed.jmin || 1;
  $(".ed-cabeca").style.left = Math.max(0, Math.min(100, ((edVideo.currentTime - ed.jmin) / span) * 100)) + "%";
}
function edDefinir(qual, valor, buscar = true) {
  valor = Math.max(ed.jmin, Math.min(ed.jmax, valor));
  if (qual === "ini") ed.ini = Math.min(valor, ed.fim - 1);
  else ed.fim = Math.max(valor, ed.ini + 1);
  // aumenta a janela se encostar na borda
  const dur = ed.job.fonte?.duracao || ed.jmax + 30;
  if (ed.ini - ed.jmin < 3) ed.jmin = Math.max(0, ed.ini - 30);
  if (ed.jmax - ed.fim < 3) ed.jmax = Math.min(dur, ed.fim + 30);
  for (const r of [$("#ed-r-ini"), $("#ed-r-fim")]) { r.min = ed.jmin; r.max = ed.jmax; }
  edAtualizar();
  if (buscar && ed.temFonte) { edVideo.pause(); edVideo.currentTime = qual === "ini" ? ed.ini : ed.fim; }
}
$("#ed-r-ini").addEventListener("input", (e) => edDefinir("ini", Number(e.target.value)));
$("#ed-r-fim").addEventListener("input", (e) => edDefinir("fim", Number(e.target.value)));
$$("[data-ajuste]").forEach((b) => (b.onclick = () => {
  const [q, v] = b.dataset.ajuste.split(":");
  edDefinir(q, (q === "ini" ? ed.ini : ed.fim) + Number(v));
}));
$$("[data-marcar]").forEach((b) => (b.onclick = () => edDefinir(b.dataset.marcar, edVideo.currentTime, false)));
$("#ed-play").onclick = () => {
  if (!edVideo.paused) { edVideo.pause(); return; }
  if (edVideo.currentTime < ed.ini || edVideo.currentTime >= ed.fim - 0.1) edVideo.currentTime = ed.ini;
  edVideo.play();
};
edVideo.addEventListener("timeupdate", () => {
  edCabeca();
  if (!edVideo.paused && edVideo.currentTime >= ed.fim) { edVideo.pause(); edVideo.currentTime = ed.fim; }
});
edVideo.addEventListener("play", () => ($("#ed-play").textContent = "⏸ Pausar"));
edVideo.addEventListener("pause", () => ($("#ed-play").textContent = "▶ Prévia do corte"));
$("#ed-trilha").addEventListener("click", (ev) => {
  if (ev.target.type === "range" && ev.offsetY < 0) return;
  const r = $("#ed-trilha").getBoundingClientRect();
  const t = ed.jmin + ((ev.clientX - r.left) / r.width) * (ed.jmax - ed.jmin);
  if (ed.temFonte) { edVideo.currentTime = t; edCabeca(); }
});

function contarDesc(campo, cont) {
  const n = $(campo).value.length;
  $(cont).textContent = `${n}/2200`;
  $(cont).style.color = n > 2200 ? "var(--vermelho)" : "";
}
$("#ed-desc").addEventListener("input", () => contarDesc("#ed-desc", "#ed-cont"));
$("#ed-gerar-desc").onclick = async () => {
  try {
    const d = await api(`/api/jobs/${ed.job.id}/clipes/${ed.c.n}/descricao`, { titulo: $("#ed-titulo").value });
    $("#ed-desc").value = d.descricao; contarDesc("#ed-desc", "#ed-cont");
  } catch (e) { alertaLeve(e.message); }
};
$("#ed-salvar").onclick = async () => {
  const corpo = {
    titulo: $("#ed-titulo").value.trim(), descricao: $("#ed-desc").value,
    legendas: $("#ed-legendas").checked, mostrar_titulo: $("#ed-mostrar-titulo").checked,
  };
  const base = ed.job.cfg_render || ed.job.cfg || {};
  const marcaAtual = ed.c.opcoes?.marca ?? base.marca ?? "";
  if ($("#ed-marca").value.trim() !== marcaAtual) corpo.marca = $("#ed-marca").value.trim();
  if (Math.abs(ed.ini - ed.c.inicio) > 0.05 || Math.abs(ed.fim - ed.c.fim) > 0.05) {
    corpo.inicio = Number(ed.ini.toFixed(2)); corpo.fim = Number(ed.fim.toFixed(2));
  }
  try {
    await api(`/api/jobs/${ed.job.id}/clipes/${ed.c.n}/editar`, corpo);
    fecharModal("#modal-editar");
    atualizar();
  } catch (e) { alertaLeve(e.message); }
};

// ---------------------------------------------------------------------  postar
const po = { job: null, c: null };
function abrirPostar(job, n) {
  const c = job.clipes.find((x) => x.n === n);
  Object.assign(po, { job, c });
  $(".po-n", $("#modal-postar")).textContent = `#${c.n}`;
  $("#po-video").src = `/arquivos/${job.id}/${c.arquivo}?v=${c.versao || 1}`;
  $("#po-desc").value = c.descricao || "";
  contarDesc("#po-desc", "#po-cont");
  $("#po-msg").textContent = ""; $("#po-msg").className = "msg";
  const tk = contas?.tiktok || {}, ig = contas?.instagram || {};
  $("#po-tk").disabled = !tk.conectado; $("#po-tk").checked = !!tk.conectado;
  $("#po-ig").disabled = !ig.conectado; $("#po-ig").checked = !!ig.conectado;
  $(".rede-estado", $("#po-tiktok")).textContent = tk.conectado ? `conectado: ${tk.nome}` : "não conectado (aba Contas)";
  $(".rede-estado", $("#po-instagram")).textContent = ig.conectado ? `@${ig.nome}` : "não conectado (aba Contas)";
  $("#po-tiktok").classList.toggle("desligada", !tk.conectado);
  $("#po-instagram").classList.toggle("desligada", !ig.conectado);
  $("#po-tk-modo").value = tk.padrao_modo || "rascunho";
  preencherPrivacidade(null, tk.padrao_privacidade);
  poModo();
  abrirModal("#modal-postar");
}
function preencherPrivacidade(opcoes, preferida) {
  const sel = $("#po-tk-priv");
  const lista = opcoes && opcoes.length ? opcoes : Object.keys(PRIV);
  sel.innerHTML = lista.map((o) => `<option value="${o}">${PRIV[o] || o}</option>`).join("");
  if (preferida && lista.includes(preferida)) sel.value = preferida;
}
async function poModo() {
  const direto = $("#po-tk-modo").value === "direto";
  $$(".so-direto", $("#po-tiktok")).forEach((e) => (e.hidden = !direto));
  if (direto && contas?.tiktok?.conectado) {
    try {
      const info = await api("/api/contas/tiktok/criador");
      preencherPrivacidade(info.privacy_level_options, contas.tiktok.padrao_privacidade);
      if (info.max_video_post_duration_sec && po.c && po.c.duracao > info.max_video_post_duration_sec) {
        $("#po-msg").textContent = `Atenção: sua conta aceita vídeos de até ${info.max_video_post_duration_sec}s.`;
      }
    } catch (e) { $("#po-msg").textContent = "Não consegui ler as opções da conta: " + e.message; }
  }
}
$("#po-tk-modo").onchange = poModo;
$("#po-desc").addEventListener("input", () => contarDesc("#po-desc", "#po-cont"));
$("#po-enviar").onclick = async () => {
  const plataformas = [];
  if ($("#po-tk").checked) plataformas.push("tiktok");
  if ($("#po-ig").checked) plataformas.push("instagram");
  const msg = $("#po-msg");
  msg.className = "msg";
  if (!plataformas.length) { msg.className = "msg erro"; msg.textContent = "Escolha TikTok e/ou Instagram."; return; }
  const corpo = {
    plataformas, legenda: $("#po-desc").value,
    opcoes: {
      tiktok: { modo: $("#po-tk-modo").value, privacidade: $("#po-tk-priv").value,
                comentarios: $("#po-tk-com").checked, dueto: $("#po-tk-duet").checked, stitch: $("#po-tk-stitch").checked },
      instagram: { feed: $("#po-ig-feed").checked },
    },
  };
  $("#po-enviar").disabled = true;
  try {
    await api(`/api/jobs/${po.job.id}/clipes/${po.c.n}/postar`, corpo);
    fecharModal("#modal-postar");
    atualizar(); carregarPubs();
  } catch (e) { msg.className = "msg erro"; msg.textContent = e.message; }
  $("#po-enviar").disabled = false;
};

function alertaLeve(txt) {
  const m = document.createElement("div");
  m.textContent = txt;
  Object.assign(m.style, { position: "fixed", bottom: "20px", left: "50%", transform: "translateX(-50%)", background: "var(--vermelho)",
    color: "#fff", padding: "10px 16px", borderRadius: "10px", zIndex: 99, fontWeight: 700 });
  document.body.appendChild(m);
  setTimeout(() => m.remove(), 4500);
}

// =====================================================================  contas
async function carregarContas() {
  try { contas = await api("/api/contas"); } catch (e) { return; }
  const tk = contas.tiktok, ig = contas.instagram;
  $("#mini-tiktok").classList.toggle("on", tk.conectado);
  $("#mini-instagram").classList.toggle("on", ig.conectado);
  $("#mini-tiktok").title = tk.conectado ? `TikTok: ${tk.nome}` : "TikTok não conectado";
  $("#mini-instagram").title = ig.conectado ? `Instagram: @${ig.nome}` : "Instagram não conectado";
  const ct = $("#conta-tiktok"), ci = $("#conta-instagram");
  const et = $(".estado", ct), ei = $(".estado", ci);
  et.textContent = tk.conectado ? `✅ ${tk.nome}` : tk.configurado ? "app salvo · falta conectar" : "não conectado";
  et.classList.toggle("on", tk.conectado);
  ei.textContent = ig.conectado ? `✅ @${ig.nome}` : "não conectado";
  ei.classList.toggle("on", ig.conectado);
  if (!$('[name="client_key"]', ct).value) $('[name="client_key"]', ct).value = tk.client_key || "";
  if (!$('[name="redirect_uri"]', ct).value) $('[name="redirect_uri"]', ct).value = tk.redirect_uri || "";
  $('[name="padrao_modo"]', ct).value = tk.padrao_modo;
  $('[name="padrao_privacidade"]', ct).value = tk.padrao_privacidade;
  if (!$('[name="app_id"]', ci).value) $('[name="app_id"]', ci).value = ig.app_id || "";
  if (!$('[name="versao"]', ci).value) $('[name="versao"]', ci).value = ig.versao || "v23.0";
  const sel = $('[name="ig_conta"]', ci);
  sel.innerHTML = (ig.contas || []).map((c) => `<option value="${c.id}">@${c.username} (${c.pagina})</option>`).join("")
    || "<option value=''>—</option>";
  const atualC = (ig.contas || []).find((c) => c.username === ig.nome);
  if (atualC) sel.value = atualC.id;
  atualizarDepois();
}

async function acaoConta(acao) {
  const ct = $("#conta-tiktok"), ci = $("#conta-instagram");
  const v = (el, n) => $(`[name="${n}"]`, el).value.trim();
  try {
    if (acao === "tk-salvar" || acao === "tk-conectar") {
      await api("/api/contas/tiktok/config", { client_key: v(ct, "client_key"), client_secret: v(ct, "client_secret"), redirect_uri: v(ct, "redirect_uri") });
      $('[name="client_secret"]', ct).value = "";
      if (acao === "tk-conectar") {
        const { url } = await api("/api/contas/tiktok/login");
        window.open(url, "_blank");
        const t = setInterval(async () => { await carregarContas(); if (contas.tiktok.conectado) clearInterval(t); }, 3000);
        setTimeout(() => clearInterval(t), 300000);
      }
    } else if (acao === "tk-codigo") {
      await api("/api/contas/tiktok/codigo", { codigo: v(ct, "tk_codigo") });
    } else if (acao === "tk-sair") {
      await api("/api/contas/tiktok/desconectar", {});
    } else if (acao === "ig-conectar") {
      await api("/api/contas/instagram", { app_id: v(ci, "app_id"), app_secret: v(ci, "app_secret"), token: v(ci, "token"), versao: v(ci, "versao") });
      $('[name="app_secret"]', ci).value = ""; $('[name="token"]', ci).value = "";
    } else if (acao === "ig-sair") {
      await api("/api/contas/instagram/desconectar", {});
    }
  } catch (e) { alertaLeve(e.message); }
  carregarContas();
}
$$("[data-acao]").forEach((b) => (b.onclick = () => acaoConta(b.dataset.acao)));
$('#conta-tiktok [name="padrao_modo"]').onchange = $('#conta-tiktok [name="padrao_privacidade"]').onchange = async () => {
  const ct = $("#conta-tiktok");
  await api("/api/contas/tiktok/padroes", { modo: $('[name="padrao_modo"]', ct).value, privacidade: $('[name="padrao_privacidade"]', ct).value });
  carregarContas();
};
$('#conta-instagram [name="ig_conta"]').onchange = async (e) => { await api("/api/contas/instagram/escolher", { id: e.target.value }); carregarContas(); };

// =====================================================================  publicações
async function carregarPubs() {
  let pubs;
  try { pubs = await api("/api/publicacoes"); } catch (e) { return; }
  pubsAtivas = pubs.filter((p) => ["na fila", "enviando", "processando"].includes(p.status)).length;
  const badge = $("#pubs-badge");
  badge.hidden = !pubsAtivas; badge.textContent = pubsAtivas;
  if ($("#aba-pubs").hidden) return;
  const lista = $("#lista-pubs");
  if (!pubs.length) { lista.innerHTML = '<div class="vazio">Nenhuma publicação ainda. Nos cortes prontos, clique em <b>📤 Postar</b>.</div>'; return; }
  lista.innerHTML = "";
  for (const p of pubs) {
    const d = document.createElement("div");
    d.className = "pub";
    const rede = p.plataforma === "tiktok" ? "TikTok" : "Instagram";
    d.innerHTML = `<div class="pub-rede ${p.plataforma}">${rede}</div>
      <div><div class="pub-tit"></div><div class="pub-msg"></div></div>
      <div><span class="pub-st ${p.status}">${ST_POST[p.status] || p.status}</span></div>`;
    $(".pub-tit", d).textContent = `Corte ${p.n} · ${p.titulo || ""}`;
    $(".pub-msg", d).textContent = `${new Date(p.criado * 1000).toLocaleString("pt-BR")} · ${p.msg || ""}`;
    if (p.link) { const a = document.createElement("a"); a.href = p.link; a.target = "_blank"; a.textContent = " abrir ↗"; a.style.color = "var(--dest2)"; $(".pub-msg", d).appendChild(a); }
    lista.appendChild(d);
  }
}

// =====================================================================  sub-abas (streamers / manual)
function modoLab(m) {
  $$(".sub-abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.modo === m));
  $("#modo-streamers").hidden = m !== "streamers";
  form.hidden = m !== "manual";
  guardar("labdecortes.modo", m);
}
$$(".sub-abas button").forEach((b) => (b.onclick = () => modoLab(b.dataset.modo)));

// =====================================================================  postar automático (barra global)
let auto = { ativo: false, redes: [] };
async function carregarAuto() {
  try { auto = await api("/api/auto"); } catch (e) {}
  pintarAuto();
}
function pintarAuto() {
  const barra = $("#auto-barra");
  barra.classList.toggle("ligado", !!auto.ativo);
  $("#auto-ativo").checked = !!auto.ativo;
  for (const chip of $$(".rede-chip", barra)) {
    const rede = chip.dataset.rede, c = contas?.[rede];
    const cb = $("input", chip);
    cb.checked = (auto.redes || []).includes(rede);
    chip.classList.toggle("off", !c?.conectado);
    $("em", chip).textContent = c?.conectado ? (rede === "instagram" ? "@" + c.nome : c.nome) : "conectar →";
  }
  const nomes = (auto.redes || []).map((r) => (r === "tiktok" ? "TikTok" : "Instagram")).join(" e ");
  $("#auto-sub").textContent = auto.ativo
    ? `Ligado: todo corte pronto é postado no ${nomes || "—"} automaticamente.`
    : "Desligado: os cortes ficam esperando você revisar e postar.";
}
async function salvarAuto(ativo, redes) {
  try { auto = await api("/api/auto", { ativo, redes }); }
  catch (e) { alertaLeve(e.message); }
  pintarAuto();
}
$("#auto-ativo").onchange = (e) => {
  let redes = [...(auto.redes || [])];
  if (e.target.checked && !redes.length) redes = ["tiktok", "instagram"].filter((r) => contas?.[r]?.conectado);
  salvarAuto(e.target.checked, redes);
};
for (const chip of $$(".rede-chip")) {
  chip.addEventListener("click", (ev) => {
    const rede = chip.dataset.rede;
    if (!contas?.[rede]?.conectado) { ev.preventDefault(); irPara("contas"); return; }
  });
  $("input", chip).onchange = (e) => {
    const rede = chip.dataset.rede;
    const redes = new Set(auto.redes || []);
    e.target.checked ? redes.add(rede) : redes.delete(rede);
    salvarAuto(auto.ativo && redes.size > 0, [...redes]);
  };
}

// =====================================================================  radar de streamers
let radar = null;
let tCfg = null;
function enviarCfgBase() {
  clearTimeout(tCfg);
  tCfg = setTimeout(() => {
    const { url, manuais, trecho_ini, trecho_fim, ...cfg } = lerForm();
    api("/api/radar/config", { cfg_base: cfg }).catch(() => {});
  }, 800);
}
function haQuanto(ts) {
  if (!ts) return "nunca";
  const s = Math.round(Date.now() / 1000 - ts);
  return s < 60 ? "agora" : s < 3600 ? `há ${Math.round(s / 60)} min` : `há ${Math.round(s / 3600)} h`;
}
async function carregarRadar() {
  try { radar = await api("/api/radar"); } catch (e) { return; }
  const st = $("#radar-status");
  const ativos = radar.streamers.filter((s) => s.ativo).length;
  if (radar.rodando) st.textContent = "🔎 Verificando os streamers agora...";
  else if (radar.ligado) {
    const falta = Math.max(0, Math.round((radar.proxima - radar.agora) / 60));
    st.textContent = `● Ligado · ${ativos} streamer(s) · próxima verificação em ${falta} min`;
  } else st.textContent = "Desligado · ligue para buscar sozinho";
  st.classList.toggle("on", !!radar.ligado);
  $("#radar-ligado").checked = !!radar.ligado;
  const campos = { "#rd-filtro": radar.filtro, "#rd-periodo": radar.periodo, "#rd-por": radar.por_streamer, "#rd-min": radar.min_views, "#rd-intervalo": radar.intervalo_min };
  for (const [sel, v] of Object.entries(campos)) if (document.activeElement !== $(sel)) $(sel).value = v;
  $("#radar-log").textContent = (radar.log || []).slice().reverse().join("\n") || "Nada ainda.";
  $("#dc-ligado").checked = !!radar.descobrir;
  $$(".dc-plat").forEach((c) => (c.checked = (radar.descobrir_plats || []).includes(c.value)));
  if (document.activeElement !== $("#dc-idioma")) $("#dc-idioma").value = radar.idioma ?? "pt";
  for (const [sel, v] of Object.entries({ "#rd-dmax": radar.descobrir_max, "#rd-dmin": radar.descobrir_min_viewers, "#rd-termo": radar.termo_youtube }))
    if (document.activeElement !== $(sel)) $(sel).value = v;
  $("#st-cont").textContent = radar.streamers.length ? `${radar.streamers.filter((s) => s.ativo).length} ativos` : "";
  const lista = $("#lista-streamers");
  if (!radar.streamers.length) {
    lista.innerHTML = '<div class="dica">Ainda vazio. Ligue o radar ou clique em <b>🔎 Descobrir streamers agora</b> que o Lab acha quem está jogando GTA 6.</div>';
    return;
  }
  lista.innerHTML = "";
  for (const s of radar.streamers) {
    const d = document.createElement("div");
    d.className = "streamer" + (s.ativo ? "" : " inativo");
    d.innerHTML = `<span class="plat ${s.plataforma}">${PLAT[s.plataforma] || s.plataforma}</span>
      <div><div class="st-nome"></div><div class="st-info"></div></div>
      <div class="st-bts">
        <label class="switch" title="Ativo"><input type="checkbox" ${s.ativo ? "checked" : ""}><span></span></label>
        <button type="button" class="sec" title="Verificar agora">↻</button>
        <button type="button" class="sec perigo" title="Remover">✕</button>
      </div>`;
    $(".st-nome", d).textContent = s.plataforma === "outra" ? s.usuario : s.usuario.startsWith("channel/") ? (s.nome || s.usuario) : "@" + s.usuario;
    if (s.auto) { const t = document.createElement("span"); t.className = "tag-auto"; t.textContent = "AUTO"; t.title = "Descoberto automaticamente"; $(".st-nome", d).appendChild(t); }
    $(".st-info", d).textContent = `${s.tipo === "clipes" ? "clipes mais vistos" : "lives completas"} · ${s.status} · ${haQuanto(s.ultima)} · ${s.total || 0} no total`;
    $("input", d).onchange = async (e) => { await api(`/api/radar/streamers/${s.id}`, { ativo: e.target.checked }); carregarRadar(); };
    const [bVer, bDel] = $$("button", d);
    bVer.onclick = async () => { enviarCfgBase(); await api("/api/radar/verificar", { id: s.id }); setTimeout(carregarRadar, 800); };
    bDel.onclick = async () => { if (confirm(`Remover ${s.nome || s.usuario}?` + (s.auto ? " Ele não será descoberto de novo." : ""))) { await api(`/api/radar/streamers/${s.id}`, undefined, "DELETE"); carregarRadar(); } };
    lista.appendChild(d);
  }
}
function dicaPlataforma() {
  const p = $("#st-plat").value;
  const tipo = $("#st-tipo");
  const soLives = p === "youtube" || p === "outra";
  tipo.disabled = soLives;
  if (soLives) tipo.value = "lives";
  $("#st-usuario").placeholder = p === "outra" ? "Cole o link do canal" : p === "youtube" ? "@canal do YouTube" : "@streamer";
}
$("#st-plat").onchange = dicaPlataforma;
$("#st-usuario").addEventListener("input", (e) => {
  const v = e.target.value;
  if (/twitch\.tv/i.test(v)) $("#st-plat").value = "twitch";
  else if (/kick\.com/i.test(v)) $("#st-plat").value = "kick";
  else if (/youtube\.com|youtu\.be/i.test(v)) $("#st-plat").value = "youtube";
  dicaPlataforma();
});
$("#st-add").onclick = async () => {
  const msg = $("#st-msg");
  msg.className = "msg";
  try {
    await api("/api/radar/streamers", { usuario: $("#st-usuario").value, plataforma: $("#st-plat").value, tipo: $("#st-tipo").value });
    $("#st-usuario").value = "";
    msg.textContent = "Adicionado! " + (radar?.ligado ? "Ele entra na próxima verificação." : "Ligue o radar (botão ao lado do título).");
    enviarCfgBase();
    carregarRadar();
  } catch (e) { msg.className = "msg erro"; msg.textContent = e.message; }
};
$("#st-usuario").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); $("#st-add").click(); } });
$("#radar-ligado").onchange = async (e) => {
  const { url, manuais, trecho_ini, trecho_fim, ...cfg } = lerForm();
  await api("/api/radar/config", { ligado: e.target.checked, cfg_base: cfg });
  carregarRadar();
};
async function salvarDescoberta() {
  await api("/api/radar/config", {
    descobrir: $("#dc-ligado").checked, descobrir_plats: $$(".dc-plat").filter((c) => c.checked).map((c) => c.value),
    idioma: $("#dc-idioma").value,
  });
  carregarRadar();
}
$("#dc-ligado").onchange = salvarDescoberta;
$$(".dc-plat").forEach((c) => (c.onchange = salvarDescoberta));
$("#dc-idioma").onchange = salvarDescoberta;
$("#dc-agora").onclick = async () => {
  const b = $("#dc-agora");
  b.disabled = true; b.textContent = "🔎 Procurando quem está jogando GTA 6...";
  await salvarDescoberta();
  await api("/api/radar/descobrir", {});
  const antes = radar?.streamers?.length || 0;
  let n = 0;
  const t = setInterval(async () => {
    await carregarRadar();
    if (++n > 30 || (radar.streamers.length !== antes && n > 3)) {
      clearInterval(t); b.disabled = false; b.textContent = "🔎 Descobrir streamers agora";
    }
  }, 2000);
};
$("#radar-agora").onclick = async () => { enviarCfgBase(); await api("/api/radar/verificar", {}); setTimeout(carregarRadar, 800); };
for (const sel of ["#rd-filtro", "#rd-periodo", "#rd-por", "#rd-min", "#rd-intervalo", "#rd-dmax", "#rd-dmin", "#rd-termo"]) {
  $(sel).addEventListener("change", () => api("/api/radar/config", {
    filtro: $("#rd-filtro").value, periodo: $("#rd-periodo").value, por_streamer: Number($("#rd-por").value),
    min_views: Number($("#rd-min").value), intervalo_min: Number($("#rd-intervalo").value),
    descobrir_max: Number($("#rd-dmax").value), descobrir_min_viewers: Number($("#rd-dmin").value), termo_youtube: $("#rd-termo").value,
  }).then(carregarRadar));
}

// =====================================================================  marca d'água
async function trocarMarca(marca, job) {
  marca = (marca || "").trim();
  if (marca && !marca.startsWith("@") && !marca.includes(" ")) marca = "@" + marca;
  const r = await api("/api/marca", job ? { marca, job } : { marca });
  if (!job) {
    form.marca.value = marca; salvarForm();
    for (const p of Object.keys(window.PERFIS)) {
      const c = ler("labdecortes.cfg." + p) || {};
      c.marca = marca; guardar("labdecortes.cfg." + p, c);
    }
  }
  atualizar();
  return r;
}
$("#marca-aplicar").onclick = async () => {
  const msg = $("#marca-msg");
  const v = $("#marca-global").value;
  if (!confirm(`Trocar a marca d'água para "${v || "(sem marca)"}" em TODOS os cortes já feitos? Os vídeos serão refeitos.`)) return;
  try {
    const r = await trocarMarca(v);
    msg.textContent = `✅ ${r.refeitos} cortes sendo refeitos com o novo @` + (r.sem_fonte ? ` · ${r.sem_fonte} sem o vídeo original (apagado)` : "") + ". Os próximos já saem com ele.";
  } catch (e) { msg.textContent = "⚠ " + e.message; }
};

// =====================================================================  ciclo
async function ciclo() {
  await atualizar();
  await carregarPubs();
  if (!$("#aba-lab").hidden && !$("#modo-streamers").hidden) await carregarRadar();
  const ativo = Object.values(cards).some((el) => !el.classList.contains("feito") && !el.classList.contains("erro"))
    || $(".clipe.ocupado") || pubsAtivas > 0;
  setTimeout(ciclo, ativo ? 2000 : 8000);
}

const abaInicial = ler("labdecortes.aba") || "gta6";
perfil = abaInicial === "geral" ? "geral" : "gta6";
carregarForm();
$("#marca-global").value = form.marca.value;
modoLab(ler("labdecortes.modo") || "streamers");
carregarContas().then(carregarAuto);
carregarRadar();
irPara(abaInicial);
contagem();
setInterval(contagem, 30000);
ciclo();
