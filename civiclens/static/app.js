const $ = (selector) => document.querySelector(selector);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      })[c],
  );
const filterIds = ["topic", "status", "district", "jurisdiction"];
let offset = 0,
  total = 0,
  saved = [],
  writeToken = "",
  tokenRequired = false,
  loadVersion = 0;
const pageSize = 10;
async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Write-Token": writeToken,
      ...options.headers,
    },
  });
  if (!response.ok) {
    let error;
    try {
      error = await response.json();
    } catch {
      error = {};
    }
    const detail =
      typeof error.detail === "string"
        ? error.detail
        : error.detail
            ?.map((d) => `${d.loc.slice(1).join(".")}: ${d.msg}`)
            .join("; ");
    throw new Error(detail || `Request failed (${response.status}).`);
  }
  return response.status === 204 ? null : response.json();
}
function notice(message, error = false) {
  $("#notice").innerHTML = message
    ? `<div class="notice ${error ? "error" : ""}">${esc(message)}</div>`
    : "";
}
function criteria() {
  const values = { q: $("#search").value.trim() };
  filterIds.forEach((id) => (values[id] = $(`#${id}`).value));
  return values;
}
function params() {
  const p = new URLSearchParams(criteria());
  for (const [k, v] of [...p]) if (!v) p.delete(k);
  return p;
}
function dateLabel(value) {
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
function sourceLink(item) {
  return item.meeting.is_demo
    ? '<span class="demo-badge">Fictional source · demonstration only</span>'
    : `<a class="inline-link" href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer">Read the original record ↗</a>`;
}
async function loadFacets() {
  const facets = await request("/api/facets");
  for (const [id, key, label] of [
    ["topic", "topics", "All topics"],
    ["district", "districts", "All districts"],
    ["jurisdiction", "jurisdictions", "All communities"],
  ]) {
    const previous = $(`#${id}`).value;
    $(`#${id}`).innerHTML =
      `<option value="">${label}</option>` +
      facets[key]
        .map((value) => `<option value="${esc(value)}">${esc(value)}</option>`)
        .join("");
    if ([...$(`#${id}`).options].some((o) => o.value === previous))
      $(`#${id}`).value = previous;
  }
  if (facets.demo_records)
    notice(
      `${facets.demo_records} fictional sample records are included to demonstrate the workflow. Import actual records to follow your community.`,
    );
}
async function load() {
  const version = ++loadVersion,
    p = params();
  p.set("offset", offset);
  p.set("limit", pageSize);
  try {
    const data = await request(`/api/agenda?${p}`);
    if (version !== loadVersion) return;
    total = data.total;
    $("#results-label").textContent =
      `${total} matching record${total === 1 ? "" : "s"} · Most recent first`;
    $("#export").href = `/api/export.csv?${params()}`;
    $("#results").innerHTML = data.items.length
      ? data.items
          .map(
            (item) =>
              `<article class="record"><div class="record-meta"><span class="topic">${esc(item.topic)}</span><span>·</span><span>${esc(dateLabel(item.meeting.date))}</span><span class="status ${item.status}">${item.status}</span>${item.meeting.is_demo ? '<span class="demo-badge">FICTIONAL DEMO</span>' : ""}</div><h3><button class="record-open" data-item="${esc(item.id)}">${esc(item.title)}</button></h3><p>${esc(item.summary)}</p><footer><span>${esc(item.meeting.body)} · ${esc(item.district)}${item.reference ? ` · ${esc(item.reference)}` : ""}</span><button data-item="${esc(item.id)}">Follow the decision ↗</button></footer></article>`,
          )
          .join("")
      : '<div class="empty">No records match this view. Try a broader search, reset the filters, or import a new meeting bundle.</div>';
    $("#previous").disabled = offset === 0;
    $("#next").disabled = offset + pageSize >= total;
    $("#page-label").textContent = total
      ? `${offset + 1}–${Math.min(offset + pageSize, total)} of ${total}`
      : "No matching records";
    const url = params();
    history.replaceState(
      null,
      "",
      location.pathname + (url.size ? `?${url}` : ""),
    );
  } catch (error) {
    if (version !== loadVersion) return;
    notice(error.message, true);
    $("#results").innerHTML =
      '<p class="empty">The record could not be loaded. Search again to retry.</p>';
  }
}
async function loadSaved() {
  saved = await request("/api/saved-searches");
  $("#saved-searches").innerHTML = saved.length
    ? saved
        .map(
          (s) =>
            `<div class="saved-search"><button data-saved="${s.id}">${esc(s.name)} <small>(${s.matches})</small></button><button class="remove-search" data-remove="${s.id}" aria-label="Remove saved search ${esc(s.name)}">×</button></div>`,
        )
        .join("")
    : '<p class="aside-help">No saved searches yet.</p>';
}
async function openRecord(id) {
  const data = await request(`/api/agenda/${encodeURIComponent(id)}`),
    item = data.item;
  $("#record-detail").innerHTML =
    `<p class="eyebrow">${esc(item.meeting.jurisdiction)} · ${esc(item.reference || "PUBLIC RECORD")}</p><span class="status ${item.status}">${item.status}</span><h2>${esc(item.title)}</h2><p>${esc(item.summary)}</p><p class="provenance">${esc(item.meeting.body)} · ${esc(dateLabel(item.meeting.date))} · ${esc(item.district)}<br>Summary method: ${esc(item.summary_method)} · ${data.revisions.length} recorded revision${data.revisions.length === 1 ? "" : "s"}</p><h3>From the source</h3><blockquote class="source-excerpt">${esc(item.source_excerpt)}</blockquote>${sourceLink(item)}<h3>The decision’s path</h3><ol class="timeline">${data.timeline.map((row) => `<li><small>${esc(dateLabel(row.meeting.date))} · ${esc(row.meeting.body)}</small><h4>${esc(row.title)}</h4><span class="status ${row.status}">${row.status}</span><p>${esc(row.summary)}</p>${sourceLink(row)}</li>`).join("")}</ol><details><summary class="inline-link">Import revision history</summary>${data.revisions.map((r) => `<p>${esc(new Date(r.changed_at).toLocaleString())} · ${esc(r.item.status)}<br>${esc(r.item.summary)}</p>`).join("")}</details>`;
  $("#detail-dialog").showModal();
}
$("#results").addEventListener("click", (event) => {
  const button = event.target.closest("[data-item]");
  if (button)
    openRecord(button.dataset.item).catch((e) => notice(e.message, true));
});
filterIds.forEach((id) =>
  $(`#${id}`).addEventListener("change", () => {
    offset = 0;
    load();
  }),
);
$("#search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  offset = 0;
  load();
});
$("#clear").addEventListener("click", () => {
  $("#search").value = "";
  filterIds.forEach((id) => ($(`#${id}`).value = ""));
  offset = 0;
  load();
});
$("#next").addEventListener("click", () => {
  offset += pageSize;
  load();
});
$("#previous").addEventListener("click", () => {
  offset = Math.max(0, offset - pageSize);
  load();
});
document
  .querySelectorAll("[data-close]")
  .forEach((button) =>
    button.addEventListener("click", () => button.closest("dialog").close()),
  );
