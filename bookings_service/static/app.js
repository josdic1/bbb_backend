// Change ports if your services run elsewhere.
const ROOMS_API = "http://localhost:8080"; // rooms_service
const BOOKINGS_API = "http://localhost:8082"; // bookings_service
const USERS_API = "http://localhost:8081"; // users_service (adjust if different)

// Keep this list identical to users_service/app/constants/dietary.py
// (Front-end cannot import that Python file directly; using a matching list avoids 404s.)
const DIETARY_OPTIONS = [
  "Gluten-Free",
  "Nut Allergy",
  "Dairy-Free",
  "Shellfish Allergy",
  "Vegetarian",
  "Vegan",
  "No Pork",
  "No Beef",
];

function byId(id) {
  return document.getElementById(id);
}

function setOutput(value) {
  const out = byId("output");
  if (!out) return;
  out.textContent =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

// Unified request logger (prints REQUEST -> RESPONSE)
async function apiRequest(url, options = {}) {
  const requestInfo = {
    url,
    method: options.method || "GET",
    headers: options.headers || {},
    body: options.body ? safeJsonParse(options.body) : null,
  };

  setOutput({
    stage: "REQUEST",
    request: requestInfo,
  });

  try {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));

    setOutput({
      stage: "RESPONSE",
      request: requestInfo,
      response: {
        status: res.status,
        ok: res.ok,
        data,
      },
    });

    return { res, data };
  } catch (err) {
    setOutput({
      stage: "NETWORK ERROR",
      request: requestInfo,
      error: String(err),
    });
    throw err;
  }
}

function safeJsonParse(maybeJsonString) {
  try {
    return JSON.parse(maybeJsonString);
  } catch {
    return maybeJsonString;
  }
}

// ---------- JWT Local Storage ----------
const JWT_STORAGE_KEY = "dev_console_jwt";

function saveJwtLocal() {
  const token = byId("jwt")?.value?.trim() || "";
  if (token) localStorage.setItem(JWT_STORAGE_KEY, token);
  else localStorage.removeItem(JWT_STORAGE_KEY);
}

function loadJwtLocal() {
  const saved = localStorage.getItem(JWT_STORAGE_KEY);
  if (!saved) return;
  const input = byId("jwt");
  if (input) input.value = saved;
}

function clearJwtLocal() {
  localStorage.removeItem(JWT_STORAGE_KEY);
  const input = byId("jwt");
  if (input) input.value = "";
}

// ---------- Auth helpers ----------
function getJwt() {
  return byId("jwt")?.value?.trim() || "";
}

