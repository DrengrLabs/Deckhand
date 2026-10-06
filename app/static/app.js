// ---------- small helpers ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

async function api(path, opts) {
  const res = await fetch(path, opts);
  const ct = res.headers.get("content-type") || "";
  if (!res.ok) {
    // Prefer a clean {"error": "..."} message from the backend; fall back
    // to the raw body only if the server returned something unexpected
    // (e.g. a framework error page) that wasn't JSON.
    if (ct.includes("application/json")) {
      const body = await res.json().catch(() => null);
      throw new Error((body && body.error) || `Request failed (${res.status})`);
    }
    const text = await res.text();
    throw new Error(`Request failed (${res.status}): ${text.slice(0, 200)}`);
  }
  return ct.includes("application/json") ? res.json() : res.text();
}

function todayStr() {
  // Local calendar date, not UTC -- toISOString() would roll over to
  // tomorrow in the evening for anyone west of UTC (e.g. generating
  // tomorrow's paperwork at 23:50 the night before should still default
  // to showing today unless you deliberately pick tomorrow yourself).
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

// A tiny modal stack: each entry is a render function that (re)populates
// #modalBox and wires up its own event listeners. Pushing a new modal (e.g.
// the signature pad opened from inside the "add TRA" form) stacks on top;
// popping it re-runs the previous render function so that form reappears
// with its in-progress state intact, instead of the whole thing closing.
let modalStack = [];
// Optional teardown for the modal currently showing (e.g. releasing the
// Topaz pad); runs whenever that modal is popped or everything closes.
let modalCleanup = null;
function setModalCleanup(fn) {
  modalCleanup = fn;
}
function runModalCleanup() {
  const fn = modalCleanup;
  modalCleanup = null;
  if (fn) Promise.resolve(fn()).catch(() => {});
}

function pushModal(renderFn) {
  runModalCleanup();
  modalStack.push(renderFn);
  renderFn();
  $("#modalBackdrop").hidden = false;
}
function popModal() {
  runModalCleanup();
  modalStack.pop();
  if (modalStack.length === 0) {
    $("#modalBackdrop").hidden = true;
    $("#modalBox").innerHTML = "";
  } else {
    modalStack[modalStack.length - 1]();
  }
}
function closeAllModals() {
  runModalCleanup();
  modalStack = [];
  $("#modalBackdrop").hidden = true;
  $("#modalBox").innerHTML = "";
}
// Back-compat aliases used by simple (non-stacked) call sites below.
function showModal(html) {
  runModalCleanup();
  modalStack = [() => ($("#modalBox").innerHTML = html)];
  $("#modalBox").innerHTML = html;
  $("#modalBackdrop").hidden = false;
}
function hideModal() {
  closeAllModals();
}
$("#modalBackdrop").addEventListener("click", (e) => {
  if (e.target.id === "modalBackdrop") hideModal();
});

// ---------- tabs ----------
$$(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".tab-btn").forEach((b) => b.classList.remove("active"));
    $$(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "signatures") loadSignatures();
    if (btn.dataset.tab === "history") loadHistory();
    if (btn.dataset.tab === "timesheets") loadTimesheets();
  });
});

