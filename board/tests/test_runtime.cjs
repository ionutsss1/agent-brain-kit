// The whole page script against a mocked platform runtime (db, user, comments) and a mocked DOM.
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path'), assert = require('node:assert/strict');
const BOARD = path.join(__dirname, '..');
const page = fs.readFileSync(path.join(BOARD, 'board.html'), 'utf8');
const baseScript = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const {library} = require('./glb_fixture.cjs');
const START = '/* BOARD_CONFIG_START */', END = '/* BOARD_CONFIG_END */';
const defaults = JSON.parse(baseScript.slice(baseScript.indexOf(START) + START.length, baseScript.indexOf(END)));
// The same substitution board/build.py makes.
const withConfig = patch => baseScript.slice(0, baseScript.indexOf(START) + START.length) + JSON.stringify({...defaults, ...patch}) + baseScript.slice(baseScript.indexOf(END));
class Element {
  constructor(id, doc) { this.id = id; this.doc = doc; this.handlers = {}; this.checked = false; this.value = ''; this.hidden = false; this.disabled = false; this.dataset = {}; this.textContent = ''; this.open = false; this.parts = {}; this.attributes = {}; this.children = []; }
  addEventListener(type, fn) { this.handlers[type] = fn; }
  set innerHTML(html) { this.html = html; for (const match of html.matchAll(/\bid="([^"]+)"/g)) this.doc.items[match[1]] = new Element(match[1], this.doc); }
  get innerHTML() { return this.html || ''; }
  get options() { return [...(this.html || '').matchAll(/<option value="([^"]*)"/g)].map(match => ({value: match[1]})); }
  querySelector(selector) { if (selector === 'video') return this.children.find(child => child.id === 'video') || null; return this.parts[selector] ||= new Element(selector, this.doc); }
  replaceChildren() { this.html = ''; this.children = []; }
  append(child) { this.children.push(child); }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; delete this[name]; }
  pause() { this.paused = true; }
  load() { this.reloaded = true; }
  focus() { this.doc.activeElement = this; }
  select() { this.selected = true; }
  setSelectionRange() { this.selected = true; }
  showModal() { this.open = true; }
  close() { this.open = false; this.handlers.close?.(); }
}
const STORE = defaults.storageKey;
async function boot({available = true, permission = true, hash = '', savedPrefs = null, storageBlocked = true, media, goals, models, bundles = {}, fetchFailure = false, config = null, comments = null} = {}) {
  const script = config ? withConfig(config) : baseScript;
  const document = {items: {}, activeElement: null, title: '', getElementById(id) { return this.items[id] || null; }, createElement(tag) { return new Element(tag, this); }, querySelector() { return null; }};
  for (const match of page.matchAll(/\bid="([^"]+)"/g)) document.items[match[1]] = new Element(match[1], document);
  let next, errorCallback, subscriptions = 0, activeWrites = 0, maxWrites = 0;
  const writes = [], useCalls = [], callbacks = {}, requests = [], storage = new Map();
  if (savedPrefs) storage.set(STORE, JSON.stringify(savedPrefs));
  let bodies = [{id: 'a', title: 'Alpha', track: 'Platform', column: 'todo', order: 0, why: 'Reason', owner_note: '', open_questions: ['Question'], brief: 'briefs/a.md'},
                {id: 'b', title: 'Beta', track: 'Platform', column: 'todo', order: 1, owner_note: '', brief: 'briefs/b.md'}];
  const snapshot = () => ({docs: bodies.map(({id, ...data}) => ({id, data: () => Object.freeze(data)})), metadata: {hasPendingWrites: false, fromCache: false}});
  const db = {collection(name) { assert.equal(name, 'cards'); return {onSnapshot(n, e) { subscriptions++; next = n; errorCallback = e; queueMicrotask(() => n(snapshot())); return () => {}; }, doc(id) { return {async update(data) { activeWrites++; maxWrites = Math.max(maxWrites, activeWrites); writes.push({id, data}); await Promise.resolve(); bodies = bodies.map(card => card.id === id ? {...card, ...data} : card); next(snapshot()); activeWrites--; }}; }}; }};
  const context = {document, URL, TextEncoder, TextDecoder, atob, btoa, CSS: {escape: value => value}, location: new URL('https://artifact.example/board.html' + hash), console, Map, Set, Promise, setTimeout, clearTimeout, queueMicrotask,
    localStorage: {getItem(key) { if (storageBlocked) throw Error('unavailable'); return storage.get(key) || null; }, setItem(key, value) { if (storageBlocked) throw Error('unavailable'); storage.set(key, value); }}, matchMedia: q => ({matches: q.includes('700px')}),
    navigator: {clipboard: {async writeText() { throw Error('denied'); }}}, fetch: async (p) => { requests.push(p); if (fetchFailure) throw Error('offline'); const body = p === 'media.json' ? media : p === 'goals.json' ? goals : p === 'models3d/index.json' ? models : bundles[p]; return {ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body}; },
    claude: {async use(name) { useCalls.push(name); if (name === 'db') return available ? db : null; if (name === 'comments') { if (!comments) throw Object.assign(Error('no comments'), {code: 'capability_disabled'}); return comments; } return {can: async () => permission, id: async () => 'u_test'}; }},
    addEventListener: (name, fn) => { callbacks[name] = fn; }};
  context.window = context;
  vm.createContext(context);
  vm.runInContext(script + '\nglobalThis.testAccess={openDetail,persist,moveToColumn,selectHub,openMedia,openModel,createModelSession,setViewer:viewer=>{modelViewer=viewer;ensureModelViewer=async()=>viewer;},getCards:()=>cards,getFiltered:()=>filteredMedia()};', context);
  const flush = async () => { for (let i = 0; i < 12; i++) await new Promise(resolve => setImmediate(resolve)); };
  await flush();
  return {context, document, writes, flush, callbacks, requests, storage, get subscriptions() { return subscriptions; }, get maxWrites() { return maxWrites; }, useCalls, terminal: () => errorCallback({code: 'revoked'})};
}
(async () => {
  let run = await boot({available: false});
  assert.match(run.document.items['connection-text'].textContent, /Read-only/); assert.equal(run.subscriptions, 0); assert.equal(run.writes.length, 0);
  run = await boot({permission: false});
  assert.equal(run.subscriptions, 1); assert.match(run.document.items['connection-text'].textContent, /Read-only/); assert.equal(run.writes.length, 0);
  run = await boot();
  assert.equal(run.subscriptions, 1); assert.deepEqual(run.useCalls, ['db', 'user', 'comments']); assert.equal(run.writes.length, 0);
  assert.equal(run.document.items['hub-tab-3d'].hidden, true, '3D tab hidden by default');
  assert.equal(run.document.items['hub-tab-media'].hidden, false);
  assert.match(run.document.items['assign-who'].innerHTML, /main · worker/);
  assert.doesNotMatch(run.document.items['track-filters'].innerHTML, /FOCUS/, 'No focus chip without a focus track');
  const select = {value: 'doing', dataset: {move: 'a'}};
  run.document.items.board.handlers.change({target: {closest: () => select}});
  await run.flush();
  assert.equal(run.subscriptions, 1); assert.equal(run.maxWrites, 1);
  assert.equal(run.context.testAccess.getCards().find(c => c.id === 'a').column, 'doing');
  assert.equal(run.context.testAccess.getCards().find(c => c.id === 'b').order, 0);
  const n = run.writes.length;
  await run.context.testAccess.persist(run.context.testAccess.moveToColumn(run.context.testAccess.getCards(), 'a', 'doing'), 'noop');
  assert.equal(run.writes.length, n);
  run.context.testAccess.openDetail('a'); await run.flush();
  assert.match(run.document.items['brief-status'].textContent, /Brief not written yet/);
  run.document.items['owner-note'].value = 'Owner decision'; run.document.items['owner-note'].handlers.input();
  assert.equal(run.writes.length, n);
  await run.document.items['save-note'].handlers.click();
  assert.equal(run.writes.length, n + 1); assert.equal(run.writes.at(-1).data.owner_note, 'Owner decision');
  run.context.testAccess.openDetail('b'); await run.flush();
  assert.equal(run.document.items['owner-note'].value, '');
  run.context.testAccess.openDetail('a'); await run.flush();
  assert.equal(run.document.items['owner-note'].value, 'Owner decision');
  run.terminal(); assert.equal(run.document.items['owner-note'].disabled, true); assert.equal(run.subscriptions, 1);
  console.log('PASS: mocked runtime permissions/null DB, one subscription, phone change handler, serial writes, no-op, note save, missing brief, revoked connection, default tabs and assignees.');

  // Assign and start: the card moves to In progress with account + start_request, and the brain gets a comment.
  const sent = [];
  const comments = {async canSendToClaude() { return 'available'; }, async anchorFor() { return 'anchor-1'; }, async sendToClaude(message) { sent.push(message); }};
  run = await boot({comments, config: {focusTrack: 'Platform', title: 'Ops Board'}});
  assert.equal(run.document.items['board-title'].textContent, 'Ops Board');
  assert.match(run.document.items['track-filters'].innerHTML, /id="track-focus"[^>]*>Platform<span class="focus-label">FOCUS/);
  run.context.testAccess.openDetail('b'); await run.flush();
  assert.equal(run.document.items['start-work'].disabled, false);
  run.document.items['assign-who'].value = 'Codex';
  await run.document.items['start-work'].handlers.click(); await run.flush();
  assert.equal(sent.length, 1); assert.equal(sent[0].text, 'START b on Codex: Beta'); assert.equal(sent[0].anchor, 'anchor-1');
  const started = run.context.testAccess.getCards().find(c => c.id === 'b');
  assert.equal(started.column, 'doing'); assert.equal(started.order, 0); assert.equal(started.account, 'Codex');
  assert.equal(started.start_request.account, 'Codex'); assert.equal(started.start_request.sent, true);
  assert.match(started.status_note, /^start requested: Codex/);
  assert.match(run.document.items['assign-status'].textContent, /Sent to the brain/);
  run = await boot();
  run.context.testAccess.openDetail('a'); await run.flush();
  await run.document.items['start-work'].handlers.click(); await run.flush();
  assert.equal(run.context.testAccess.getCards().find(c => c.id === 'a').start_request.sent, false);
  assert.match(run.document.items['assign-status'].textContent, /next board check/);
  console.log('PASS: Assign and start with and without the comments capability; config title and focus track.');

  const media = {generated: '2026-01-07', items: [
    {id: 'old', date: '2025-12-30', kind: 'image', title: 'River', caption: 'Mist over the valley', topic: 'Design', file: 'media/old.jpg', orig_path: '/art/old.jpg'},
    {id: 'clip', date: '2026-01-06', kind: 'video', title: 'Demo clip', caption: 'Login flow', topic: 'Product', file: 'media/clip.mp4', poster: 'media/poster.jpg', duration_s: 65, orig_path: '/art/clip.mp4'},
    {id: 'new', date: '2026-01-07', kind: 'image', title: 'Tent concept', caption: 'Canvas by the river', topic: 'Design', file: 'media/new.jpg', orig_path: '/art/new.jpg'}
  ]};
  const goals = {generated: '2026-01-07', now: 'Ship the health check.', goals: [
    {id: 'platform', title: 'Platform <script>', group: 'systems', status: 'active', progress: 'Rulebook approved', why: 'Summary', where_we_are: 'Pending.', cards: ['a', 'not-seeded'], decisions: [{date: '2026-01-05', text: 'Health check first.', source: '/notes/RULEBOOK.md'}], subgoals: [{title: 'Endpoint', status: 'active', cards: ['b']}], sources: ['/notes/RULEBOOK.md']},
    {id: 'world', title: 'World', group: 'vision', status: 'later', progress: null, where_we_are: 'Later.', cards: [], decisions: [], subgoals: [], sources: []}
  ]};
  const click = (run, id, key, value) => run.document.items[id].handlers.click({target: {closest: () => ({dataset: {[key]: value}})}});
  run = await boot({hash: '#media', savedPrefs: {hub: 'goals'}, storageBlocked: false, media, goals});
  assert.equal(run.document.items['panel-media'].hidden, false);
  assert.equal(run.document.items['panel-tasks'].hidden, true);
  assert.equal(run.document.items['hub-tab-media'].getAttribute('aria-selected'), 'true');
  assert.equal(run.context.location.hash, '#media');
  assert.equal(JSON.parse(run.storage.get(STORE)).hub, 'media');
  assert.deepEqual(run.requests, ['media.json']);
  assert.equal(run.subscriptions, 1); assert.equal(run.writes.length, 0);
  assert.match(run.document.items['media-content'].innerHTML, /January 2026/);
  assert.match(run.document.items['media-content'].innerHTML, /December 2025/);
  assert.match(run.document.items['media-content'].innerHTML, /poster.jpg/);
  assert.match(run.document.items['media-content'].innerHTML, /1:05/);
  assert.match(run.document.items['media-content'].innerHTML, /loading="lazy"/);
  assert.equal(run.document.items['media-count'].textContent, '3 / 3 files');
  assert.deepEqual(Array.from(run.context.testAccess.getFiltered(), item => item.id), ['new', 'clip', 'old']);
  click(run, 'media-kinds', 'kind', 'video');
  assert.deepEqual(Array.from(run.context.testAccess.getFiltered(), item => item.id), ['clip']);
  assert.equal(run.document.items['media-kind-video'].getAttribute('aria-pressed'), 'true');
  click(run, 'media-kinds', 'kind', 'all'); click(run, 'media-topics', 'topic', 'Design');
  assert.deepEqual(Array.from(run.context.testAccess.getFiltered(), item => item.id), ['new', 'old']);
  run.document.items['media-search'].value = 'mist'; run.document.items['media-search'].handlers.input();
  assert.deepEqual(Array.from(run.context.testAccess.getFiltered(), item => item.id), ['old']);
  run.document.items['media-search'].value = 'no result'; run.document.items['media-search'].handlers.input();
  assert.equal(run.document.items['media-state'].hidden, false); assert.match(run.document.items['media-state'].textContent, /No media matches/);
  run.document.items['media-search'].value = ''; run.document.items['media-search'].handlers.input();
  run.document.items['media-search'].focus();
  click(run, 'media-content', 'media', 'new');
  assert.equal(run.document.items['media-viewer'].open, true); assert.equal(run.document.items['viewer-title'].textContent, 'Tent concept');
  assert.equal(run.document.items['viewer-path'].textContent, '/art/new.jpg');
  assert.equal(run.document.items['viewer-prev'].disabled, true);
  run.document.items['viewer-next'].focus();
  run.document.items['viewer-next'].handlers.click();
  assert.equal(run.document.items['viewer-title'].textContent, 'River');
  assert.equal(run.document.items['viewer-next'].disabled, true);
  assert.equal(run.document.activeElement.id, 'viewer-close');
  let prevented = false;
  run.document.items['media-viewer'].handlers.keydown({key: 'ArrowLeft', preventDefault() { prevented = true; }});
  assert(prevented); assert.equal(run.document.items['viewer-title'].textContent, 'Tent concept');
  run.document.items['media-viewer'].handlers.keydown({key: 'Escape', preventDefault() {}});
  assert.equal(run.document.items['media-viewer'].open, false); assert.equal(run.document.activeElement.id, 'media-search');
  assert.equal(run.document.items['viewer-stage'].children.length, 0);
  click(run, 'media-topics', 'topic', ''); click(run, 'media-content', 'media', 'clip');
  const video = run.document.items['viewer-stage'].children[0];
  assert.equal(video.id, 'video'); assert.equal(video.controls, true); assert.equal(video.playsInline, true);
  assert.match(video.poster, /poster.jpg$/); assert.equal(video.autoplay, undefined);
  video.handlers.error(); assert.equal(run.document.items['viewer-error'].hidden, false);
  run.document.items['viewer-close'].handlers.click(); assert.equal(video.paused, true); assert.equal(video.reloaded, true);

  click(run, 'hub-tabs', 'hub', 'goals'); await run.flush();
  assert.equal(run.context.location.hash, '#goals'); assert.equal(run.document.items['panel-goals'].hidden, false);
  assert.equal(run.document.items['goals-now-text'].textContent, 'Ship the health check.');
  assert.match(run.document.items['goals-content'].innerHTML, /Platform &lt;script&gt;/);
  assert.match(run.document.items['goals-content'].innerHTML, /Rulebook approved/);
  assert.match(run.document.items['goals-content'].innerHTML, /Health check first/);
  assert.match(run.document.items['goals-content'].innerHTML, /Endpoint/);
  assert(run.document.items['goals-content'].innerHTML.indexOf('>Vision<') < run.document.items['goals-content'].innerHTML.indexOf('>Systems<'));
  click(run, 'goals-content', 'goalCard', 'a'); await run.flush();
  assert.equal(run.context.location.hash, '#tasks'); assert.equal(run.document.items['panel-tasks'].hidden, false);
  assert.equal(run.document.items['detail-sheet'].open, true); assert.equal(run.document.items['detail-title'].textContent, 'Alpha');
  assert.equal(run.subscriptions, 1); assert.equal(run.writes.length, 0);
  run.document.items['close-sheet'].handlers.click();
  assert.equal(run.document.activeElement.id, 'card-61-open');
  run.context.testAccess.selectHub('goals'); click(run, 'goals-content', 'goalCard', 'not-seeded');
  assert.equal(run.context.location.hash, '#tasks'); assert.match(run.document.items['goal-link-status'].textContent, /not in the shared database yet/);
  run.context.location.hash = '#media'; run.callbacks.hashchange(); await run.flush();
  assert.equal(run.document.items['panel-media'].hidden, false);
  assert.equal(run.requests.filter(p => p === 'media.json').length, 1);
  run.document.items['hub-tabs'].handlers.keydown({key: 'ArrowRight', preventDefault() {}}); await run.flush();
  assert.equal(run.context.location.hash, '#goals'); assert.equal(run.document.activeElement.id, 'hub-tab-goals');
  run.document.items['hub-tabs'].handlers.keydown({key: 'ArrowRight', preventDefault() {}}); await run.flush();
  assert.equal(run.context.location.hash, '#tasks', 'Keyboard wraps past the disabled 3D tab');
  run.document.items['hub-tabs'].handlers.keydown({key: 'ArrowLeft', preventDefault() {}}); await run.flush();
  const saved = JSON.parse(run.storage.get(STORE));
  run = await boot({savedPrefs: saved, storageBlocked: false, media, goals});
  assert.equal(run.context.location.hash, '#goals'); assert.equal(run.document.items['panel-goals'].hidden, false);
  run = await boot({hash: '#media'}); assert.match(run.document.items['media-state'].textContent, /library is being built/i);
  run.context.testAccess.selectHub('goals'); await run.flush(); assert.match(run.document.items['goals-state'].textContent, /goals are being gathered/i);
  run = await boot({hash: '#media', media: {items: []}, goals: {goals: []}});
  assert.match(run.document.items['media-state'].textContent, /library is being built/i);
  run.context.testAccess.selectHub('goals'); await run.flush(); assert.equal(run.document.items['goals-state'].hidden, false);
  run = await boot({hash: '#media', media: {unexpected: true}, goals: {unexpected: true}});
  assert.match(run.document.items['media-state'].textContent, /could not be loaded/);
  run.context.testAccess.selectHub('goals'); await run.flush(); assert.match(run.document.items['goals-state'].textContent, /could not be loaded/);
  run = await boot({hash: '#goals', fetchFailure: true}); assert.match(run.document.items['goals-state'].textContent, /could not be loaded/);
  run = await boot({hash: '#goals', goals: JSON.parse(fs.readFileSync(path.join(BOARD, 'example', 'goals.json'), 'utf8'))});
  assert.match(run.document.items['goals-content'].innerHTML, /Observable service/);
  assert.match(run.document.items['goals-content'].innerHTML, /data-goal-card="EX01"/);
  assert.equal(run.subscriptions, 1);
  run = await boot({hash: '#3d'});
  assert.equal(run.context.location.hash, '#tasks', 'The disabled 3D tab is never opened');
  assert.deepEqual(run.requests, [], 'Nothing is fetched for a disabled tab');
  console.log('PASS: tab click/keyboard/hash/storage; media months, filters, full viewer, stepping, video cleanup; goals and task links; missing, empty, malformed and failed files; disabled 3D tab.');

  // The optional 3D tab, switched on by config, with only the rendering layer mocked.
  const {index: modelIndex, bundles: modelBundles} = library();
  const on3d = {tabs: {media: true, goals: true, '3d': true}};
  run = await boot({models: modelIndex, bundles: modelBundles, config: on3d});
  assert.equal(run.document.items['hub-tab-3d'].hidden, false);
  assert.deepEqual(run.requests, [], 'Tasks never fetches 3D assets');
  click(run, 'hub-tabs', 'hub', '3d'); await run.flush();
  assert.equal(run.context.location.hash, '#3d'); assert.equal(run.document.items['panel-3d'].hidden, false);
  assert.deepEqual(run.requests, ['models3d/index.json'], 'Opening the tab only fetches its index');
  assert.equal(run.document.items['model-count'].textContent, '3 / 3 models');
  run.document.items['model-search'].value = 'walk'; run.document.items['model-search'].handlers.input();
  assert.equal(run.document.items['model-count'].textContent, '1 / 3 models');
  assert.match(run.document.items['model-picker'].innerHTML, /optgroup label="Characters"/);
  assert(!run.document.items['model-picker'].innerHTML.includes('optgroup label="Buildings"'));
  run.document.items['model-search'].value = 'absent model'; run.document.items['model-search'].handlers.input();
  assert.match(run.document.items['model-picker'].innerHTML, /No models match/);
  run.document.items['model-search'].value = ''; run.document.items['model-search'].handlers.input();
  const sceneRoots = [], disposed = [], clipChanges = []; let toggles = 0, frames = 0;
  const fakeScene = {add(root) { sceneRoots.push(root); }, remove(root) { sceneRoots.splice(sceneRoots.indexOf(root), 1); }};
  const fakeLoader = {parse(bytes, base, resolve) {
    const view = new DataView(bytes), length = view.getUint32(12, true), doc = JSON.parse(new TextDecoder().decode(new Uint8Array(bytes, 20, length)));
    const material = {dispose() { disposed.push('material'); }}, geometry = {dispose() { disposed.push('geometry'); }};
    resolve({scene: {traverse(fn) { fn({isMesh: true, geometry, material}); }}, animations: doc.animations || []});
  }};
  const session = run.context.testAccess.createModelSession(fakeLoader, fakeScene, () => ({stopAllAction() { disposed.push('stop'); }, uncacheRoot() { disposed.push('uncache'); }}));
  run.context.testAccess.setViewer({show: getBytes => session.show(getBytes), clip: index => clipChanges.push(index), toggle: () => toggles++, frame: () => frames++, dispose: () => session.clear()});
  run.document.items['model-picker'].value = 'hut'; run.document.items['model-picker'].handlers.change(); await run.flush();
  assert.equal(run.document.items['model-state'].hidden, true); assert.equal(run.document.items['model-frame'].disabled, false);
  assert.equal(run.document.items['model-play'].disabled, true); assert.equal(run.document.items['model-clip'].disabled, true);
  assert.equal(run.document.items['model-title'].textContent, 'Hut'); assert.match(run.document.items['model-facts'].textContent, /triangles/);
  await run.context.testAccess.openModel('crate'); await run.flush();
  assert.equal(run.requests.filter(file => file === 'models3d/set_1.json').length, 1, 'Switching within a bundle reuses its fetch');
  assert.equal(sceneRoots.length, 1); assert.deepEqual(disposed, ['material', 'geometry']);
  await run.context.testAccess.openModel('walker'); await run.flush();
  assert.equal(run.document.items['model-clip'].disabled, false); assert.equal(run.document.items['model-play'].disabled, false);
  assert.equal((run.document.items['model-clip'].innerHTML.match(/<option /g) || []).length, 2);
  assert.deepEqual(clipChanges, [0]);
  run.document.items['model-clip'].value = '1'; run.document.items['model-clip'].handlers.change(); assert.deepEqual(clipChanges, [0, 1]);
  run.document.items['model-play'].handlers.click(); assert.equal(toggles, 1);
  run.document.items['model-frame'].handlers.click(); assert.equal(frames, 1);
  run.document.items['hub-tabs'].handlers.keydown({key: 'ArrowRight', preventDefault() {}}); assert.equal(run.context.location.hash, '#tasks');
  run.document.items['hub-tabs'].handlers.keydown({key: 'ArrowLeft', preventDefault() {}}); await run.flush(); assert.equal(run.context.location.hash, '#3d');
  assert.equal(run.requests.filter(file => file === 'models3d/index.json').length, 1);
  assert.equal(run.subscriptions, 1); assert.equal(run.writes.length, 0);
  run.callbacks.pagehide(); assert.equal(sceneRoots.length, 0); assert(disposed.includes('stop') && disposed.includes('uncache'));
  run = await boot({hash: '#3d', models: modelIndex, bundles: {}, config: on3d});
  run.context.testAccess.setViewer({show: getBytes => getBytes()}); await run.context.testAccess.openModel('hut');
  assert.match(run.document.items['model-state'].textContent, /could not load/); assert.equal(run.document.items['model-retry'].hidden, false);
  run = await boot({hash: '#3d', config: on3d}); assert.match(run.document.items['model-state'].textContent, /library is being built/);
  run = await boot({hash: '#3d', models: {unexpected: true}, config: on3d}); assert.match(run.document.items['model-state'].textContent, /Invalid 3D index/);
  run = await boot({hash: '#3d', models: {models: []}, config: on3d}); assert.match(run.document.items['model-state'].textContent, /library is being built/);
  run = await boot({savedPrefs: {hub: '3d'}, storageBlocked: false, models: modelIndex, config: on3d}); assert.equal(run.context.location.hash, '#3d');
  console.log('PASS: optional 3D tab on by config: tab/hash/keyboard/storage, grouped search, index-only fetch, model events, bundle caching, GLTF parse, disposal, clip controls, cleanup and error/empty states.');
})().catch(error => { console.error(error); process.exit(1); });