function getAuthHeaders(extra = {}) {
  const token = getJwt();
  const headers = { accept: "application/json", ...extra };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

// ---------- Rooms + Tables picker ----------
let roomsCache = [];
let selectedTableId = null;

function setTableIdInput(valueOrNull) {
  const input = byId("table_id");
  if (!input) return;
  input.value = valueOrNull == null ? "" : String(valueOrNull);
}

function clearSelectedTable() {
  selectedTableId = null;
  setTableIdInput(null);
  renderRoomsTables();
}

function selectTable(tableId) {
  selectedTableId = Number(tableId);
  setTableIdInput(selectedTableId);
  renderRoomsTables();
}

function normalizeRoomsPayload(data) {
  const rooms = Array.isArray(data)
    ? data
    : Array.isArray(data?.rooms)
      ? data.rooms
      : [];

  return rooms.map((r) => ({
    id: r.id,
    name: r.name ?? `Room #${r.id}`,
    is_active: r.is_active ?? true,
    tables: Array.isArray(r.tables) ? r.tables : [],
  }));
}

function renderRoomsTables() {
  const el = byId("roomsTables");
  if (!el) return;

  if (!Array.isArray(roomsCache) || roomsCache.length === 0) {
    el.innerHTML = `<div class="muted">No rooms loaded yet. Click “Load Rooms + Tables”.</div>`;
    return;
  }

  el.innerHTML = roomsCache
    .filter((r) => r.is_active !== false)
    .map((room) => {
      const tables = (room.tables || []).filter((t) => t.is_active !== false);

      const tableButtons =
        tables.length === 0
          ? `<div class="muted">No tables found for this room.</div>`
          : `<div class="picker">
              ${tables
                .map((t) => {
                  const isSelected = selectedTableId === t.id;
                  const cls = isSelected ? "selected" : "";
                  const seats = t.seats != null ? ` · ${t.seats} seats` : "";
                  return `<button class="${cls}" onclick="selectTable(${t.id})">Table #${t.id}${seats}</button>`;
                })
                .join("")}
            </div>`;

      return `
        <div class="panel">
          <div><b>${room.name}</b> <span class="muted">(#${room.id})</span></div>
          ${tableButtons}
        </div>
      `;
    })
    .join("");
}

async function loadRoomsAndTables() {
  const { res, data } = await apiRequest(`${ROOMS_API}/rooms/`, {
    method: "GET",
    headers: { accept: "application/json" },
  });

  if (!res.ok) return;

  roomsCache = normalizeRoomsPayload(data);
  renderRoomsTables();
}

// ---------- Bookings list ----------
function renderBookings(list) {
  const el = byId("bookingsList");
  if (!el) return;

  if (!Array.isArray(list) || list.length === 0) {
    el.innerHTML = `<div class="muted">No bookings found.</div>`;
    return;
  }

  el.innerHTML = list
    .slice()
    .sort((a, b) => (a.id ?? 0) - (b.id ?? 0))
    .map((b) => {
      const tables = (b.tables || []).map((t) => t.table_id).join(", ");
      const attendees = (b.attendees || [])
        .map((a) => {
          const base =
            a.type === "member" ? `member:${a.member_id}` : `guest:${a.name}`;
          const diet =
            Array.isArray(a.dietary) && a.dietary.length
              ? ` (${a.dietary.join(", ")})`
              : "";
          return `${base}${diet}`;
        })
        .join(", ");

      return `
        <div class="booking">
          <h4>#${b.id} — ${b.date} — ${b.service_period} — ${b.status}</h4>
          <div><b>User:</b> ${b.user_id} | <b>Party:</b> ${b.party_size ?? ""} | <b>Duration:</b> ${b.duration_minutes ?? ""}</div>
          <div><b>Tables:</b> ${tables || "(none)"} </div>
          <div><b>Attendees:</b> ${attendees || "(none)"} </div>
          <div><b>Notes:</b> ${b.notes || ""}</div>
        </div>
      `;
    })
    .join("");
}

async function loadBookings() {
  const { res, data } = await apiRequest(`${BOOKINGS_API}/bookings/`, {
    method: "GET",
    headers: { accept: "application/json" },
  });

  if (!res.ok) return;
  renderBookings(data);
}

// ---------- Members picker ----------
let membersCache = []; // loaded members for the user
let selectedMemberIds = new Set(); // selected member IDs

function renderMembersPicker() {
  const el = byId("membersPicker");
  if (!el) return;

  if (!Array.isArray(membersCache) || membersCache.length === 0) {
    el.innerHTML = `<div class="muted">No members loaded. Enter User ID and click “Load Members”.</div>`;
    renderSelectedAttendees();
    return;
  }

  el.innerHTML = membersCache
    .map((m) => {
      const selected = selectedMemberIds.has(m.id);
      const cls = selected ? "selected" : "";
      const label = `${m.name} (#${m.id})`;
      return `<button class="${cls}" onclick="toggleMember(${m.id})">${label}</button>`;
    })
    .join("");

  renderSelectedAttendees();
}

function toggleMember(memberId) {
  if (selectedMemberIds.has(memberId)) selectedMemberIds.delete(memberId);
  else selectedMemberIds.add(memberId);
  renderMembersPicker();
}

async function whoAmI() {
  const { res, data } = await apiRequest(`${USERS_API}/auth/me`, {
    method: "GET",
    headers: getAuthHeaders(),
  });

  if (!res.ok) return;

  const userInput = byId("user_id");
  if (data?.id != null && userInput) {
    userInput.value = data.id;
  }
}

async function loadMembersForUser() {
  const userIdRaw = byId("user_id")?.value?.trim();
  if (!userIdRaw) {
    setOutput({
      error: "Enter user_id first (or click Who am I to auto-fill it)",
    });
    return;
  }

  const url = `${USERS_API}/users/${Number(userIdRaw)}/members/`;

  const { res, data } = await apiRequest(url, {
    method: "GET",
    headers: getAuthHeaders(),
  });

  if (!res.ok) return;

  membersCache = Array.isArray(data) ? data : [];
  selectedMemberIds = new Set();
  renderMembersPicker();
}

// ---------- Dietary helpers ----------
function normalizeDietary(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  if (typeof value === "string") {
    return value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }
  return [];
}

function getMemberDietary(memberId) {
  const m = (membersCache || []).find((x) => x.id === Number(memberId));
  return normalizeDietary(
    m?.dietary_restrictions ??
      m?.dietary ??
      m?.allergies ??
      m?.restrictions ??
      null,
  );
}

function buildDietaryPicker(selectedValues = []) {
  const wrap = document.createElement("div");
  wrap.className = "dietary";
  wrap.dataset.role = "dietary";

  const selectedSet = new Set((selectedValues || []).map(String));

  for (const opt of DIETARY_OPTIONS) {
    const lbl = document.createElement("label");

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = opt;
    cb.checked = selectedSet.has(String(opt));
    cb.onchange = renderSelectedAttendees;

    const txt = document.createElement("span");
    txt.textContent = opt;

    lbl.appendChild(cb);
    lbl.appendChild(txt);
    wrap.appendChild(lbl);
  }

  return wrap;
}