function switchToTab(tabName) {
  $$(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tabName));
  $$(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${tabName}`));
}

// ---------- hitch setup ----------
let hitch = null;

// The six standard crew rows every hitch starts with. The Day Shift
// Supervisor is the TRA/TBT approver and the Night Shift Supervisor the
// 2nd approver -- their name/position fill those blocks on every document.
const CREW_SLOTS = [
  { slot: "day_supervisor", label: "Day Shift Supervisor", hint: "e.g. day shift supervisor", position: "Supervisor", official: "ROV Supervisor", shift: "day" },
  { slot: "day_spt", label: "Day Shift SPT", hint: "e.g. day shift SPT", position: "SPT", official: "ROV Senior Pilot/Technician", shift: "day" },
  { slot: "day_tech", label: "Day Shift Tech", hint: "e.g. day shift Tech", position: "Tech", official: "ROV Pilot/Technician I", shift: "day" },
  { slot: "night_supervisor", label: "Night Shift Supervisor", hint: "e.g. night shift supervisor", position: "Supervisor", official: "ROV Supervisor", shift: "night" },
  { slot: "night_spt", label: "Night Shift SPT", hint: "e.g. night shift SPT", position: "SPT", official: "ROV Senior Pilot/Technician", shift: "night" },
  { slot: "night_tech", label: "Night Shift Tech", hint: "e.g. night shift Tech", position: "Tech", official: "ROV Pilot/Technician I", shift: "night" },
];

// Official job titles (as on the timesheet). The short "Position" stays on
// TRAs/TBTs; these go on timesheets.
const OFFICIAL_POSITIONS = [
  "OCM", "NOCM", "ROV Supervisor", "ROV Senior Pilot/Technician",
  "ROV Pilot/Technician I", "ROV Pilot/Technician II",
];

// slotDef: one of CREW_SLOTS for a standard row (can be cleared, not
// removed), or null for an extra crew member added with "+ Add".
// extra: { official_position, shift, contractor } as saved.
function addCrewRow(name = "", position = "", slotDef = null, extra = {}) {
  const tbody = $("#crewTable tbody");
  const tr = document.createElement("tr");
  if (slotDef) tr.dataset.slot = slotDef.slot;
  const official = extra.official_position || (slotDef ? slotDef.official : "");
  const shift = slotDef ? slotDef.shift : (extra.shift || "day");
  const officialOptions = ['<option value="">(choose)</option>']
    .concat(OFFICIAL_POSITIONS.map((p) => `<option${p === official ? " selected" : ""}>${escapeAttr(p)}</option>`))
    .join("");
  tr.innerHTML = `
    <td><input class="crew-name" value="${escapeAttr(name)}" placeholder="${escapeAttr(slotDef ? slotDef.hint : "e.g. crew member name")}"></td>
    <td><input class="crew-position" value="${escapeAttr(position)}" placeholder="e.g. Tech"></td>
    <td><select class="crew-official">${officialOptions}</select></td>
    <td><select class="crew-shift" ${slotDef ? 'disabled title="Set by the row (day/night shift)"' : ""}>
      <option value="day"${shift === "day" ? " selected" : ""}>Day</option>
      <option value="night"${shift === "night" ? " selected" : ""}>Night</option></select></td>
    <td class="crew-contractor-cell"><input type="checkbox" class="crew-contractor" ${extra.contractor ? "checked" : ""} title="Tick for a contractor - their timesheet is filed under 2 - CONTRACTOR TIMESHEETS"></td>
    <td><button type="button" class="secondary remove-row">${slotDef ? "Clear" : "Remove"}</button></td>`;
  tr.querySelector(".remove-row").addEventListener("click", () => {
    if (slotDef) {
      tr.querySelector(".crew-name").value = "";
      tr.querySelector(".crew-position").value = slotDef.position;
      tr.querySelector(".crew-official").value = slotDef.official;
      tr.querySelector(".crew-contractor").checked = false;
    } else {
      tr.remove();
    }
  });
  tbody.appendChild(tr);
}

// Full HTML-escaper, safe for both text content and quoted attribute
// values (used everywhere a crew name, position, task note, etc. gets
// interpolated into an innerHTML template string). Escaping more than an
// attribute strictly needs is always safe -- the reverse isn't.
function escapeAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function getCrewFromForm() {
  return $$("#crewTable tbody tr").map((tr) => {
    const c = {
      name: tr.querySelector(".crew-name").value.trim(),
      position: tr.querySelector(".crew-position").value.trim(),
      official_position: tr.querySelector(".crew-official").value,
      shift: tr.querySelector(".crew-shift").value,
      contractor: tr.querySelector(".crew-contractor").checked,
    };
    if (tr.dataset.slot) c.slot = tr.dataset.slot;
    return c;
  }).filter((c) => c.name);
}

// Every plain-text Hitch Setup field (form input name == stored key).
// (The approver name/position fields are derived from the crew roster.)
const HITCH_TEXT_FIELDS = [
  "name", "project", "location", "sub_location", "approver", "responsible_person", "equipment",
  "output_folder", "client", "ts_output_folder",
];

async function loadHitch() {
  hitch = await api("/api/hitch");
  const form = $("#hitchForm");
  for (const key of HITCH_TEXT_FIELDS) {
    form.elements[key].value = hitch[key] || "";
  }
  $("#crewTable tbody").innerHTML = "";
  const crew = hitch.crew || [];
  const hasSlots = crew.some((c) => c.slot);
  const usedLegacyNames = new Set();
  for (const def of CREW_SLOTS) {
    let entry = crew.find((c) => c.slot === def.slot);
    // Hitches saved before the standard slots existed: carry the old
    // approver / 2nd approver over into the two supervisor slots.
    if (!entry && !hasSlots) {
      const legacy = def.slot === "day_supervisor" ? [hitch.approver_name, hitch.approver_position]
        : def.slot === "night_supervisor" ? [hitch.approver2_name, hitch.approver2_position] : null;
      if (legacy && legacy[0]) {
        entry = { name: legacy[0], position: legacy[1] || def.position };
        usedLegacyNames.add(legacy[0]);
      }
    }
    addCrewRow(entry ? entry.name : "", entry ? entry.position : def.position, def, entry || {});
  }
  crew.filter((c) => !c.slot && !usedLegacyNames.has(c.name)).forEach((c) => addCrewRow(c.name, c.position, null, c));
}

async function loadHitchSwitcher() {
  const res = await api("/api/hitches");
  const select = $("#hitchSelect");
  select.innerHTML = "";
  if (res.hitches.length === 0) {
    const opt = document.createElement("option");
    opt.textContent = "No hitch yet";
    select.appendChild(opt);
    return;
  }
  res.hitches.forEach((h) => {
    const opt = document.createElement("option");
    opt.value = h.id;
    opt.textContent = h.name;
    if (h.id === res.active) opt.selected = true;
    select.appendChild(opt);
  });
  renderHitchManageList(res.hitches, res.active);
}

function renderHitchManageList(hitches, activeId) {
  const list = $("#hitchManageList");
  const onlyOne = hitches.length <= 1;
  list.innerHTML = hitches.map((h) => `
    <div class="hitch-manage-row">
      <span>${escapeAttr(h.name)}${h.id === activeId ? ' <span class="badge active">active</span>' : ""}</span>
      <button type="button" class="secondary remove-hitch" data-id="${escapeAttr(h.id)}" data-name="${escapeAttr(h.name)}"
        ${onlyOne ? 'disabled title="The only hitch can\'t be removed -- create another one first."' : ""}>Remove</button>
    </div>`).join("");
  $$(".remove-hitch", list).forEach((btn) => {
    btn.addEventListener("click", () => confirmRemoveHitch(btn.dataset.id, btn.dataset.name, btn.dataset.id === activeId));
  });
}

function confirmRemoveHitch(id, name, isActive) {
  showModal(`
    <h3>Remove hitch &ldquo;${escapeAttr(name)}&rdquo;?</h3>
    <p>This removes its setup, crew roster and History from the app.</p>
    <p class="hint">PDFs already saved to its output folder are not touched, and the signature library is kept.
    The removed data is moved to <code>app_data\\removed_hitches</code> rather than deleted, in case you ever need it back.</p>
    ${isActive ? '<p class="hint warn">This is the hitch you currently have open &mdash; the app will switch to another one.</p>' : ""}
    <div class="row">
      <button type="button" id="confirmRemoveHitch" class="danger">Remove</button>
      <button type="button" id="cancelRemoveHitch" class="secondary">Cancel</button>
    </div>`);
  $("#cancelRemoveHitch").addEventListener("click", hideModal);
  $("#confirmRemoveHitch").addEventListener("click", async () => {
    try {
      await api(`/api/hitches/${encodeURIComponent(id)}`, { method: "DELETE" });
    } catch (e) {
      hideModal();
      alert("Couldn't remove that hitch: " + e.message);
      return;
    }
    hideModal();
    await loadHitchSwitcher();
    await reloadAllForActiveHitch();
  });
}

$("#hitchSelect").addEventListener("change", async (e) => {
  await api(`/api/hitches/${encodeURIComponent(e.target.value)}/activate`, { method: "POST" });
  await reloadAllForActiveHitch();
});

$("#newHitchBtn").addEventListener("click", async () => {
  const name = prompt("Name for the new hitch (e.g. project + location):");
  if (!name || !name.trim()) return;
  await api("/api/hitches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name.trim() }),
  });
  await loadHitchSwitcher();
  await reloadAllForActiveHitch();
  switchToTab("setup");
});

async function reloadAllForActiveHitch() {
  await loadHitch();
  await loadTraList();
  if ($("#tab-history").classList.contains("active")) await loadHistory();
  if ($("#tab-signatures").classList.contains("active")) await loadSignatures();
}

$("#addCrewRow").addEventListener("click", () => addCrewRow());

// "Browse..." buttons: HSE output folder and timesheet output folder.
function wireBrowse(btnSel, inputSel) {
  $(btnSel).addEventListener("click", async () => {
    const input = $(inputSel);
    const btn = $(btnSel);
    btn.disabled = true;
    btn.textContent = "Opening...";
    try {
      const res = await api("/api/browse-folder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initial: input.value.trim() }),
      });
      if (res.folder) input.value = res.folder;
    } catch (e) {
      alert("Couldn't open the folder browser: " + e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Browse…";
    }
  });
}
wireBrowse("#browseFolderBtn", "#outputFolderInput");
wireBrowse("#browseTsFolderBtn", "#tsFolderInput");

$("#hitchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = { crew: getCrewFromForm() };
  for (const key of HITCH_TEXT_FIELDS) data[key] = form.elements[key].value;
  // Approver = Day Shift Supervisor, 2nd approver = Night Shift Supervisor.
  const day = data.crew.find((c) => c.slot === "day_supervisor");
  const night = data.crew.find((c) => c.slot === "night_supervisor");
  data.approver_name = day ? day.name : "";
  data.approver_position = day ? day.position : "";
  data.approver2_name = night ? night.name : "";
  data.approver2_position = night ? night.position : "";
  hitch = await api("/api/hitch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  await loadHitchSwitcher();
  $("#hitchSaveStatus").textContent = "Saved.";
  setTimeout(() => ($("#hitchSaveStatus").textContent = ""), 2000);
});

// ---------- templates catalog ----------
let templateCatalog = null;
async function loadTemplateCatalog() {
  if (!templateCatalog) templateCatalog = await api("/api/templates");
  return templateCatalog;
}

// ---------- signatures ----------
async function getSignaturesIndex() {
  return api("/api/signatures");
}

function openSignatureModal(personName, onSaved) {
  $("#modalBox").innerHTML = `
    <h3>Signature &mdash; ${escapeAttr(personName)}</h3>
    <p class="hint" id="sigHint">Draw in the box with the mouse, touchscreen or stylus.</p>
    <canvas id="sigCanvas" width="560" height="200"></canvas>
    <div class="row">
      <button type="button" id="sigPad" hidden>Sign on Topaz Pad</button>
      <button type="button" id="sigClear" class="secondary">Clear</button>
      <button type="button" id="sigSave">Save Signature</button>
      <button type="button" id="sigCancel" class="secondary">Cancel</button>
    </div>
  `;
  const canvas = $("#sigCanvas");
  const ctx = canvas.getContext("2d");
  ctx.lineWidth = 2.5;
  ctx.lineCap = "round";
  ctx.strokeStyle = "#0b1f6b";
  let drawing = false;
  let last = null;
  let drewSomething = false;
  let pad = null;   // active Topaz capture session, if any

  async function stopPad() {
    if (pad) {
      const p = pad;
      pad = null;
      await p.stop();
    }
  }
  // Release the pad however this window closes (Cancel, Save, backdrop).
  setModalCleanup(stopPad);

  // Offer the Topaz pad only when the SigWeb service is on this computer.
  topazAvailable().then((ok) => {
    if (!ok || !$("#sigPad")) return;
    $("#sigPad").hidden = false;
    $("#sigHint").textContent = "Click \"Sign on Topaz Pad\" and sign on the pad, or draw in the box with the mouse / touchscreen.";
  });

  $("#sigPad").addEventListener("click", async () => {
    const btn = $("#sigPad");
    btn.disabled = true;
    try {
      await stopPad();
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      pad = await topazStart(canvas);
      drewSomething = false;
      btn.textContent = "Pad ready — sign now";
      $("#sigHint").textContent = "Sign on the Topaz pad. The signature appears here as you sign. Click Save Signature when done.";
    } catch (e) {
      pad = null;
      btn.disabled = false;
      alert("Couldn't start the Topaz pad: " + e.message);
    }
  });

  function pos(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  }
  canvas.addEventListener("pointerdown", (e) => {
    if (pad) return;   // pad session owns the box; ignore mouse input
    drawing = true;
    drewSomething = true;
    last = pos(e);
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!drawing) return;
    const p = pos(e);
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last = p;
  });
  ["pointerup", "pointerleave", "pointercancel"].forEach((ev) =>
    canvas.addEventListener(ev, () => (drawing = false))
  );

  $("#sigClear").addEventListener("click", async () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drewSomething = false;
    if (pad) await pad.clear().catch(() => {});
  });
  $("#sigCancel").addEventListener("click", popModal);
  $("#sigSave").addEventListener("click", async () => {
    if (pad) {
      try {
        await pad.finish();
        pad = null;
      } catch (e) {
        alert(e.message);
        return;
      }
    } else if (!drewSomething) {
      alert("Nothing has been signed yet.");
      return;
    }
    const dataUrl = canvas.toDataURL("image/png");
    await api(`/api/signatures/${encodeURIComponent(personName)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: dataUrl }),
    });
    popModal();
    if (onSaved) onSaved();
  });
}

