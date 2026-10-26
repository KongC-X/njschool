/* 对比核心单测：node --test tests/
 * 覆盖三态空值、差异判定、?ids= 去重与失效识别。
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';

globalThis.window = globalThis;
await import('../assets/compare-core.js');

const C = globalThis.__NJ_COMPARE__;

const SPECS = [
  { key: 'type',    label: '性质', group: 'identity', source: 'index', field: 'type',    diff: 'exact', priority: 10 },
  { key: 'tuition', label: '学费', group: 'path',     source: 'facts', field: 'tuition', diff: 'exact', priority: 20 },
  { key: 'address', label: '校址', group: 'evidence', source: 'facts', field: 'address', diff: 'none',  priority: 30 }
];

const mk = (over) => Object.assign({
  id: 'x', name: 'X', type: '公办', level: '小学', tagline: '', facts: null, hasSite: 0
}, over);

test('norm：全角转半角、空白归一、忽略大小写', () => {
  assert.equal(C.norm('Ａ Ｂ'), 'a b');
  assert.equal(C.norm('  公办  '), '公办');
  assert.equal(C.norm('公办\u3000民办'), '公办 民办');
  assert.equal(C.norm(null), '');
  assert.equal(C.norm('公办'), C.norm('公办 '), '尾部空格不应造成差异');
});

test('三态空值：有值 / 未获取 / 未收录', () => {
  const items = [
    mk({ id: 'a', facts: { tuition: '1 万/学期' } }),
    mk({ id: 'b', facts: null }),          // 档案声明了缺口
    mk({ id: 'c', facts: null })           // 档案没提
  ];
  const miss = { b: ['tuition'] };
  const rows = C.buildRows(SPECS, items, (id) => miss[id]);
  const t = rows.find((r) => r.key === 'tuition');

  assert.equal(t.cells[0].state, 'has');
  assert.equal(t.cells[0].text, '1 万/学期');
  assert.equal(t.cells[1].state, 'gap');
  assert.equal(t.cells[1].text, '未获取');
  assert.equal(t.cells[2].state, 'none');
  assert.equal(t.cells[2].text, '—');
  assert.equal(t.filled, 1);
});

test('差异判定：归一后仍不同才算不同', () => {
  const items = [mk({ type: '公办' }), mk({ type: '公办 ' }), mk({ type: '民办' })];
  const rows = C.buildRows(SPECS, items, null);
  const t = rows.find((r) => r.key === 'type');
  assert.equal(t.hasDiff, true);
  assert.equal(t.cells[0].isDiff, false, '「公办」与「公办 」应视为相同');
  assert.equal(t.cells[2].isDiff, true, '民办是行内唯一值');
});

test('全部相同 → 无差异', () => {
  const rows = C.buildRows(SPECS, [mk({ type: '公办' }), mk({ type: '公办' })], null);
  assert.equal(rows.find((r) => r.key === 'type').hasDiff, false);
});

test('diff:none 的行不参与差异判定', () => {
  const items = [
    mk({ id: 'a', facts: { address: '地址 A' } }),
    mk({ id: 'b', facts: { address: '地址 B' } })
  ];
  const rows = C.buildRows(SPECS, items, null);
  const r = rows.find((x) => x.key === 'address');
  assert.equal(r.hasDiff, false, '长文本行标差异会让四列全亮，等于没标');
  assert.equal(r.cells.every((c) => !c.isDiff), true);
});

test('只有一所填了不算差异，也不参与判定', () => {
  const items = [
    mk({ id: 'a', facts: { tuition: '1 万' } }),
    mk({ id: 'b', facts: null })
  ];
  const rows = C.buildRows(SPECS, items, null);
  const t = rows.find((r) => r.key === 'tuition');
  assert.equal(t.filled, 1);
  assert.equal(t.hasDiff, false, 'filled < 2 时「缺」不是「异」');
});

test('行按 priority 排序，且携带 total', () => {
  const rows = C.buildRows(SPECS, [mk({}), mk({})], null);
  assert.deepEqual(rows.map((r) => r.key), ['type', 'tuition', 'address']);
  assert.equal(rows[0].total, 2);
  assert.equal(rows[0].group, 'identity');
});

test('parseIds：去重、跳过无效、识别全失效', () => {
  const has = (id) => id.startsWith('ok');
  assert.deepEqual(C.parseIds('?ids=okA,okB,okA', has).ids, ['okA', 'okB'], '重复 id 只算一次');
  assert.equal(C.parseIds('?ids=okA,okB,okA', has).ids.length, 2);

  const bad = C.parseIds('?ids=X,Y', has);
  assert.deepEqual(bad.ids, []);
  assert.equal(bad.hadParam, true);
  assert.equal(bad.allInvalid, true, '链接失效要与「还没选」区分开');

  const none = C.parseIds('', has);
  assert.equal(none.hadParam, false);
  assert.equal(none.allInvalid, false);
});

test('toQuery：空数组不产生 ?ids=', () => {
  assert.equal(C.toQuery([]), '');
  assert.equal(C.toQuery(['a']), '?ids=a');
  assert.match(C.toQuery(['小学-甲']), /^\?ids=%E5%B0%8F/, '中文 id 必须编码进 URL');
});

test('levels 限定：该学段不适用的行整行不出现', () => {
  const specs = [
    { key: 'score', label: '投档线', group: 'path', source: 'facts',
      field: 'score', diff: 'exact', priority: 10, levels: ['高中'] },
    { key: 'type', label: '性质', group: 'identity', source: 'index',
      field: 'type', diff: 'exact', priority: 20 }
  ];
  const primary = [mk({ level: '小学' }), mk({ level: '小学' })];
  assert.deepEqual(C.buildRows(specs, primary, null).map((r) => r.key), ['type'],
    '四所小学对比不该出现投档线这一行');

  const hs = [mk({ level: '高中' }), mk({ level: '高中' })];
  assert.deepEqual(C.buildRows(specs, hs, null).map((r) => r.key), ['score', 'type']);

  const mixed = [mk({ level: '小学' }), mk({ level: '高中' })];
  assert.equal(C.buildRows(specs, mixed, null).length, 2, '混合学段时应保留该行');
});