function getDietaryFromGuestRow(rowEl) {
  const checks = Array.from(
    rowEl.querySelectorAll('[data-role="dietary"] input[type="checkbox"]'),
  );
  return checks.filter((c) => c.checked).map((c) => c.value);
}

// ---------- Guest rows ----------
function addGuestRow(initialValue = "") {
  const guestRows = byId("guestRows");
  if (!guestRows) return;

  const rowId = `guest_${crypto.randomUUID?.() || String(Math.random()).slice(2)}`;

  const wrapper = document.createElement("div");
  wrapper.className = "hstack";
  wrapper.id = rowId;

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Guest name";
  input.value = initialValue;
  input.oninput = renderSelectedAttendees;

  const removeBtn = document.createElement("button");
  removeBtn.textContent = "Remove";
  removeBtn.onclick = () => {
    wrapper.remove();
    renderSelectedAttendees();
  };

  wrapper.appendChild(input);
  wrapper.appendChild(buildDietaryPicker([]));
  wrapper.appendChild(removeBtn);

  guestRows.appendChild(wrapper);
  renderSelectedAttendees();
}

function getGuestRowsData() {
  const guestRows = byId("guestRows");
  if (!guestRows) return [];

  const rows = Array.from(guestRows.children);

  return rows
    .map((row) => {
      const name = row.querySelector("input[type='text']")?.value?.trim() || "";
      const dietary = getDietaryFromGuestRow(row);
      return { name, dietary };
    })
    .filter((g) => g.name.length > 0);
}

// ---------- Attendee payload + preview ----------
function buildAttendeesPayload() {
  const attendees = [];

  // Members
  for (const memberId of selectedMemberIds) {
    const dietArr = getMemberDietary(memberId);

    attendees.push({
      type: "member",
      member_id: Number(memberId),
      dietary_restrictions: normalizeDietary(dietArr),
    });
  }

  // Guests
  for (const g of getGuestRowsData()) {
    const dietArr = normalizeDietary(g.dietary);

    attendees.push({
      type: "guest",
      name: g.name,
      dietary_restrictions: normalizeDietary(dietArr),
    });
  }

  return attendees;
}

function renderSelectedAttendees() {
  const el = byId("selectedAttendees");
  if (!el) return;

  const attendees = buildAttendeesPayload();

  if (attendees.length === 0) {
    el.innerHTML = `<div class="muted">None selected yet.</div>`;
    return;
  }

  el.innerHTML = attendees
    .map((a) => {
      const base =
        a.type === "member" ? `member:${a.member_id}` : `guest:${a.name}`;
      const diet =
        Array.isArray(a.dietary) && a.dietary.length
          ? ` — ${a.dietary.join(", ")}`
          : "";
      return `<span class="chip">${base}${diet}</span>`;
    })
    .join("");
}

// ---------- Create booking ----------
async function createBooking() {
  const userIdRaw = byId("user_id")?.value?.trim();
  const bookingDate = byId("date")?.value;
  const servicePeriod = byId("service_period")?.value;
  const durationRaw = byId("duration_minutes")?.value?.trim();
  const notes = byId("notes")?.value?.trim();

  const tableIdRaw = byId("table_id")?.value?.trim();

  // Prefer the picker selection; fall back to manual input.
  const resolvedTableId =
    selectedTableId != null
      ? Number(selectedTableId)
      : tableIdRaw
        ? Number(tableIdRaw)
        : null;

  const tableIds = resolvedTableId != null ? [resolvedTableId] : [];

  if (!userIdRaw) {
    setOutput({ error: "user_id is required" });
    return;
  }
  if (!bookingDate) {
    setOutput({ error: "date is required" });
    return;
  }
  if (!servicePeriod) {
    setOutput({ error: "service_period is required" });
    return;
  }

  const payload = {
    user_id: Number(userIdRaw),
    date: bookingDate,
    service_period: servicePeriod, // "lunch" | "dinner"
    duration_minutes: durationRaw ? Number(durationRaw) : 120,
    notes: notes || null,
    table_ids: tableIds,
    attendees: buildAttendeesPayload(),
    ordering_mode: null,
  };

  const { res } = await apiRequest(`${BOOKINGS_API}/bookings/`, {
    method: "POST",
    headers: {
      ...getAuthHeaders({ "Content-Type": "application/json" }),
      accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) return;

  await loadBookings();
}

// ---------- Init ----------
loadJwtLocal();

addGuestRow();
renderMembersPicker();
renderSelectedAttendees();
renderRoomsTables();