async function loadSignatures() {
  const index = await getSignaturesIndex();
  const names = new Set(Object.keys(index));
  (hitch?.crew || []).forEach((c) => names.add(c.name));
  if (hitch?.approver_name) names.add(hitch.approver_name);

  const list = $("#sigList");
  list.innerHTML = "";
  if (names.size === 0) {
    list.innerHTML = '<p class="hint">Add crew in Hitch Setup first.</p>';
    return;
  }
  [...names].sort().forEach((name) => {
    const has = !!index[name];
    const card = document.createElement("div");
    card.className = "sig-card";
    card.innerHTML = `
      <div class="name">${escapeAttr(name)}</div>
      ${has ? `<img src="/api/signatures/${encodeURIComponent(name)}/image?t=${Date.now()}">` : '<div class="sig-empty">No signature</div>'}
      <div class="actions">
        <button type="button" class="draw-btn">${has ? "Re-capture" : "Capture"}</button>
        ${has ? '<button type="button" class="secondary clear-btn">Clear</button>' : ""}
      </div>`;
    card.querySelector(".draw-btn").addEventListener("click", () => pushModal(() => openSignatureModal(name, loadSignatures)));
    const clearBtn = card.querySelector(".clear-btn");
    if (clearBtn) clearBtn.addEventListener("click", async () => {
      await api(`/api/signatures/${encodeURIComponent(name)}`, { method: "DELETE" });
      loadSignatures();
    });
    list.appendChild(card);
  });
}

