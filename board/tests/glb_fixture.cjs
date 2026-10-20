// A tiny, valid 3D library for the tests: three models in two bundles, built in memory (no asset files).
function makeGlb(doc, bin = Buffer.from([0, 0, 0, 0])) {
  const json = Buffer.from(JSON.stringify(doc));
  const jsonLen = (json.length + 3) & ~3, binLen = (bin.length + 3) & ~3;
  const out = Buffer.alloc(12 + 8 + jsonLen + 8 + binLen);
  out.writeUInt32LE(0x46546C67, 0); out.writeUInt32LE(2, 4); out.writeUInt32LE(out.length, 8);
  out.writeUInt32LE(jsonLen, 12); out.writeUInt32LE(0x4E4F534A, 16);
  out.fill(0x20, 20, 20 + jsonLen); json.copy(out, 20);
  const o = 20 + jsonLen;
  out.writeUInt32LE(binLen, o); out.writeUInt32LE(0x004E4942, o + 4); bin.copy(out, o + 8);
  return out;
}
function library() {
  const models = [
    {id: 'hut', name: 'Hut', group: 'Buildings', clips: [], tris: 120, size_m: [4, 3, 4], bundle: 'models3d/set_1.json'},
    {id: 'crate', name: 'Crate', group: 'Props', clips: [], tris: 12, size_m: [1, 1, 1], bundle: 'models3d/set_1.json'},
    {id: 'walker', name: 'Walker', group: 'Characters', clips: ['idle', 'walk'], tris: 800, size_m: [0.5, 1.8, 0.3], bundle: 'models3d/set_2.json'}
  ];
  const index = {groups: ['Buildings', 'Characters', 'Props', 'Details'], models};
  const bundles = {};
  for (const m of models) {
    const doc = {asset: {version: '2.0'}, scenes: [{nodes: []}], animations: m.clips.map(name => ({name, channels: [], samplers: []}))};
    (bundles[m.bundle] ||= {})[m.id] = {name: m.name, group: m.group, bin: makeGlb(doc).toString('base64'), clips: m.clips, size_m: m.size_m};
  }
  return {index, bundles};
}
module.exports = {makeGlb, library};
