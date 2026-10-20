const results = document.querySelector('#results');
const controls = ['search','topic','status'].map(id => document.querySelector(`#${id}`));
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
async function load() {
  const params = new URLSearchParams({q: controls[0].value, topic: controls[1].value, status: controls[2].value});
  Object.keys(Object.fromEntries(params)).forEach(key => { if (!params.get(key)) params.delete(key); });
  const data = await fetch(`/api/agenda?${params}`).then(r => r.json());
  results.innerHTML = data.length ? data.map(item => `<article class="record"><div class="tag">${esc(item.topic)} · ${esc(item.status)}</div><h2>${esc(item.title)}</h2><p>${esc(item.summary)}</p><footer><span>${esc(item.district || 'Citywide')}</span><a href="${esc(item.source_url)}" target="_blank" rel="noreferrer">Read source ↗</a></footer></article>`).join('') : '<p class="empty">No matching agenda items.</p>';
}
controls.forEach(control => control.addEventListener('input', load));
load();