// ---------- today / daily TRA generation ----------
$("#dateInput").value = todayStr();
$("#dateInput").addEventListener("change", loadTraList);

async function loadTraList() {
  const date = $("#dateInput").value;
  const day = await api(`/api/day/${date}`);
  const catalog = await loadTemplateCatalog();
  const container = $("#traList");
  container.innerHTML = "";
  if (day.tras.length === 0) {
    container.innerHTML = '<p class="hint">No TRAs/TBTs generated yet for this date. Click "+ Add TRA" or "+ Add TBT" to start.</p>';
    return;
  }
  day.tras.forEach((t) => {
    const title = catalog[t.tra_key]?.title || t.tra_key;
    const card = document.createElement("div");
    card.className = "tra-card";
    const signerRows = t.signers.map((s) =>
      `<div class="signer-row"><span>${escapeAttr(s.name)} (${escapeAttr(s.position)})</span><span class="badge ${s.signed ? "signed" : "unsigned"}">${s.signed ? "Signature on file" : "Needs signature"}</span></div>`
    ).join("");
    const leader = catalog[t.tra_key]?.category === "TBT" ? "TBT Leader" : "Approver";
    const approver2Row = t.approver2_name
      ? `<div class="signer-row"><span>2nd ${leader}: ${escapeAttr(t.approver2_name)}</span><span class="badge ${t.approver2_signed ? "signed" : "unsigned"}">${t.approver2_signed ? "Signature on file" : "Needs signature"}</span></div>`
      : "";
    card.innerHTML = `
      <h3>${escapeAttr(t.tra_key)} &mdash; ${escapeAttr(title)}</h3>
      <div class="meta">Generated ${escapeAttr(t.generated_at)} &middot; ${escapeAttr(t.file)}</div>
      <div class="signer-row"><span>${leader}: ${escapeAttr(t.approver_name) || "(none)"}</span><span class="badge ${t.approver_signed ? "signed" : "unsigned"}">${t.approver_signed ? "Signature on file" : "Needs signature"}</span></div>
      ${approver2Row}
      ${signerRows}
      <div class="row">
        <button type="button" class="view-btn">View</button>
        <button type="button" class="edit-btn secondary">Edit / Regenerate</button>
        <button type="button" class="remove-btn danger">Remove</button>
      </div>`;
    card.querySelector(".view-btn").addEventListener("click", () => {
      api(`/api/day/${date}/tra/${encodeURIComponent(t.tra_key)}/open`, { method: "POST" })
        .catch((e) => alert(e.message));
    });
    card.querySelector(".edit-btn").addEventListener("click", () => pushModal(() => openGenerateConfig(t.tra_key, t)));
    card.querySelector(".remove-btn").addEventListener("click", async () => {
      await api(`/api/day/${date}/tra/${encodeURIComponent(t.tra_key)}`, { method: "DELETE" });
      loadTraList();
    });
    container.appendChild(card);
  });
}

async function loadHistory() {
  const days = await api("/api/days");
  const container = $("#historyList");
  container.innerHTML = "";
  if (days.length === 0) {
    container.innerHTML = '<p class="hint">Nothing generated yet. Once you create TRAs/TBTs on the Today tab, every date shows up here.</p>';
    return;
  }
  days.forEach((d) => {
    const card = document.createElement("div");
    card.className = "tra-card";
    card.innerHTML = `
      <div class="row" style="justify-content:space-between; margin:0;">
        <div>
          <h3 style="margin-bottom:4px">${d.date}</h3>
          <div class="meta">${d.count} document${d.count === 1 ? "" : "s"} generated &middot; <span class="badge ${d.all_signed ? "signed" : "unsigned"}">${d.all_signed ? "All signed" : "Some unsigned"}</span></div>
        </div>
        <button type="button" class="view-day-btn">View</button>
      </div>`;
    card.querySelector(".view-day-btn").addEventListener("click", () => {
      $("#dateInput").value = d.date;
      switchToTab("today");
      loadTraList();
    });
    container.appendChild(card);
  });
}

async function openAddPicker(category) {
  const catalog = await loadTemplateCatalog();
  const items = Object.values(catalog)
    .filter((it) => it.category === category)
    .sort((a, b) => a.key.localeCompare(b.key));
  pushModal(() => {
    $("#modalBox").innerHTML = `
      <h3>Add a ${category}</h3>
      <input type="text" id="traSearch" placeholder="Search ${category} name..." style="width:100%;margin-bottom:8px;">
      <div class="tra-pick-list" id="traPickList"></div>
    `;
    const listEl = $("#traPickList");
    function render(filter) {
      listEl.innerHTML = "";
      const filtered = items.filter((it) => !filter || it.key.toLowerCase().includes(filter) || it.title.toLowerCase().includes(filter));
      if (filtered.length === 0) {
        listEl.innerHTML = `<p class="hint">No ${category} templates found. Finished ${category} template PDFs go in the DOUS Deckhand\\templates\\${category} folder.</p>`;
        return;
      }
      filtered.forEach((it) => {
        const div = document.createElement("div");
        div.className = "tra-pick-item";
        div.innerHTML = `${it.key}${it.altered ? ' <span class="badge unsigned">&#9888; altered</span>' : ""}`;
        div.addEventListener("click", () => {
          popModal();
          pushModal(() => openGenerateConfig(it.key, null));
        });
        listEl.appendChild(div);
      });
    }
    render("");
    $("#traSearch").addEventListener("input", (e) => render(e.target.value.toLowerCase()));
    $("#traSearch").focus();
  });
}

$("#addTraBtn").addEventListener("click", () => openAddPicker("TRA"));
$("#addTbtBtn").addEventListener("click", () => openAddPicker("TBT"));

