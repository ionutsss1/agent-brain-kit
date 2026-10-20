// Run the page's actual pure functions; no dependencies or network required.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const BOARD = path.join(__dirname, '..');
const page = fs.readFileSync(path.join(BOARD, 'board.html'), 'utf8');
const script = page.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script); // Syntax-check the entire inline page script.
const pure = script.split('// PURE_START')[1].split('\n').slice(1).join('\n').split('// PURE_END')[0];
const context = vm.createContext({URL, location: {href: 'https://artifact.example/board.html'}});
vm.runInContext(pure, context);
const run = code => JSON.parse(JSON.stringify(vm.runInContext(code, context)));
vm.runInContext(`const fixture = [
 {id:'a',column:'todo',order:0}, {id:'b',column:'todo',order:1},
 {id:'c',column:'todo',order:2}, {id:'d',column:'doing',order:0}
];`, context);
const apply = (cards, changes) => cards.map(card => ({...card, ...changes.find(change => change.id === card.id)}));
const fixture = run('fixture');
let changed = run("moveCards(fixture,'c','todo',0)");
let result = apply(fixture, changed).filter(card => card.column === 'todo').sort((a, b) => a.order - b.order);
assert.deepEqual(result.map(card => card.id), ['c', 'a', 'b']);
assert.deepEqual(result.map(card => card.order), [0, 1, 2]);
changed = run("moveToColumn(fixture,'b','doing')"); // Exact function used by the phone select handler.
result = apply(fixture, changed);
assert.deepEqual(result.filter(card => card.column === 'doing').sort((a, b) => a.order - b.order).map(card => card.id), ['d', 'b']);
assert.deepEqual(result.filter(card => card.column === 'todo').sort((a, b) => a.order - b.order).map(card => [card.id, card.order]), [['a', 0], ['c', 1]]);
assert.deepEqual(run("moveToColumn(fixture,'b','todo')"), []);
assert.deepEqual(run("moveCards(fixture,'b','todo',1)"), []);
assert.deepEqual(run("moveCards(fixture,'b','invalid',0)"), []);
assert.deepEqual(run("moveCards(fixture,'missing','done',0)"), []);
assert.equal(run("safeURL('javascript:alert(1)')"), null);
assert.equal(run("safeURL('data:text/html,x')"), null);
assert.equal(run("escapeHTML('<img onerror=1>')"), '&lt;img onerror=1&gt;');
assert.equal((script.match(/\.onSnapshot\(/g) || []).length, 1);
assert(!/claude\.db/.test(script));
assert(script.includes('const changes = moveToColumn(cards,id,target)'));
assert(!/<(?:html|head|body)(?:\s|>)/i.test(page));
assert(!page.includes('\r'));
console.log('PASS: page syntax; renumbered moves; phone Move to; no-op writes; URL escaping; single subscription.');

// Board settings: defaults and the markers board/build.py replaces.
const cfg = run('BOARD_CONFIG');
assert.equal(cfg.title, 'Task Board');
assert.equal(cfg.focusTrack, '', 'No focus track by default');
assert.deepEqual(cfg.tabs, {media: true, goals: true, '3d': false}, '3D tab is optional and off by default');
assert(cfg.assignees.length >= 1 && cfg.assignees.every(item => typeof item.value === 'string' && item.value));
assert.deepEqual(run('HUB_TABS'), ['tasks', 'media', 'goals']);
assert(page.includes('/* BOARD_CONFIG_START */') && page.includes('/* BOARD_CONFIG_END */'));
console.log('PASS: default board settings, 3D off by default, config markers.');

// Hub routing and data helpers execute the same functions as the UI.
assert.equal(run("hubTab('#goals','media')"), 'goals');
assert.equal(run("hubTab('', 'media')"), 'media');
assert.equal(run("hubTab('#unknown', 'unknown')"), 'tasks');
assert.equal(run("hubTab('#3d','tasks')"), 'tasks', 'A disabled tab is never routed to');
assert.equal(run("mediaURL('javascript:void(0)')"), null);
assert.equal(run("mediaURL('https://other.example/track.jpg')"), null);
assert.equal(run("mediaURL('media/image.jpg')"), 'https://artifact.example/media/image.jpg');
vm.runInContext(`const mediaFixture = {items:[
 {id:'older',date:'2025-12-30',kind:'image',title:'Old view',caption:'River mist',topic:'Design',file:'media/old.jpg'},
 {id:'movie',date:'2026-01-07T10:00:00+02:00',kind:'video',title:'Demo',caption:'Login flow',topic:'Product',file:'media/demo.mp4',poster:'media/demo.jpg',duration_s:65},
 {id:'newer',date:'2026-01-07T11:00:00+02:00',kind:'image',title:'New view',caption:'River camp',topic:'Design',file:'media/new.jpg'},
 {id:'newer',kind:'image',file:'media/duplicate.jpg'},
 {id:'unsafe',kind:'image',file:'data:text/html,unsafe'},null,
 {id:'bad-kind',kind:'audio',file:'media/a.mp3'}
]}; const parsedMedia = parseMedia(mediaFixture);`, context);
assert.deepEqual(run('parsedMedia.map(item=>item.id)'), ['newer', 'movie', 'older']);
assert.deepEqual(run("filterMedia(parsedMedia,'all','',' river ').map(item=>item.id)"), ['newer', 'older']);
assert.deepEqual(run("filterMedia(parsedMedia,'video','Product','login').map(item=>item.id)"), ['movie']);
assert.deepEqual(run("filterMedia(parsedMedia,'image','Product','').map(item=>item.id)"), []);
assert.equal(run("mediaStep(parsedMedia,'newer',1)"), 'movie');
assert.equal(run("mediaStep(parsedMedia,'movie',-1)"), 'newer');
assert.equal(run("mediaStep(parsedMedia,'newer',-1)"), null);
assert.equal(run("mediaStep(parsedMedia,'older',1)"), null);
assert.equal(run("mediaStep(parsedMedia,'unknown',1)"), null);
assert.equal(run('durationLabel(65.9)'), '1:05');
assert.equal(run('durationLabel(null)'), 'Video');
assert.throws(() => vm.runInContext('parseMedia({})', context), /Invalid media/);
assert.throws(() => vm.runInContext('parseGoals({})', context), /Invalid goals/);
assert.deepEqual(run("parseGoals({goals:[null,{id:'x',group:'systems',status:'active'},{id:'x',group:'systems'},{id:'y',group:'invalid'}]}).map(g=>g.id)"), ['x']);

// The example data shipped with the kit is valid and consistent.
const goalsData = JSON.parse(fs.readFileSync(path.join(BOARD, 'example', 'goals.json'), 'utf8'));
const tasks = JSON.parse(fs.readFileSync(path.join(BOARD, 'example', 'tasks.json'), 'utf8'));
const cardIds = new Set(tasks.tasks.map(task => task.id));
assert.equal(cardIds.size, 5, 'Five example cards');
assert(Number.isFinite(Date.parse(goalsData.generated)));
assert.equal(typeof goalsData.now, 'string');
assert.equal(new Set(goalsData.goals.map(goal => goal.id)).size, goalsData.goals.length);
for (const goal of goalsData.goals) {
  for (const field of ['id', 'title', 'group', 'why', 'status', 'where_we_are']) assert.equal(typeof goal[field], 'string', goal.id + ': ' + field);
  assert(cfg.goalGroups.includes(goal.group));
  assert(['done', 'active', 'next', 'paused', 'later'].includes(goal.status));
  for (const decision of goal.decisions) for (const field of ['date', 'text', 'source']) assert.equal(typeof decision[field], 'string');
  for (const id of [...goal.cards, ...goal.subgoals.flatMap(sub => sub.cards)]) assert(cardIds.has(id), goal.id + ': ' + id);
}
assert(page.includes('<title>Task Board</title>'));
for (const tab of ['tasks', 'media', 'goals', '3d']) assert(page.includes('id="panel-' + tab + '"'));
assert.equal((page.match(/<script src=/g) || []).length, 2);
assert(page.includes('/Sortable/1.15.2/') && page.includes('/marked/9.1.6/'));
assert(page.includes('loading="lazy"'));
assert(!/\b(?:alert|confirm|prompt)\s*\(/.test(script));
for (const file of ['board.html', 'example/goals.json', 'example/tasks.json', 'tests/test_board.cjs', 'tests/test_runtime.cjs', 'tests/test_3d.cjs'])
  assert(!fs.readFileSync(path.join(BOARD, file), 'utf8').includes('\r'), file + ' must use LF');
// Icons: Material Symbols only (no emoji in the page).
assert(page.includes('Material+Symbols+Outlined'));
assert(!/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(page), 'No emoji glyphs in the board');
console.log('PASS: hub routes; media validation/filter/order/stepping; example goals and card ids; page contract; Material icons only.');

assert(page.includes('view_in_ar'));
assert(page.includes('three@0.160.0/build/three.module.js'));
assert(page.includes('three@0.160.0/examples/jsm/'));
assert(page.includes('controls.autoRotate = false'));
assert(page.includes("loader.parse(bytes,'',resolve,reject)"));
console.log('PASS: optional 3D tab code present with pinned imports and no auto-rotate.');
