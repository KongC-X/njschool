/* 搜索核心单测：node --test tests/
 *
 * 用固定样本，不读构建产物——否则 fresh clone 没有 site/ 就跑不了。
 * 期望值来自 tests/search-cases.json，非开发者也能加用例。
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));

/* assets/*.js 是 IIFE，靠 window 挂全局；Node 里先把 window 指回 globalThis */
globalThis.window = globalThis;
await import('../assets/search-core.js');

const S = globalThis.__NJ_SEARCH__;
const FIX = JSON.parse(fs.readFileSync(path.join(HERE, 'fixtures.json'), 'utf8')).schools;
const CASES = JSON.parse(fs.readFileSync(path.join(HERE, 'search-cases.json'), 'utf8'));

const ids = (rows) => rows.map((s) => s.id);

test('数字归一：阿拉伯数字转中文', () => {
  assert.equal(S.cnNum(9), '九');
  assert.equal(S.cnNum(13), '十三');
  assert.equal(S.cnNum(29), '二十九');
  assert.equal(S.normTerm('29中'), '二十九中');
  assert.equal(S.normTerm('1中'), '一中');
  assert.equal(S.normTerm('琅琊路'), '琅琊路', '非数字词不应被改动');
});

test('分词：空格分隔、去空、转小写', () => {
  assert.deepEqual(S.terms('  琅琊路   小学 '), ['琅琊路', '小学']);
  assert.deepEqual(S.terms(''), []);
  assert.deepEqual(S.terms('29中 12中'), ['二十九中', '十二中']);
});

test('数字边界：九中不能命中二十九中', () => {
  assert.equal(S.hasTerm('南京市第九中学', '九中'), true);
  assert.equal(S.hasTerm('南京市第二十九中学', '九中'), false, '「九中」是「二十九中」的子串，必须排除');
  assert.equal(S.hasTerm('南京市第二十九中学', '二十九中'), true);
  assert.equal(S.hasTerm('南京市第十二中学', '二中'), false);
});

test('别名按整词匹配，不做子串', () => {
  const a = { aliases: '拉力琅 拉力琅芳' };
  const b = { aliases: '拉力琅芳' };
  assert.equal(S.aliasHit(a, '拉力琅'), true);
  assert.equal(S.aliasHit(b, '拉力琅'), false, '「拉力琅」是「拉力琅芳」的前缀，不能算命中');
  assert.equal(S.aliasHit(b, '拉力琅芳'), true);
  assert.equal(S.aliasHit({ aliases: '' }, '拉力琅'), false);
});

test('评分：校名精确 > 前缀 > 包含 > 别名 > 简称 > 区名', () => {
  const ts = ['琅琊路'];
  assert.ok(S.score({ name: '琅琊路', short: '', tier: '', district: '' }, ts)
          > S.score({ name: '南京市琅琊路小学', short: '', tier: '', district: '' }, ts),
          '校名精确应高于前缀/包含');
  const alias = S.score({ name: '甲', short: '', tier: '', district: '', aliases: '琅琊路' }, ts);
  const outer = S.score({ name: '甲', short: '', tier: '', district: '琅琊路区' }, ts);
  assert.ok(alias > outer, '别名权重应高于区名');
});

for (const c of CASES) {
  test(`查询「${c.q}」${c.note ? '（' + c.note + '）' : ''}`, () => {
    const res = S.query(FIX, c.q, null);
    if (typeof c.expect === 'number') {
      assert.equal(res.rows.length, c.expect);
    } else {
      assert.deepEqual(ids(res.rows), c.expect);
    }
    if (c.fellBack !== undefined) assert.equal(res.fellBack, c.fellBack);
  });
}

test('limit 只截断结果，不影响命中判定', () => {
  const all = S.query(FIX, '拉力琅', null);
  const top2 = S.query(FIX, '拉力琅', null, { limit: 2 });
  assert.equal(all.rows.length, 3);
  assert.equal(top2.rows.length, 2);
  assert.deepEqual(ids(top2.rows), ids(all.rows).slice(0, 2));
});

test('筛选条件与关键词是 AND 关系', () => {
  const res = S.query(FIX, '小学', { lv: '小学', dist: '鼓楼区', type: '公办' });
  assert.equal(res.rows.length, 4);
  assert.equal(S.query(FIX, '小学', { lv: '高中' }).rows.length, 0);
  assert.equal(S.query(FIX, '玄外', { type: '公办' }).rows.length, 0, '玄外是民办');
});

test('tagline 只在主索引零结果时兜底', () => {
  const hit = S.query(FIX, '摇号', null);
  assert.equal(hit.fellBack, true);
  assert.equal(hit.rows.length, 1);
  /* 「琅小」在主索引里（简称），不应触发兜底 */
  assert.equal(S.query(FIX, '琅小', null).fellBack, false);
});

test('空查询返回全部，不算兜底', () => {
  const res = S.query(FIX, '', null);
  assert.equal(res.rows.length, FIX.length);
  assert.equal(res.fellBack, false);
  assert.deepEqual(res.terms, []);
});