async function openGenerateConfig(traKey, existing, opts = {}) {
  // preferHitch is true for a "fresh" open (picker, Edit/Regenerate) so a
  // Hitch Setup change shows up right away. It must be false for the
  // internal re-render that happens after capturing a signature mid-session
  // (see openSigFor below) -- otherwise whatever the user just typed into
  // the approver fields gets silently discarded back to the hitch default
  // the moment they capture anyone's signature.
  const preferHitch = opts.preferHitch !== false;
  const catalog = await loadTemplateCatalog();
  const info = catalog[traKey];
  if (!info) {
    $("#modalBox").innerHTML = `
      <h3>Template not found</h3>
      <p class="hint">"${escapeAttr(traKey)}" no longer matches a file in the DOUS Deckhand\\templates folders (it may have been renamed or removed). This historical record is unaffected, but it can't be edited/regenerated under this name.</p>
      <div class="row"><button type="button" id="cancelBtn">Close</button></div>`;
    $("#cancelBtn").addEventListener("click", popModal);
    return;
  }
  if (info.altered) {
    $("#modalBox").innerHTML = `
      <h3>&#9888; Template may have been altered</h3>
      <p class="hint warn">"${traKey}" no longer matches its original blank content (someone may have edited or signed it directly in Acrobat). Generating from it is blocked until the original blank file is restored in the DOUS Deckhand\\templates\\${info.category} folder.</p>
      <div class="row"><button type="button" id="cancelBtn">Close</button></div>`;
    $("#cancelBtn").addEventListener("click", popModal);
    return;
  }
  const sigIndex = await getSignaturesIndex();
  const crewPool = hitch?.crew || [];
  const rowLimit = info.num_crew_rows;
  const defaultPool = info.num_crew_rows > 0 ? crewPool.slice(0, rowLimit) : [];
  const selectedNames = new Set((existing?.crew || defaultPool).map((c) => c.name));

  const crewRowsHtml = crewPool.map((c) => {
    const checked = selectedNames.has(c.name) ? "checked" : "";
    const has = !!sigIndex[c.name];
    return `<div class="crew-check-row">
      <input type="checkbox" class="crew-pick" value="${escapeAttr(c.name)}" ${checked}>
      <span style="flex:1">${escapeAttr(c.name)} (${escapeAttr(c.position)})</span>
      <span class="badge ${has ? "signed" : "unsigned"}">${has ? "Signature on file" : "No signature"}</span>
      <button type="button" class="secondary sig-btn" data-name="${escapeAttr(c.name)}">${has ? "Re-capture" : "Capture"}</button>
    </div>`;
  }).join("") || '<p class="hint">No crew in hitch setup yet.</p>';

  // On a fresh open, Hitch Setup is the source of truth for the approver
  // so a change there shows up right away. On the internal re-render after
  // a mid-session signature capture, `existing` is this form's own
  // just-typed snapshot and must win outright -- see preferHitch above.
  const approverName = preferHitch ? (hitch?.approver_name || existing?.approver_name || "") : (existing?.approver_name || "");
  const approverPosition = preferHitch ? (hitch?.approver_position || existing?.approver_position || "") : (existing?.approver_position || "");
  const approver2Name = preferHitch ? (hitch?.approver2_name || existing?.approver2_name || "") : (existing?.approver2_name || "");
  const approver2Position = preferHitch ? (hitch?.approver2_position || existing?.approver2_position || "") : (existing?.approver2_position || "");
  const hasApproverSig = !!sigIndex[approverName];
  const hasApprover2Sig = !!sigIndex[approver2Name];
  // On a TBT the sign-off block is the "TBT Leader" rather than the
  // "DOUS Deckhandroval" approver -- same hitch defaults, different wording.
  const leader = info.category === "TBT" ? "TBT Leader" : "Approver";

  $("#modalBox").innerHTML = `
    <h3>${escapeAttr(traKey)}</h3>
    <p class="hint">${escapeAttr(info.title)}</p>
    ${!hitch?.output_folder ? `<p class="hint warn">&#9888; No output folder is set for this hitch -- generating will be blocked until you set one on the Hitch Setup tab.</p>` : ""}
    ${info.has_task_field ? `<label class="full">Task / Activity detail (optional)<input id="taskValue" value="${escapeAttr(existing?.task_value || "")}"></label>` : ""}
    <h4>${leader}</h4>
    <div class="grid">
      <label>Name <input id="approverNameInput" value="${escapeAttr(approverName)}"></label>
      <label>Position <input id="approverPositionInput" value="${escapeAttr(approverPosition)}"></label>
    </div>
    <div class="crew-check-row">
      <span style="flex:1">${leader} signature</span>
      <span class="badge ${hasApproverSig ? "signed" : "unsigned"}" id="approverSigBadge">${hasApproverSig ? "Signature on file" : "No signature"}</span>
      <button type="button" class="secondary" id="approverSigBtn">${hasApproverSig ? "Re-capture" : "Capture"}</button>
    </div>
    <h4>2nd ${leader} <span class="hint" style="margin:0">(e.g. night supervisor &mdash; leave blank if not needed)</span></h4>
    <div class="grid">
      <label>Name <input id="approver2NameInput" value="${escapeAttr(approver2Name)}"></label>
      <label>Position <input id="approver2PositionInput" value="${escapeAttr(approver2Position)}"></label>
    </div>
    <div class="crew-check-row">
      <span style="flex:1">2nd ${leader} signature</span>
      <span class="badge ${hasApprover2Sig ? "signed" : "unsigned"}" id="approver2SigBadge">${hasApprover2Sig ? "Signature on file" : "No signature"}</span>
      <button type="button" class="secondary" id="approver2SigBtn">${hasApprover2Sig ? "Re-capture" : "Capture"}</button>
    </div>
    <h4>Crew on this document (${info.num_crew_rows} row${info.num_crew_rows === 1 ? "" : "s"} available on the form)</h4>
    <div id="crewChecks">${crewRowsHtml}</div>
    <p class="hint" id="crewLimitMsg"></p>
    <div class="row">
      <button type="button" id="generateBtn">Generate PDF</button>
      <button type="button" class="secondary" id="cancelBtn">Cancel</button>
      <span id="genStatus"></span>
    </div>
  `;

  function updateCrewLimitMsg() {
    const checkedCount = $$(".crew-pick", $("#modalBox")).filter((cb) => cb.checked).length;
    const msg = $("#crewLimitMsg");
    msg.textContent = `${checkedCount} of ${rowLimit} signature row${rowLimit === 1 ? "" : "s"} used.`;
    msg.classList.toggle("warn", checkedCount >= rowLimit);
  }
  updateCrewLimitMsg();
  $$(".crew-pick", $("#modalBox")).forEach((cb) => {
    cb.addEventListener("change", () => {
      const checkedCount = $$(".crew-pick", $("#modalBox")).filter((c) => c.checked).length;
      if (checkedCount > rowLimit) {
        cb.checked = false;
        alert(`This document only has ${rowLimit} signature row${rowLimit === 1 ? "" : "s"} available. Uncheck someone before adding another.`);
      }
      updateCrewLimitMsg();
    });
  });

  function currentFormSnapshot() {
    const selected = $$(".crew-pick", $("#modalBox")).filter((cb) => cb.checked).map((cb) => cb.value);
    return {
      crew: crewPool.filter((c) => selected.includes(c.name)),
      approver_name: $("#approverNameInput").value.trim(),
      approver_position: $("#approverPositionInput").value.trim(),
      approver2_name: $("#approver2NameInput").value.trim(),
      approver2_position: $("#approver2PositionInput").value.trim(),
      task_value: info.has_task_field ? $("#taskValue").value.trim() : undefined,
    };
  }
  // Opens the signature pad on top of this form. Before doing so, swap the
  // current (bottom) stack entry for one bound to a fresh snapshot of the
  // form's in-progress state, so popping back after saving re-renders this
  // same config with edits intact and the signature badges up to date.
  function openSigFor(name) {
    // Capture the snapshot NOW, while this form's DOM is still live --
    // by the time the signature modal is popped back off, modalBox will
    // already contain (and only contain) the signature pad's markup.
    const snapshot = currentFormSnapshot();
    modalStack[modalStack.length - 1] = () => openGenerateConfig(traKey, snapshot, { preferHitch: false });
    pushModal(() => openSignatureModal(name, () => {}));
  }

  $("#cancelBtn").addEventListener("click", popModal);
  $("#approverSigBtn").addEventListener("click", () => {
    const name = $("#approverNameInput").value.trim();
    if (!name) return alert("Enter the approver's name first.");
    openSigFor(name);
  });
  $("#approver2SigBtn").addEventListener("click", () => {
    const name = $("#approver2NameInput").value.trim();
    if (!name) return alert("Enter the 2nd approver's name first.");
    openSigFor(name);
  });
  $$(".sig-btn", $("#modalBox")).forEach((btn) => {
    btn.addEventListener("click", () => openSigFor(btn.dataset.name));
  });

  async function doGenerate(date, snap, filenameOverride) {
    const body = { date, tra_key: traKey, ...snap, filename: filenameOverride || undefined };
    try {
      await api("/api/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      closeAllModals();
      loadTraList();
    } catch (e) {
      alert("Couldn't generate the PDF: " + e.message);
    }
  }

  // Before writing the file, check whether that exact name is already
  // sitting in the output folder -- generating used to overwrite it with
  // no warning at all. If it exists, stack a small Replace/Rename/Cancel
  // prompt on top of this form (same snapshot-preserving pattern used for
  // signature capture) instead of writing over it silently.
  async function checkThenGenerate(date, snap, filenameOverride) {
    let check;
    try {
      check = await api("/api/generate/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date, tra_key: traKey, filename: filenameOverride }),
      });
    } catch (e) {
      alert("Couldn't check the output folder: " + e.message);
      return;
    }
    if (!check.exists) {
      await doGenerate(date, snap, filenameOverride);
      return;
    }
    modalStack[modalStack.length - 1] = () => openGenerateConfig(traKey, snap, { preferHitch: false });
    pushModal(() => {
      $("#modalBox").innerHTML = `
        <h3>File already exists</h3>
        <p class="hint">"${escapeAttr(check.name)}" is already in the output folder.</p>
        <div class="row">
          <button type="button" id="replaceBtn" class="danger">Replace</button>
          <button type="button" id="renameBtn" class="secondary">Rename</button>
          <button type="button" id="cancelExistBtn" class="secondary">Cancel</button>
        </div>`;
      $("#cancelExistBtn").addEventListener("click", popModal);
      $("#replaceBtn").addEventListener("click", async () => {
        popModal();
        await doGenerate(date, snap, filenameOverride);
      });
      $("#renameBtn").addEventListener("click", () => {
        const defaultStem = (filenameOverride || check.name).replace(/\.pdf$/i, "");
        modalStack[modalStack.length - 1] = () => openGenerateConfig(traKey, snap, { preferHitch: false });
        pushModal(() => {
          $("#modalBox").innerHTML = `
            <h3>Rename file</h3>
            <label class="full">New file name (without .pdf)<input id="renameInput" value="${escapeAttr(defaultStem)}"></label>
            <div class="row">
              <button type="button" id="renameConfirmBtn">Check &amp; Generate</button>
              <button type="button" class="secondary" id="renameCancelBtn">Cancel</button>
            </div>`;
          $("#renameCancelBtn").addEventListener("click", popModal);
          $("#renameConfirmBtn").addEventListener("click", async () => {
            const newName = $("#renameInput").value.trim();
            if (!newName) return;
            popModal();
            await checkThenGenerate(date, snap, newName);
          });
        });
      });
    });
  }

  $("#generateBtn").addEventListener("click", async () => {
    const btn = $("#generateBtn");
    btn.disabled = true;
    $("#genStatus").textContent = "Checking...";
    const date = $("#dateInput").value;
    const snap = currentFormSnapshot();
    try {
      await checkThenGenerate(date, snap, null);
    } finally {
      // The modal may already be gone (success) or replaced by the
      // exists/rename prompt; only touch these if this exact form is
      // still the one showing.
      const stillHere = document.getElementById("generateBtn") === btn;
      if (stillHere) {
        btn.disabled = false;
        $("#genStatus").textContent = "";
      }
    }
  });
}

// ---------- weekly timesheets ----------
const TS_CODES = { O: "Offshore", T: "Travel", S: "Shop", M: "Other" };
const TS_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
let tsWeek = null;   // "YYYY-MM-DD", always a Sunday
let tsData = null;

function isoDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function parseIso(s) {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}
function shortDate(s) {
  const d = parseIso(s);
  return `${d.getMonth() + 1}/${d.getDate()}/${d.getFullYear()}`;
}
// Timesheet weeks run Monday-Sunday: any date snaps to the Sunday ending its week.
function weekEndingFor(s) {
  const d = parseIso(s);
  d.setDate(d.getDate() + ((7 - d.getDay()) % 7));
  return isoDate(d);
}
function shiftWeek(s, weeks) {
  const d = parseIso(s);
  d.setDate(d.getDate() + 7 * weeks);
  return isoDate(d);
}

async function loadTimesheets(week) {
  tsWeek = weekEndingFor(week || tsWeek || todayStr());
  $("#tsWeekInput").value = tsWeek;
  tsData = await api(`/api/timesheets/${tsWeek}`);
  renderTimesheets();
}

$("#tsWeekInput").addEventListener("change", (e) => {
  if (!e.target.value) return;
  const snapped = weekEndingFor(e.target.value);
  if (snapped !== e.target.value) {
    $("#tsWeekLabel").textContent = "(moved to the Sunday that ends that week)";
  }
  loadTimesheets(snapped);
});
$("#tsPrevWeek").addEventListener("click", () => loadTimesheets(shiftWeek(tsWeek, -1)));
$("#tsNextWeek").addEventListener("click", () => loadTimesheets(shiftWeek(tsWeek, 1)));

function saveTimesheetWeek(payload) {
  return api(`/api/timesheets/${tsWeek}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch((e) => alert("Couldn't save: " + e.message));
}