$("#open-import").addEventListener("click", () =>
  $("#import-dialog").showModal(),
);
$("#write-token").addEventListener(
  "input",
  (event) => (writeToken = event.target.value),
);
$("#open-save").addEventListener("click", () => {
  if (tokenRequired && !writeToken) {
    notice(
      "Enter your workspace write token in Import records before saving a search.",
      true,
    );
    $("#import-dialog").showModal();
    return;
  }
  $("#save-dialog").showModal();
});
$("#save-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#save-submit").disabled = true;
  $("#save-error").textContent = "";
  try {
    const data = criteria();
    if (!data.status) data.status = null;
    await request("/api/saved-searches", {
      method: "POST",
      body: JSON.stringify({ name: $("#search-name").value.trim(), ...data }),
    });
    await loadSaved();
    $("#save-dialog").close();
    notice("Search saved. Its count updates when new records match.");
  } catch (error) {
    $("#save-error").textContent = error.message;
  } finally {
    $("#save-submit").disabled = false;
  }
});
$("#saved-searches").addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.dataset.saved) {
    const search = saved.find((s) => s.id === button.dataset.saved);
    $("#search").value = search.q;
    filterIds.forEach((id) => ($(`#${id}`).value = search[id] || ""));
    offset = 0;
    load();
  }
  if (button.dataset.remove) {
    try {
      await request(`/api/saved-searches/${button.dataset.remove}`, {
        method: "DELETE",
      });
      await loadSaved();
    } catch (error) {
      notice(error.message, true);
    }
  }
});
$("#import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#import-submit");
  button.disabled = true;
  $("#import-error").textContent = "";
  try {
    const file = $("#import-file").files[0];
    if (!file || file.size > 2 * 1024 * 1024)
      throw new Error("Choose a JSON file smaller than 2 MB.");
    let bundle;
    try {
      bundle = JSON.parse(await file.text());
    } catch {
      throw new Error(
        "The file is not valid JSON. Download the example bundle for the expected format.",
      );
    }
    const result = await request("/api/import", {
      method: "POST",
      body: JSON.stringify(bundle),
    });
    await loadFacets();
    await loadSaved();
    offset = 0;
    await load();
    $("#import-dialog").close();
    notice(
      `Import complete: ${result.added} added, ${result.updated} revised, ${result.unchanged} unchanged.`,
    );
  } catch (error) {
    $("#import-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
(async () => {
  try {
    const status = await request("/api/status");
    tokenRequired = status.write_token_required;
    await loadFacets();
    const query = new URLSearchParams(location.search);
    $("#search").value = query.get("q") || "";
    filterIds.forEach((id) => {
      if ([...$(`#${id}`).options].some((o) => o.value === query.get(id)))
        $(`#${id}`).value = query.get(id);
    });
    await Promise.all([load(), loadSaved()]);
  } catch (error) {
    notice(error.message, true);
  }
})();
