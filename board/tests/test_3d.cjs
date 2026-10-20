// The optional 3D tab's pure helpers against a small in-memory library (no asset files, no dependencies).
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const path = require('node:path');
const {library, makeGlb} = require('./glb_fixture.cjs');
const page = fs.readFileSync(path.join(__dirname, '..', 'board.html'), 'utf8');
const script = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const pure = script.split('// PURE_START')[1].split('\n').slice(1).join('\n').split('// PURE_END')[0];
const context = vm.createContext({URL, location: {href: 'https://artifact.example/board.html'}, TextEncoder, TextDecoder, atob, btoa});
vm.runInContext(pure + '\nglobalThis.api={parseModelIndex,parseModelBundle,filterModels,modelDocument,toGlb,createModelBundles,createModelSession,disposeModel};', context);
const api = context.api;
const plain = value => JSON.parse(JSON.stringify(value));
const {index, bundles} = library();
const models = api.parseModelIndex(index);
assert.equal(models.length, 3);
assert.deepEqual(plain(api.filterModels(models, '  WALK ')).map(m => m.id), ['walker']);
assert.equal(api.filterModels(models, 'Props').length, 1);
assert.equal(api.filterModels(models, 'no such model').length, 0);
assert.throws(() => api.parseModelIndex({}), /Invalid 3D index/);
assert.throws(() => api.parseModelIndex({models: [index.models[0], index.models[0]]}), /Invalid/);
assert.throws(() => api.parseModelIndex({models: [{...index.models[0], bundle: 'https://evil.test/a.json'}]}), /Invalid/);
assert.throws(() => api.parseModelIndex({models: [{...index.models[0], group: 'Unknown'}]}), /Invalid/, 'Groups come from the board config');
assert.throws(() => api.parseModelBundle({bad: {}}), /Invalid/);
assert.throws(() => api.parseModelBundle([]), /Invalid/);
assert.throws(() => api.modelDocument(btoa('invalid')), /Incomplete GLB/);
console.log('PASS: index and bundle validation, search, refusal of foreign bundle URLs and unknown groups.');

// GLB round trip: bundle base64 -> _bin document -> GLB bytes, byte-identical in content.
for (const [file, bundle] of Object.entries(bundles)) {
  api.parseModelBundle(bundle);
  for (const [id, entry] of Object.entries(bundle)) {
    const original = Buffer.from(entry.bin, 'base64');
    const rebuilt = Buffer.from(api.toGlb(api.modelDocument(entry.bin)));
    assert.equal(rebuilt.readUInt32LE(0), 0x46546c67); assert.equal(rebuilt.readUInt32LE(8), rebuilt.length);
    const json = b => JSON.parse(b.subarray(20, 20 + b.readUInt32LE(12)).toString());
    assert.deepEqual(json(rebuilt), json(original), file + ' ' + id + ': JSON chunk survives');
    assert.equal(rebuilt.length % 4, 0, 'Chunks stay 4-byte aligned');
  }
}
const odd = makeGlb({asset: {version: '2.0'}}, Buffer.from([1, 2, 3, 4, 5]));
assert.equal(Buffer.from(api.toGlb(api.modelDocument(odd.toString('base64')))).length % 4, 0);
console.log('PASS: GLB round trip and 4-byte padding.');

(async () => {
  let calls = 0;
  const fetcher = async file => { calls++; return {ok: !!bundles[file], status: bundles[file] ? 200 : 404, json: async () => bundles[file]}; };
  const get = api.createModelBundles(fetcher);
  const [a, b] = await Promise.all([get('models3d/set_1.json'), get('models3d/set_1.json')]);
  assert.equal(a, b); assert.equal(calls, 1, 'Concurrent loads of one bundle share a fetch');
  await assert.rejects(() => get('../secret.json'), /Invalid 3D bundle path/);
  await assert.rejects(() => get('models3d/missing.json'), /Bundle file 404/);
  await assert.rejects(() => get('models3d/missing.json'), /Bundle file 404/);
  assert.equal(calls, 3, 'A failed bundle is retried, not cached');
  const disposed = [];
  const scene = {roots: [], add(r) { this.roots.push(r); }, remove(r) { this.roots.splice(this.roots.indexOf(r), 1); }};
  const loader = {parse(bytes, base, resolve) { resolve({scene: {traverse(fn) { fn({geometry: {dispose() { disposed.push('g'); }}, material: {dispose() { disposed.push('m'); }}}); }}, animations: []}); }};
  const session = api.createModelSession(loader, scene, () => null);
  let release;
  const slow = session.show(() => new Promise(resolve => { release = resolve; }));
  const fast = await session.show(async () => new ArrayBuffer(8));
  release(new ArrayBuffer(8));
  assert.equal(await slow, null, 'A stale load never replaces a newer one');
  assert(fast); assert.equal(scene.roots.length, 1);
  session.clear(); assert.equal(scene.roots.length, 0); assert.deepEqual(disposed, ['m', 'g']);
  console.log('PASS: bundle cache (shared, retried, path-checked), stale-load race, scene cleanup.');
})().catch(error => { console.error(error); process.exit(1); });