function renderTimesheets() {
  const d = tsData;
  $("#tsWeekLabel").textContent = `Week ${d.week_number}  ·  ${shortDate(d.days[0])} – ${shortDate(d.days[6])}`;

  const opsFields = [["client", "Client"], ["vessel", "Vessel"], ["project", "Project Number"], ["system", "System"]];
  $("#tsOps").innerHTML = opsFields.map(([k, label]) =>
    `<label>${label} <input data-op="${k}" value="${escapeAttr(d.ops[k] || "")}"></label>`).join("");
  $$("#tsOps input").forEach((inp) => inp.addEventListener("change", () => {
    d.ops[inp.dataset.op] = inp.value;
    saveTimesheetWeek({ ops: d.ops });
  }));

  if (!d.people.length) {
    $("#tsGrid").innerHTML = '<p class="hint">No crew on this hitch yet &mdash; add them on Hitch Setup.</p>';
    return;
  }
  const head = d.days.map((day, i) =>
    `<th class="ts-day">${TS_DAY_NAMES[i]}<br><span>${shortDate(day).replace(/\/\d{4}$/, "")}</span></th>`).join("");
  const rows = d.people.map((p, idx) => {
    const cells = p.codes.map((c, i) => `<td class="ts-day"><select data-person="${idx}" data-day="${i}">
        ${["", "O", "T", "S", "M"].map((v) => `<option value="${v}"${v === c ? " selected" : ""}>${v || "–"}</option>`).join("")}
      </select></td>`).join("");
    const status = p.generated
      ? `<span class="badge signed">Done</span> <button type="button" class="ts-open" data-person="${idx}">View</button>`
      : (p.problems.length ? `<span class="badge unsigned" title="${escapeAttr(p.problems.join(" "))}">Needs setup</span>` : "");
    return `<tr>
      <td><input type="checkbox" class="ts-include" data-person="${idx}" checked></td>
      <td>${escapeAttr(p.name)}${p.contractor ? ' <span class="badge active">contractor</span>' : ""}
        <div class="ts-sub">${escapeAttr(p.official_position || "no official position set")} · ${p.shift} shift</div></td>
      ${cells}
      <td>${status}</td></tr>`;
  }).join("");
  const problems = [...new Set(d.people.flatMap((p) => p.problems))];
  $("#tsGrid").innerHTML = `
    ${problems.length ? `<div class="hint warn">${problems.map(escapeAttr).join("<br>")}</div>` : ""}
    <div class="table-scroll"><table class="ts-table">
      <thead><tr><th title="Include in this run">✓</th><th>Name</th>${head}<th></th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;

  $$("#tsGrid select").forEach((sel) => sel.addEventListener("change", () => {
    const p = d.people[sel.dataset.person];
    p.codes[sel.dataset.day] = sel.value;
    saveTimesheetWeek({ codes: { [p.name]: p.codes } });
  }));
  $$("#tsGrid .ts-open").forEach((btn) => btn.addEventListener("click", () => {
    api(`/api/timesheets/${tsWeek}/open`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: d.people[btn.dataset.person].name }),
    }).catch((e) => alert(e.message));
  }));
}

// One person's acknowledgement prompt. Resolves "ack", "skip" or "stop".
function timesheetAckModal(p) {
  return new Promise((resolve) => {
    const finish = (answer) => { closeAllModals(); resolve(answer); };
    const render = () => {
      const counts = { O: 0, T: 0, S: 0, M: 0 };
      p.codes.forEach((c) => { if (counts[c] !== undefined) counts[c] += 1; });
      const total = Object.values(counts).reduce((a, b) => a + b, 0);
      const dayRows = tsData.days.map((day, i) =>
        `<tr><td>${TS_DAY_NAMES[i]} ${shortDate(day)}</td><td>${p.codes[i] ? `${p.codes[i]} &ndash; ${TS_CODES[p.codes[i]]}` : "&ndash; (not working)"}</td></tr>`).join("");
      $("#modalBox").innerHTML = `
        <h3>Timesheet &mdash; ${escapeAttr(p.name)}</h3>
        <p class="hint">Week ending ${shortDate(tsWeek)} (week ${tsData.week_number}) &middot; ${escapeAttr(p.official_position)} &middot;
          supervisor signature: ${escapeAttr(p.supervisor)}</p>
        <table class="ts-ack-table"><tbody>${dayRows}</tbody></table>
        <p>Offshore ${counts.O} &middot; Travel ${counts.T} &middot; Shop ${counts.S} &middot; Other ${counts.M} &middot; <b>Total days ${total}</b></p>
        ${p.exists ? '<p class="hint warn">A timesheet for this week already exists and will be replaced.</p>' : ""}
        <div class="ts-ack-text"><b>${escapeAttr(p.name)}, please read and confirm:</b><br>${escapeAttr(tsData.acknowledgement)}</div>
        ${p.has_signature ? "" : `<p class="hint warn">${escapeAttr(p.name)} has no signature saved yet.
          <button type="button" class="secondary" id="tsCaptureSig">Capture signature</button></p>`}
        <div class="row">
          <button type="button" id="tsAck" ${p.has_signature ? "" : "disabled"}>I acknowledge &mdash; sign &amp; save</button>
          <button type="button" class="secondary" id="tsSkip">Skip ${escapeAttr(p.name.split(" ")[0])}</button>
          <button type="button" class="secondary" id="tsStop">Stop</button>
        </div>`;
      $("#tsAck").addEventListener("click", () => finish("ack"));
      $("#tsSkip").addEventListener("click", () => finish("skip"));
      $("#tsStop").addEventListener("click", () => finish("stop"));
      const cap = $("#tsCaptureSig");
      if (cap) cap.addEventListener("click", () => pushModal(() => openSignatureModal(p.name, () => { p.has_signature = true; })));
    };
    closeAllModals();
    pushModal(render);
  });
}

$("#tsGenerateBtn").addEventListener("click", async () => {
  if (!tsData) return;
  const chosen = $$("#tsGrid .ts-include").filter((c) => c.checked).map((c) => tsData.people[c.dataset.person]);
  if (!chosen.length) { alert("Tick at least one person."); return; }
  const done = [], skipped = [];
  for (const p of chosen) {
    if (p.problems.length) { skipped.push(`${p.name}: ${p.problems.join(" ")}`); continue; }
    const answer = await timesheetAckModal(p);
    if (answer === "stop") break;
    if (answer === "skip") { skipped.push(`${p.name}: skipped`); continue; }
    try {
      const res = await api(`/api/timesheets/${tsWeek}/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: p.name, codes: p.codes, ops: tsData.ops, acknowledged: true }),
      });
      done.push(res.file);
    } catch (e) {
      skipped.push(`${p.name}: ${e.message}`);
    }
  }
  showModal(`
    <h3>Timesheets &mdash; week ending ${shortDate(tsWeek)}</h3>
    <p><b>${done.length}</b> saved:</p>
    ${done.length ? `<ul class="ts-result">${done.map((f) => `<li>${escapeAttr(f)}</li>`).join("")}</ul>` : ""}
    ${skipped.length ? `<p class="hint warn">Not saved:</p><ul class="ts-result">${skipped.map((s) => `<li>${escapeAttr(s)}</li>`).join("")}</ul>` : ""}
    <div class="row"><button type="button" id="tsDoneClose">Close</button></div>`);
  $("#tsDoneClose").addEventListener("click", hideModal);
  await loadTimesheets(tsWeek);
});

