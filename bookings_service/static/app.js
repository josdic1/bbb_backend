// ── Service URLs ────────────────────────────────────────────────────────────
// Correct port assignments:
const ROOMS_API = "http://localhost:8080"; // rooms_service
const USERS_API = "http://localhost:8081"; // users_service
const BOOKINGS_API = "http://localhost:8082"; // bookings_service
const ORDERS_API = "http://localhost:8083"; // orders_service
const MENU_API = "http://localhost:8084"; // menu_service



// Keep identical to users_service/app/constants/dietary.py
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

async function apiRequest(url, options = {}) {
  const requestInfo = {
    url,
    method: options.method || "GET",
    headers: options.headers || {},
    body: options.body ? safeJsonParse(options.body) : null,
  };
  setOutput({ stage: "REQUEST", request: requestInfo });

  try {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    setOutput({
      stage: "RESPONSE",
      request: requestInfo,
      response: { status: res.status, ok: res.ok, data },
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

function safeJsonParse(s) {
  try {
    return JSON.parse(s);
  } catch {
    return s;
  }
}

// ── JWT ─────────────────────────────────────────────────────────────────────
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

function getJwt() {
  return byId("jwt")?.value?.trim() || "";
}

function getAuthHeaders(extra = {}) {
  const token = getJwt();
  const headers = { accept: "application/json", ...extra };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

// ── Rooms + Tables picker ────────────────────────────────────────────────────
let roomsCache = [];
let selectedTableId = null;

function setTableIdInput(v) {
  const input = byId("table_id");
  if (!input) return;
  input.value = v == null ? "" : String(v);
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
  if (!roomsCache.length) {
    el.innerHTML = `<div class="muted">No rooms loaded yet. Click "Load Rooms + Tables".</div>`;
    return;
  }
  el.innerHTML = roomsCache
    .filter((r) => r.is_active !== false)
    .map((room) => {
      const tables = (room.tables || []).filter((t) => t.is_active !== false);
      const tableButtons =
        tables.length === 0
          ? `<div class="muted">No tables in this room.</div>`
          : `<div class="picker">${tables
              .map((t) => {
                const sel = selectedTableId === t.id;
                const seats = t.seats != null ? ` · ${t.seats} seats` : "";
                return `<button class="${sel ? "selected" : ""}" onclick="selectTable(${t.id})">Table #${t.id}${seats}</button>`;
              })
              .join("")}</div>`;
      return `<div class="panel"><div><b>${room.name}</b> <span class="muted">(#${room.id})</span></div>${tableButtons}</div>`;
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

// ── Bookings list ────────────────────────────────────────────────────────────
function renderBookings(list) {
  const el = byId("bookingsList");
  if (!el) return;
  if (!Array.isArray(list) || !list.length) {
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
            Array.isArray(a.dietary_restrictions) &&
            a.dietary_restrictions.length
              ? ` (${a.dietary_restrictions.join(", ")})`
              : "";
          return `${base}${diet}`;
        })
        .join(", ");
      const statusColors = {
        draft: "#888",
        confirmed: "#2980B9",
        seated: "#27AE60",
        completed: "#8E44AD",
        cancelled: "#E74C3C",
      };
      const statusColor = statusColors[b.status] || "#333";
      const ordersFlag = b.has_orders
        ? `<span style="color:#E67E22;font-weight:600"> · has orders</span>`
        : "";
      return `
        <div class="booking">
          <h4>#${b.id} — ${b.date} — ${b.service_period} — <span style="color:${statusColor}">${b.status}</span>${ordersFlag}</h4>
          <div><b>User:</b> ${b.user_id} | <b>Party:</b> ${b.party_size ?? ""} | <b>Duration:</b> ${b.duration_minutes ?? ""}</div>
          <div><b>Tables:</b> ${tables || "(none)"}</div>
          <div><b>Attendees:</b> ${attendees || "(none)"}</div>
          <div><b>Notes:</b> ${b.notes || ""}</div>
        </div>`;
    })
    .join("");
}

async function loadBookings() {
  const { res, data } = await apiRequest(`${BOOKINGS_API}/bookings/`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  if (!res.ok) return;
  renderBookings(data);
}

// ── Members picker ───────────────────────────────────────────────────────────
let membersCache = [];
let selectedMemberIds = new Set();

function renderMembersPicker() {
  const el = byId("membersPicker");
  if (!el) return;
  if (!membersCache.length) {
    el.innerHTML = `<div class="muted">No members loaded. Enter User ID and click "Load Members".</div>`;
    renderSelectedAttendees();
    return;
  }
  el.innerHTML = membersCache
    .map((m) => {
      const sel = selectedMemberIds.has(m.id);
      return `<button class="${sel ? "selected" : ""}" onclick="toggleMember(${m.id})">${m.name} (#${m.id})</button>`;
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
  if (data?.id != null && userInput) userInput.value = data.id;
}

async function loadMembersForUser() {
  const userIdRaw = byId("user_id")?.value?.trim();
  if (!userIdRaw) {
    setOutput({ error: "Enter user_id first (or click Who am I)" });
    return;
  }
  const { res, data } = await apiRequest(
    `${USERS_API}/users/${Number(userIdRaw)}/members/`,
    { method: "GET", headers: getAuthHeaders() },
  );
  if (!res.ok) return;
  membersCache = Array.isArray(data) ? data : [];
  selectedMemberIds = new Set();
  renderMembersPicker();
}

// ── Dietary helpers ──────────────────────────────────────────────────────────
function normalizeDietary(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  if (typeof value === "string")
    return value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
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
  return Array.from(
    rowEl.querySelectorAll('[data-role="dietary"] input[type="checkbox"]'),
  )
    .filter((c) => c.checked)
    .map((c) => c.value);
}

// ── Guest rows ───────────────────────────────────────────────────────────────
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
  return Array.from(guestRows.children)
    .map((row) => ({
      name: row.querySelector("input[type='text']")?.value?.trim() || "",
      dietary: getDietaryFromGuestRow(row),
    }))
    .filter((g) => g.name.length > 0);
}

// ── Attendee payload + preview ───────────────────────────────────────────────
function buildAttendeesPayload() {
  const attendees = [];
  for (const memberId of selectedMemberIds) {
    attendees.push({
      type: "member",
      member_id: Number(memberId),
      dietary_restrictions: normalizeDietary(getMemberDietary(memberId)),
    });
  }
  for (const g of getGuestRowsData()) {
    attendees.push({
      type: "guest",
      name: g.name,
      dietary_restrictions: normalizeDietary(g.dietary),
    });
  }
  return attendees;
}

function renderSelectedAttendees() {
  const el = byId("selectedAttendees");
  if (!el) return;
  const attendees = buildAttendeesPayload();
  if (!attendees.length) {
    el.innerHTML = `<div class="muted">None selected yet.</div>`;
    return;
  }
  el.innerHTML = attendees
    .map((a) => {
      const base =
        a.type === "member" ? `member:${a.member_id}` : `guest:${a.name}`;
      const diet =
        Array.isArray(a.dietary_restrictions) && a.dietary_restrictions.length
          ? ` — ${a.dietary_restrictions.join(", ")}`
          : "";
      return `<span class="chip">${base}${diet}</span>`;
    })
    .join("");
}

// ── Booking CRUD ─────────────────────────────────────────────────────────────
async function createBooking() {
  const userIdRaw = byId("user_id")?.value?.trim();
  const bookingDate = byId("date")?.value;
  const servicePeriod = byId("service_period")?.value;
  const durationRaw = byId("duration_minutes")?.value?.trim();
  const notes = byId("notes")?.value?.trim();
  const tableIdRaw = byId("table_id")?.value?.trim();

  const resolvedTableId =
    selectedTableId != null
      ? Number(selectedTableId)
      : tableIdRaw
        ? Number(tableIdRaw)
        : null;

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
    service_period: servicePeriod,
    duration_minutes: durationRaw ? Number(durationRaw) : 120,
    notes: notes || null,
    table_ids: resolvedTableId != null ? [resolvedTableId] : [],
    attendees: buildAttendeesPayload(),
    ordering_mode: null,
  };

  const { res } = await apiRequest(`${BOOKINGS_API}/bookings/`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!res.ok) return;
  await loadBookings();
}

async function confirmBooking() {
  const id = byId("action_booking_id")?.value?.trim();
  if (!id) {
    setOutput({ error: "booking_id is required" });
    return;
  }
  const { res } = await apiRequest(`${BOOKINGS_API}/bookings/${id}/confirm`, {
    method: "PATCH",
    headers: getAuthHeaders(),
  });
  if (!res.ok) return;
  await loadBookings();
}

async function seatBooking() {
  const id = byId("action_booking_id")?.value?.trim();
  if (!id) {
    setOutput({ error: "booking_id is required" });
    return;
  }
  const { res } = await apiRequest(`${BOOKINGS_API}/bookings/${id}/seat`, {
    method: "PATCH",
    headers: getAuthHeaders(),
  });
  if (!res.ok) return;
  await loadBookings();
}

async function closeBooking() {
  const id = byId("action_booking_id")?.value?.trim();
  if (!id) {
    setOutput({ error: "booking_id is required" });
    return;
  }
  const { res } = await apiRequest(`${BOOKINGS_API}/bookings/${id}/close`, {
    method: "PATCH",
    headers: getAuthHeaders(),
  });
  if (!res.ok) return;
  await loadBookings();
}

async function cancelBooking() {
  const id = byId("action_booking_id")?.value?.trim();
  if (!id) {
    setOutput({ error: "booking_id is required" });
    return;
  }
  const { res } = await apiRequest(`${BOOKINGS_API}/bookings/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) return;
  await loadBookings();
}

// ── Orders panel ─────────────────────────────────────────────────────────────
let menuCache = [];

async function loadMenu() {
  const { res, data } = await apiRequest(`${ORDERS_API}/menu/`, {
    method: "GET",
    headers: { accept: "application/json" },
  });
  if (!res.ok) return;
  menuCache = Array.isArray(data) ? data : [];
  renderMenuPicker();
}

function renderMenuPicker() {
  const el = byId("menuPicker");
  if (!el) return;
  if (!menuCache.length) {
    el.innerHTML = `<div class="muted">No menu items loaded. Click "Load Menu".</div>`;
    return;
  }

  // Group by category
  const byCategory = {};
  for (const item of menuCache) {
    if (!byCategory[item.category]) byCategory[item.category] = [];
    byCategory[item.category].push(item);
  }

  el.innerHTML = Object.entries(byCategory)
    .map(
      ([cat, items]) => `
    <div class="panel">
      <div class="pipeline-label">${cat}</div>
      <div class="picker">
        ${items
          .map(
            (item) => `
          <button onclick="setOrderMenuItem(${item.id}, '${item.name.replace(/'/g, "\\'")}', ${item.price_cents})">
            ${item.name} <span class="muted">$${(item.price_cents / 100).toFixed(2)}</span>
          </button>
        `,
          )
          .join("")}
      </div>
    </div>
  `,
    )
    .join("");
}

function setOrderMenuItem(id, name, priceCents) {
  const idInput = byId("order_menu_item_id");
  const nameDisplay = byId("order_menu_item_name");
  if (idInput) idInput.value = id;
  if (nameDisplay)
    nameDisplay.textContent = `${name} ($${(priceCents / 100).toFixed(2)})`;
}

async function createOrder() {
  const bookingId = byId("order_booking_id")?.value?.trim();
  const attendeeId = byId("order_attendee_id")?.value?.trim();
  const notes = byId("order_notes")?.value?.trim();
  const menuItemId = byId("order_menu_item_id")?.value?.trim();
  const quantity = byId("order_quantity")?.value?.trim() || "1";
  const itemNotes = byId("order_item_notes")?.value?.trim();

  if (!bookingId) {
    setOutput({ error: "booking_id is required" });
    return;
  }
  if (!menuItemId) {
    setOutput({ error: "Select a menu item first" });
    return;
  }

  const payload = {
    booking_id: Number(bookingId),
    attendee_id: attendeeId ? Number(attendeeId) : null,
    notes: notes || null,
    items: [
      {
        menu_item_id: Number(menuItemId),
        quantity: Number(quantity),
        notes: itemNotes || null,
      },
    ],
  };

  const { res } = await apiRequest(`${ORDERS_API}/orders/`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!res.ok) return;
  await loadOrdersForBooking();
}

async function loadOrdersForBooking() {
  const bookingId = byId("order_booking_id")?.value?.trim();
  if (!bookingId) {
    setOutput({ error: "Enter a booking_id to load its orders" });
    return;
  }

  const { res, data } = await apiRequest(
    `${ORDERS_API}/orders/?booking_id=${bookingId}`,
    { method: "GET", headers: getAuthHeaders() },
  );
  if (!res.ok) return;
  renderOrdersList(Array.isArray(data) ? data : []);
}

function renderOrdersList(orders) {
  const el = byId("ordersList");
  if (!el) return;
  if (!orders.length) {
    el.innerHTML = `<div class="muted">No orders for this booking.</div>`;
    return;
  }

  const statusColors = {
    pending: "#888",
    confirmed: "#2980B9",
    served: "#27AE60",
  };

  el.innerHTML = orders
    .map((o) => {
      const color = statusColors[o.status] || "#333";
      const items = (o.items || [])
        .map((i) => {
          const name = i.menu_item?.name || `item #${i.menu_item_id}`;
          return `${i.quantity}× ${name} @ $${(i.price_at_time / 100).toFixed(2)}${i.notes ? ` (${i.notes})` : ""}`;
        })
        .join(", ");
      const total = (o.items || []).reduce(
        (sum, i) => sum + i.price_at_time * i.quantity,
        0,
      );
      return `
      <div class="booking">
        <h4>Order #${o.id} — <span style="color:${color}">${o.status}</span>
          ${o.attendee_id ? `<span class="muted"> · attendee ${o.attendee_id}</span>` : ""}
        </h4>
        <div>${items || "(no items)"}</div>
        <div><b>Total:</b> $${(total / 100).toFixed(2)}</div>
        ${o.notes ? `<div><b>Notes:</b> ${o.notes}</div>` : ""}
        <div class="hstack" style="margin-top:8px">
          <button class="btn-confirm" onclick="advanceOrderStatus(${o.id}, '${o.status}')">Advance Status</button>
          <button class="btn-cancel" onclick="cancelOrder(${o.id})">Cancel Order</button>
        </div>
      </div>`;
    })
    .join("");
}

async function advanceOrderStatus(orderId, currentStatus) {
  const next = { pending: "confirmed", confirmed: "served" }[currentStatus];
  if (!next) {
    setOutput({ error: `Order is already ${currentStatus}` });
    return;
  }
  const { res } = await apiRequest(`${ORDERS_API}/orders/${orderId}`, {
    method: "PATCH",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ status: next }),
  });
  if (!res.ok) return;
  await loadOrdersForBooking();
}

async function cancelOrder(orderId) {
  const { res } = await apiRequest(`${ORDERS_API}/orders/${orderId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) return;
  await loadOrdersForBooking();
}

// ── Init ─────────────────────────────────────────────────────────────────────
loadJwtLocal();
addGuestRow();
renderMembersPicker();
renderSelectedAttendees();
renderRoomsTables();
