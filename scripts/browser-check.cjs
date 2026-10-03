/* Real browser controllers + a real WebSocket presenter. No app engine in JS. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("@playwright/test");
const root = path.resolve(__dirname, "..");
const base = process.env.PALO_ALTO_SERVER_URL || "http://127.0.0.1:8018";
const data = JSON.parse(
  fs.readFileSync(path.join(root, "data/scenarios.json"), "utf8"),
);
const names = ["Équipe Cyan", "Équipe Magenta", "Équipe Verte", "Équipe Ambre"];
const colors = ["#33E6FF", "#FF4FD8", "#5CFF85", "#FFC857"];
async function api(p, body) {
  const r = await fetch(base + p, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw Error(await r.text());
  return r.json();
}
async function run() {
  const created = await api("/api/sessions", { names, colors });
  const ws = new WebSocket(
    base.replace(/^http/, "ws") + "/ws/presenter/" + created.room_code,
  );
  const messages = [];
  let ready = false;
  ws.addEventListener("message", (e) => {
    const m = JSON.parse(e.data);
    messages.push(m);
    if (m.type === "snapshot") ready = true;
  });
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", () => {
      ws.send(JSON.stringify({ token: created.presenter_token }));
      resolve();
    });
    ws.addEventListener("error", reject);
  });
  const wait = async (predicate) => {
    const deadline = Date.now() + 10000;
    while (Date.now() < deadline) {
      if (predicate()) return;
      await new Promise((r) => setTimeout(r, 30));
    }
    throw Error("Browser test timeout");
  };
  await wait(() => ready);
  const browser = await chromium.launch({ headless: true });
  const contexts = [],
    pages = [],
    errors = [];
  let revision = 0;
  const state = {
    type: "state",
    round_id: 1,
    phase_id: "browser-lobby",
    revision: revision++,
    phase: "TITLE",
    mode: "ONLINE",
    scores: [0, 0, 0, 0],
    awards: [0, 0, 0, 0],
    options: [],
    question: "",
    path: null,
    results: {},
    title: "Les signaux faibles",
  };
  const publish = async (patch) => {
    Object.assign(state, patch, { revision: revision++ });
    ws.send(JSON.stringify(state));
    await wait(() =>
      messages.some(
        (m) =>
          m.type === "snapshot" &&
          m.phase_id === state.phase_id &&
          m.revision === state.revision,
      ),
    );
  };
  const shots = path.join(root, "docs/screenshots");
  fs.mkdirSync(shots, { recursive: true });
  try {
    await publish({});
    for (let team = 0; team < 4; team++) {
      const context = await browser.newContext({
        viewport:
          team === 0
            ? { width: 360, height: 640 }
            : team === 1
              ? { width: 390, height: 844 }
              : { width: 430, height: 932 },
      });
      contexts.push(context);
      const page = await context.newPage();
      pages.push(page);
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("console", (msg) => {
        if (msg.type() === "error") errors.push(msg.text());
      });
      await page.goto(base + "/join?room=" + created.room_code);
      await page.getByRole("button", { name: "REJOINDRE LA SESSION" }).click();
      await page.getByRole("button", { name: new RegExp(names[team]) }).click();
      await page
        .getByRole("heading", { name: "Vous êtes connecté." })
        .waitFor();
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      );
      assert(!overflow, "Horizontal overflow");
    }
    await pages[0].screenshot({
      path: path.join(shots, "16-mobile-waiting.png"),
      fullPage: true,
    });
    await publish({
      phase: "DIALOGUE_VOTE_OPEN",
      phase_id: "browser-vote",
      question: data.rounds[0].prompt,
      options: Object.entries(data.rounds[0].choices).map(([id, c]) => ({
        id,
        text: c.text,
      })),
    });
    for (let team = 0; team < 4; team++) {
      const page = pages[team];
      await page
        .getByRole("heading", { name: data.rounds[0].prompt })
        .waitFor();
      const lock = page.getByRole("button", { name: "VERROUILLER LE CHOIX" });
      assert(await lock.isDisabled());
      await page
        .locator(".option")
        .nth(team === 3 ? 2 : 0)
        .click();
      assert((await page.locator(".option[aria-pressed=true]").count()) === 1);
      if (team === 0)
        await page.screenshot({
          path: path.join(shots, "17-mobile-vote.png"),
          fullPage: true,
        });
      await lock.click();
      await page.getByRole("heading", { name: "Choix verrouillé." }).waitFor();
    }
    await wait(() =>
      messages.some(
        (m) => m.type === "ALL_TEAMS_LOCKED" && m.phase_id === "browser-vote",
      ),
    );
    assert.deepEqual(
      messages.filter((m) => m.type === "snapshot").at(-1).submissions,
      { 0: "A", 1: "A", 2: "A", 3: "C" },
    );
    // Reopen, then submit another choice using the exact mobile UI.
    ws.send(
      JSON.stringify({ type: "reopen", team: 0, phase_id: "browser-vote" }),
    );
    await pages[0]
      .getByRole("heading", { name: data.rounds[0].prompt })
      .waitFor();
    await pages[0].locator(".option").nth(1).click();
    await pages[0]
      .getByRole("button", { name: "VERROUILLER LE CHOIX" })
      .click();
    await pages[0]
      .getByRole("heading", { name: "Choix verrouillé." })
      .waitFor();
    await pages[0].reload(); // Same browser token restores the reservation and locked answer.
    await pages[0]
      .getByRole("button", { name: "REJOINDRE LA SESSION" })
      .click();
    await pages[0].getByRole("button", { name: new RegExp(names[0]) }).click();
    await pages[0]
      .getByRole("heading", { name: "Choix verrouillé." })
      .waitFor();
    const analysis = data.rounds[0].choices.A.analysis;
    await publish({
      phase: "ANALYSIS_OPEN",
      phase_id: "browser-analysis",
      question: analysis.question,
      options: analysis.answers.map((text, i) => ({ id: String(i + 1), text })),
    });
    for (let team = 0; team < 4; team++) {
      await pages[team]
        .getByRole("heading", { name: analysis.question })
        .waitFor();
      await pages[team]
        .locator(".option")
        .nth(team === 3 ? 1 : 0)
        .click();
      await pages[team]
        .getByRole("button", { name: "VERROUILLER L'ANALYSE" })
        .click();
      await pages[team]
        .getByRole("heading", { name: "Choix verrouillé." })
        .waitFor();
    }
    await wait(() =>
      messages.some(
        (m) =>
          m.type === "ALL_TEAMS_LOCKED" && m.phase_id === "browser-analysis",
      ),
    );
    await publish({
      phase: "ANALYSIS_RESULTS",
      phase_id: "browser-result",
      question: "",
      options: [],
      scores: [1, 1, 1, 0],
      awards: [1, 1, 1, 0],
      results: { 0: "1", 1: "1", 2: "1", 3: "2" },
    });
    await pages[0].getByRole("heading", { name: "Signal décodé." }).waitFor();
    await pages[3]
      .getByRole("heading", { name: "À observer encore." })
      .waitFor();
    await pages[0].screenshot({
      path: path.join(shots, "18-mobile-result.png"),
      fullPage: true,
    });
    await publish({
      phase: "FINAL_SCOREBOARD",
      phase_id: "browser-final",
      scores: [5, 4, 4, 0],
      awards: [0, 0, 0, 0],
    });
    for (const page of pages) {
      await page
        .getByRole("heading", { name: "La conversation est décodée." })
        .waitFor();
      assert((await page.locator(".rank").count()) === 4);
    }
    assert(errors.length === 0, JSON.stringify(errors));
    console.log(
      "PASS: four real browser controllers, 360/390/430px, selection/lock/reopen/reload, analysis, final tie, no overflow, no JS/console errors",
    );
  } finally {
    ws.send(JSON.stringify({ type: "end" }));
    ws.close();
    for (const context of contexts) await context.close();
    await browser.close();
  }
}
run().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