// ---------- app updates ----------
function notesHtml(text) {
  return escapeAttr(text).split(String.fromCharCode(10)).join("<br>");
}

// Asks the app (which asks the private GitHub repo) whether a newer
// release exists. Offline or not set up -> stays silent.
async function checkForUpdate() {
  let info;
  try { info = await api("/api/update/check"); } catch (e) { return; }
  const banner = $("#updateBanner");
  const parts = [];
  if (info.available) {
    parts.push(`<span><b>Update available:</b> DOUS Deckhand v${escapeAttr(info.latest)} (you have v${escapeAttr(info.current)})</span>
      <button type="button" id="updNotes" class="secondary">What's new</button>
      <button type="button" id="updInstall">Install update</button>`);
  }
  if (info.key_expires_soon) {
    parts.push(`<span class="hint warn" style="margin:0">The update key expires ${escapeAttr(info.key_expires.slice(0, 10))} &mdash; publish a release with a renewed key before then.</span>`);
  }
  if (!parts.length) { banner.hidden = true; return; }
  banner.innerHTML = parts.join("");
  banner.hidden = false;
  const notes = () => {
    showModal(`
      <h3>What's new in v${escapeAttr(info.latest)}</h3>
      <div class="update-notes">${notesHtml(info.notes || "No notes for this release.")}</div>
      <div class="row"><button type="button" id="updNotesClose">Close</button></div>`);
    $("#updNotesClose").addEventListener("click", hideModal);
  };
  if ($("#updNotes")) $("#updNotes").addEventListener("click", notes);
  if ($("#updInstall")) $("#updInstall").addEventListener("click", () => installUpdate(info));
}

