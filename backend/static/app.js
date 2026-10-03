"use strict";
const view = document.querySelector("#view"),
  feedback = document.querySelector("#feedback"),
  identity = document.querySelector("#identity"),
  net = document.querySelector("#network"),
  dot = document.querySelector("#connection-dot");
let room = new URLSearchParams(location.search).get("room") || "",
  team = null,
  token = "",
  sessionId = "",
  state = null,
  socket = null,
  retry = 0,
  selected = null,
  pending = false,
  lastSeen = Date.now(),
  retryTimer,
  heartbeat;
function el(tag, cls, value) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (value !== undefined) n.textContent = value;
  return n;
}
function add(tag, cls, value) {
  const n = el(tag, cls, value);
  view.append(n);
  return n;
}
function art() {
  const n = el("div", "join-art");
  for (let i = 0; i < 3; i++) n.append(el("div", "orbit"));
  n.append(el("div", "nucleus"));
  return n;
}
function message(value) {
  feedback.textContent = value || "";
}
function connection(online) {
  dot.classList.toggle("online", online);
  net.textContent = online ? "CANAL / EN LIGNE" : "CANAL / RECONNEXION";
}
async function api(path, body) {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = await response.json();
  if (!response.ok)
    throw Error(
      typeof json.detail === "string"
        ? json.detail
        : "Vérifiez les informations saisies.",
    );
  return json;
}
function join() {
  clearTimeout(retryTimer);
  clearInterval(heartbeat);
  state = null;
  identity.hidden = true;
  view.replaceChildren();
  add("p", "eyebrow", "Contrôleur d'équipe / 01");
  add("h1", "", "Entrez dans la conversation.");
  add(
    "p",
    "",
    "Quatre équipes. Une histoire commune. Vos choix tracent la suite.",
  );
  view.append(art());
  const form = add("form");
  const label = el("label", "", "CODE DE SESSION");
  label.htmlFor = "room";
  form.append(label);
  const input = el("input");
  input.id = "room";
  input.name = "room";
  input.inputMode = "numeric";
  input.autocomplete = "off";
  input.pattern = "[0-9]{4}";
  input.maxLength = 4;
  input.placeholder = "4821";
  input.required = true;
  input.value = room;
  form.append(input);
  const submit = el("button", "primary", "REJOINDRE LA SESSION   ↗");
  submit.type = "submit";
  form.append(submit);
  add("p", "hint", "Le code est affiché sur l'écran principal.");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    room = input.value;
    submit.disabled = true;
    try {
      await teams();
      message("");
    } catch (err) {
      message(err.message);
      submit.disabled = false;
    }
  });
}
async function teams() {
  const info = await api("/api/rooms/" + room);
  view.replaceChildren();
  add("p", "eyebrow", "SESSION / " + room);
  add("h1", "", "Choisissez votre équipe.");
  add(
    "p",
    "",
    "Un seul téléphone devient le contrôleur officiel de chaque équipe.",
  );
  for (let i = 0; i < 4; i++) {
    const btn = add("button", "team");
    btn.style.setProperty("--team", info.colors[i]);
    btn.append(
      el("b", "", String(i + 1).padStart(2, "0")),
      el("span", "", info.names[i]),
    );
    let saved;
    try {
      saved = JSON.parse(
        localStorage.getItem("palo:" + room + ":" + i) || "null",
      );
    } catch {}
    const occupied = info.occupied.includes(i) && !saved;
    btn.append(
      el("small", "", occupied ? "OCCUPÉE" : saved ? "REPRENDRE" : "REJOINDRE"),
    );
    btn.disabled = occupied;
    btn.addEventListener("click", async () => {
      if (info.requires_pin && !saved) {
        pinForm(i, info);
        return;
      }
      await claim(i, "", saved);
    });
  }
  const back = add("button", "primary", "CHANGER DE SESSION");
  back.addEventListener("click", join);
}
function pinForm(i, info) {
  view.replaceChildren();
  add("p", "eyebrow", info.names[i]);
  add("h1", "", "Code de l'équipe");
  const form = add("form");
  const label = el("label", "", "PIN DE L'ÉQUIPE");
  label.htmlFor = "pin";
  const input = el("input");
  input.id = "pin";
  input.type = "password";
  input.inputMode = "numeric";
  input.maxLength = 8;
  input.required = true;
  form.append(label, input);
  const btn = el("button", "primary", "CONFIRMER");
  form.append(btn);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    await claim(i, input.value, null);
  });
}
async function claim(i, pin, saved) {
  try {
    const data = await api("/api/rooms/" + room + "/claim", {
      team: i,
      pin,
      reconnect_token: saved?.token || "",
    });
    team = i;
    token = data.token;
    sessionId = data.session_id;
    localStorage.setItem(
      "palo:" + room + ":" + team,
      JSON.stringify({ token, sessionId }),
    );
    connect();
  } catch (err) {
    message(err.message);
  }
}
function waiting(title, detail) {
  view.replaceChildren();
  const box = add("div", "waiting");
  box.append(
    el("p", "eyebrow", "SIMULATION / " + room),
    art(),
    el("h1", "", title),
    el("p", "", detail),
    el("p", "hint", "REGARDEZ L'ÉCRAN PRINCIPAL"),
  );
  box.append(el("span", "cursor"));
}
function connect() {
  clearTimeout(retryTimer);
  clearInterval(heartbeat);
  connection(false);
  waiting("Connexion…", "Ouverture du canal de votre équipe.");
  const ws = new WebSocket(
    (location.protocol === "https:" ? "wss://" : "ws://") +
      location.host +
      "/ws/team/" +
      room +
      "/" +
      team,
  );
  socket = ws;
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "auth", token }));
    lastSeen = Date.now();
    heartbeat = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}');
      if (Date.now() - lastSeen > 40000) ws.close();
    }, 12000);
  };
  ws.onmessage = (e) => {
    lastSeen = Date.now();
    let data;
    try {
      data = JSON.parse(e.data);
    } catch {
      return;
    }
    if (data.type === "closed") {
      closed();
      return;
    }
    if (data.type === "error") {
      pending = false;
      message(data.message);
      if (state) render();
      return;
    }
    if (data.type !== "snapshot") return;
    connection(true);
    retry = 0;
    message("");
    if (!state || state.phase_id !== data.phase_id) {
      selected = null;
      pending = false;
    } else if (data.own_answer) {
      pending = false;
    }
    state = data;
    sessionId = data.session_id;
    render();
  };
  ws.onclose = (e) => {
    clearInterval(heartbeat);
    if (socket !== ws) return;
    connection(false);
    if (e.code === 1000) {
      closed();
      return;
    }
    if (e.code === 4409) {
      waiting(
        "Contrôleur déjà actif.",
        "Fermez l'autre onglet de cette équipe avant de reconnecter.",
      );
      message("Rechargez ensuite cette page.");
      return;
    }
    if (e.code === 4403 || e.code === 4400) {
      waiting(
        "Session indisponible.",
        "Le serveur a peut-être redémarré. Demandez le nouveau code à l'animateur.",
      );
      const btn = add("button", "primary", "REJOINDRE UNE SESSION");
      btn.onclick = join;
      return;
    }
    waiting(
      "Connexion perdue.",
      "Votre réponse verrouillée reste conservée. Tentative de reconnexion…",
    );
    retryTimer = setTimeout(connect, Math.min(1000 * 2 ** retry++, 10000));
  };
  ws.onerror = () => connection(false);
}
function closed() {
  clearTimeout(retryTimer);
  clearInterval(heartbeat);
  if (socket) {
    const old = socket;
    socket = null;
    old.close();
  }
  connection(false);
  waiting("Session terminée.", "Merci d'avoir participé à la simulation.");
  net.textContent = "CANAL / FERMÉ";
  const btn = add("button", "primary", "NOUVELLE SESSION");
  btn.onclick = join;
}
function render() {
  const own = state.team;
  identity.hidden = false;
  identity.style.setProperty("--accent", state.colors[own]);
  document.documentElement.style.setProperty("--accent", state.colors[own]);
  identity.replaceChildren(
    el("strong", "", state.names[own]),
    el(
      "span",
      "",
      ("score" in state ? state.score : state.scores[own]) +
        " PTS · " +
        state.round_id +
        "/4",
    ),
  );
  const open =
    ["DIALOGUE_VOTE_OPEN", "ANALYSIS_OPEN"].includes(state.phase) &&
    state.mode === "ONLINE";
  if (open && !state.own_answer) {
    view.replaceChildren();
    const vote = state.phase === "DIALOGUE_VOTE_OPEN";
    add(
      "p",
      "eyebrow",
      (vote ? "RÉPLIQUE" : "ANALYSE") + " / 0" + state.round_id,
    );
    add("h2", "", state.question);
    add(
      "span",
      "tag",
      vote
        ? "VOTRE CHOIX FAIT AVANCER L'HISTOIRE"
        : state.round_id === 4
          ? "DIAGNOSTIC FINAL / +2 POINTS"
          : "VOTRE ANALYSE / +1 POINT",
    );
    for (const option of state.options) {
      const b = add("button", "option");
      b.setAttribute("aria-pressed", String(selected === option.id));
      b.append(el("span", "key", option.id), el("span", "label", option.text));
      b.disabled = pending;
      b.addEventListener("click", () => {
        selected = option.id;
        render();
      });
    }
    const lock = add(
      "button",
      "primary",
      pending
        ? "ENVOI EN COURS…"
        : "VERROUILLER " + (vote ? "LE CHOIX" : "L'ANALYSE") + "   ↗",
    );
    lock.disabled =
      !selected || pending || socket?.readyState !== WebSocket.OPEN;
    lock.onclick = () => {
      if (!selected || pending || socket.readyState !== WebSocket.OPEN) return;
      pending = true;
      socket.send(
        JSON.stringify({
          type: "submit",
          session_id: sessionId,
          round_id: state.round_id,
          phase_id: state.phase_id,
          answer: selected,
        }),
      );
      render();
    };
    return;
  }
  if (open) {
    waiting(
      "Choix verrouillé.",
      "Votre réponse est enregistrée. L'animateur dévoilera toutes les réponses ensemble.",
    );
    return;
  }
  if (state.phase === "ANALYSIS_RESULTS") {
    view.replaceChildren();
    add("p", "eyebrow", "ANALYSE / RÉSULTAT");
    add("h1", "", state.award ? "Signal décodé." : "À observer encore.");
    add("div", "result", "+" + (state.award || 0));
    add(
      "p",
      "",
      "POINT" +
        (state.award > 1 ? "S" : "") +
        " · Écoutez l'explication de l'animateur.",
    );
    add("p", "hint", "REGARDEZ L'ÉCRAN PRINCIPAL");
    return;
  }
  if (["FINAL_SCOREBOARD", "SESSION_COMPLETE"].includes(state.phase)) {
    view.replaceChildren();
    add("p", "eyebrow", "SESSION / COMPLÈTE");
    add("h1", "", "La conversation est décodée.");
    [0, 1, 2, 3]
      .sort((a, b) => state.scores[b] - state.scores[a])
      .forEach((i) => {
        const rank = 1 + state.scores.filter((s) => s > state.scores[i]).length;
        const row = add("div", "rank");
        row.style.color = state.colors[i];
        row.append(
          el("span", "", String(rank).padStart(2, "0")),
          el("span", "", state.names[i]),
          el("b", "", state.scores[i] + " PTS"),
        );
      });
    add("p", "hint", "MERCI D'AVOIR PARTICIPÉ.");
    return;
  }
  if (state.mode === "MANUAL") {
    waiting(
      "Le clavier prend le relais.",
      "Annoncez votre réponse à l'animateur. Votre téléphone est en attente.",
    );
    return;
  }
  if (state.phase === "TIE_BREAK") {
    waiting(
      "Égalité détectée.",
      "L'animateur choisit le chemin parmi les options ex æquo.",
    );
    return;
  }
  if (state.path && state.phase === "DIALOGUE_RESULTS") {
    waiting(
      "Chemin " + state.path + " retenu.",
      "La majorité a choisi. La simulation continue.",
    );
    return;
  }
  waiting(
    state.phase === "TITLE" ? "Vous êtes connecté." : "Simulation en cours…",
    state.phase === "TITLE"
      ? "En attente du lancement par l'animateur."
      : "La conversation se poursuit sur le projecteur.",
  );
}
join();