function installUpdate(info) {
  showModal(`
    <h3>Install DOUS Deckhand v${escapeAttr(info.latest)}?</h3>
    <div class="update-notes">${notesHtml(info.notes || "")}</div>
    <p class="hint">Your hitches, crew, signatures, History and timesheets are kept. The app restarts itself afterwards (about 10 seconds).</p>
    <div class="row">
      <button type="button" id="updGo">Install now</button>
      <button type="button" id="updCancel" class="secondary">Not now</button>
    </div>`);
  $("#updCancel").addEventListener("click", hideModal);
  $("#updGo").addEventListener("click", async () => {
    $("#modalBox").innerHTML = `<h3>Updating&hellip;</h3><p id="updStatus">Downloading and checking the update &mdash; this can take a few minutes on a slow connection. Don't close this window.</p>`;
    try {
      await api("/api/update/install", { method: "POST" });
    } catch (e) {
      $("#modalBox").innerHTML = `<h3>The update didn't install</h3><p class="hint warn">${escapeAttr(e.message)}</p>
        <p class="hint">Nothing was changed &mdash; the app still works as before.</p>
        <div class="row"><button type="button" id="updErrClose">Close</button></div>`;
      $("#updErrClose").addEventListener("click", hideModal);
      return;
    }
    $("#updStatus").textContent = "Installed. Restarting the app...";
    // Wait for the restarted app to answer with the new version, then reload.
    for (let i = 0; i < 60; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      try {
        const v = await api("/api/version");
        if (v.version === info.latest) { location.reload(); return; }
      } catch (e) { /* still restarting */ }
    }
    $("#updStatus").textContent = "The update installed, but the app didn't restart by itself. Close this window and open DOUS Deckhand from the desktop icon.";
  });
}

// ---------- init ----------
(async function init() {
  try {
    await loadHitchSwitcher();
    await loadHitch();
    await loadTraList();
    checkForUpdate();   // in the background; never blocks start-up
  } catch (e) {
    document.querySelector("main").innerHTML = `
      <div class="hint warn" style="font-size:15px;padding:16px;">
        <strong>The app couldn't start up properly.</strong><br>
        ${e.message}<br><br>
        Try refreshing the page. If this keeps happening, check the black
        command window behind the browser for a more detailed error, or
        see the README's "If something goes wrong" section.
      </div>`;
    throw e;
  }
})();
