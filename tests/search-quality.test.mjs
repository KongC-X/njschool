/* 搜索质量回归测试：跑真实构建产物，不是手写样本。
 *
 * 为什么单独一个文件：tests/search-core.test.mjs 跑的是 fixtures.json 里
 * 8 所手写样本，只能证明「逻辑写对了」，证明不了「545 所真实数据上都搜得出来」。
 * 实测曾出现三个只有全量数据才暴露的问题：
 *   · 搜「初中」返回 50 条（实际 164 所）——level 不在检索串里
 *   · 搜「金陵中学」本部排第 5——「南京市」前缀吃掉了前缀分
 *   · 别名表只有 7 条，家长圈术语全部落空
 * 这三个都不会被 fixtures 抓到，页面也不会报错，只是「搜不到」。
 *
 * 依赖 site/assets/*.js。fresh clone 没有 site/ 时整体 skip，不误报失败；
 * 但只要跑过 make site，这条闸门就必须全绿。
 *
 * 单独跑：node --test tests/search-quality.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const SITE = path.join(ROOT, 'site', 'assets');

const need = ['schools-data.js', 'streets-data.js'];
const missing = need.filter((f) => !fs.existsSync(path.join(SITE, f)));
const SKIP = missing.length > 0;
const WHY = `缺少构建产物 ${missing.join(', ')}，先跑 make site`;

if (SKIP) {
  console.log(`\n⚠ 搜索质量测试已跳过：${WHY}`);
  console.log('  这条闸门只在有构建产物时有意义，跳过不代表通过。\n');
}

/* CI 里设 NJ_REQUIRE_QUALITY=1：缺产物必须失败，不许静默跳过。
   否则「闸门」会变成「什么都没检查但显示通过」——这比没有闸门更危险，
   因为它会让人以为已经验过了。本地 fresh clone 不设这个变量，正常跳过。 */
if (SKIP && process.env.NJ_REQUIRE_QUALITY === '1') {
  test('搜索质量闸门缺少构建产物（CI 不允许跳过）', () => {
    assert.fail(`缺少 ${missing.join(', ')}。CI 里必须先构建站点再跑质量测试。`);
  });
}

/* 全局 window：三个 assets 都是 IIFE + window 挂载 */
globalThis.window = globalThis;

const RUN = (p) => vm.runInThisContext(fs.readFileSync(p, 'utf8'), { filename: p });

let DATA = [];
let Q = null;

if (!SKIP) {
  RUN(path.join(SITE, 'schools-data.js'));
  RUN(path.join(SITE, 'streets-data.js'));
  RUN(path.join(ROOT, 'assets', 'search-core.js'));

  Q = globalThis.__NJ_SEARCH__;
  const S = globalThis.__SCHOOLS__;
  const ST = globalThis.__STREETS__.rows;

  DATA = S.rows.map((row, i) => {
    const o = {};
    S.cols.forEach((k, idx) => { o[k] = row[idx]; });
    o.addr = ST[i] || '';
    o.id = `${o.level}-${o.name}`;
    return o;
  });
}

const q = (s) => Q.query(DATA, s, {});
const names = (rows, n) => rows.slice(0, n).map((x) => x.name);

/* ── 数据契约 ───────────────────────────────────────────── */

test('构建产物与索引的学校数一致，且各学段都有数据', { skip: SKIP && WHY }, () => {
  /* 不硬编码 545：每新增一所学校就要改测试的闸门，迟早会被人注释掉。
     改成与 index.json 交叉校验——数据增删它自己会跟上，只有「产物被截断」
     或「某学段整体丢失」才会红。 */
  const idx = path.join(ROOT, 'index.json');
  if (fs.existsSync(idx)) {
    const n = JSON.parse(fs.readFileSync(idx, 'utf8')).schools.length;
    assert.equal(DATA.length, n, `产物 ${DATA.length} 行，index.json 有 ${n} 所`);
  }
  const byLv = {};
  DATA.forEach((s) => { byLv[s.level] = (byLv[s.level] || 0) + 1; });
  for (const [lv, floor] of [['小学', 300], ['初中', 100], ['高中', 30]]) {
    assert.ok((byLv[lv] || 0) >= floor, `${lv}只有 ${byLv[lv] || 0} 所，低于下限 ${floor}`);
  }
});

test('每条记录都有校名、学段、区和一句话定位', { skip: SKIP && WHY }, () => {
  const bad = DATA.filter((s) => !s.name || !s.level || !s.district || !s.tagline);
  assert.equal(bad.length, 0, `字段缺失：${bad.slice(0, 3).map((s) => s.name).join(', ')}`);
});

/* ── 召回：家长用的词必须搜得到 ─────────────────────────── */

test('学段词能命中全部对应学段', { skip: SKIP && WHY }, () => {
  /* 这条曾全线失效：level 不在 hayMain 里，搜「初中」只出 50 条。
     留 4 条余量，避免个别档案改名时测试变脆。 */
  const cases = [['小学', 336], ['初中', 160], ['高中', 37]];
  for (const [kw, floor] of cases) {
    const n = q(kw).rows.length;
    assert.ok(n >= floor, `搜「${kw}」只有 ${n} 条，应至少 ${floor} 条（level 未进检索串？）`);
  }
});

test('学段 + 区名组合能收窄而不是清空', { skip: SKIP && WHY }, () => {
  /* 「初中 鼓楼」曾只返回 1 条，因为「初中」在 level 里搜不到，只剩校名撞上的那一所。 */
  const n = q('初中 鼓楼').rows.length;
  assert.ok(n >= 5, `搜「初中 鼓楼」只有 ${n} 条，组合检索失效`);
  const all = q('初中 鼓楼').rows;
  assert.ok(all.every((s) => s.district === '鼓楼区' && s.level === '初中'),
    '结果必须全部落在鼓楼区且为初中');
});

test('性质 + 学段能命中全部民办初中', { skip: SKIP && WHY }, () => {
  const real = DATA.filter((s) => s.type === '民办' && s.level === '初中').length;
  const n = q('民办 初中').rows.length;
  assert.equal(n, real, `搜「民办 初中」返回 ${n} 条，实际有 ${real} 所`);
});

/* ── 排序：搜全称/常用称呼，本部必须在第一位 ─────────────── */

test('完整校名搜索，top1 必须是该校自己', { skip: SKIP && WHY }, () => {
  /* 这是搜索的底线能力。曾 100% 通过，改动评分后必须保持。 */
  const fail = [];
  for (const s of DATA) {
    const r = q(s.name);
    if (!r.rows.length || r.rows[0].name !== s.name) {
      fail.push(`${s.name} → ${r.rows[0] ? r.rows[0].name : '零结果'}`);
    }
  }
  assert.equal(fail.length, 0,
    `${fail.length} 所搜自己都不是第一位：${fail.slice(0, 5).join('；')}`);
});

test('简称搜索，top1 命中率不低于 90%', { skip: SKIP && WHY }, () => {
  const withShort = DATA.filter((s) => (s.short || '').trim());
  let ok = 0;
  const fail = [];
  for (const s of withShort) {
    const r = q(s.short.trim());
    if (r.rows.length && r.rows[0].name === s.name) ok++;
    else fail.push(`${s.short} → ${r.rows[0] ? r.rows[0].name : '零结果'}`);
  }
  const rate = ok / withShort.length;
  assert.ok(rate >= 0.9,
    `简称 top1 命中率 ${(rate * 100).toFixed(1)}%（${ok}/${withShort.length}），低于 90%。例：${fail.slice(0, 5).join('；')}`);
});

test('校名带「南京市」的学校，搜核心名不会被同族分校压住', { skip: SKIP && WHY }, () => {
  /* 「金陵中学实验小学」因前缀命中拿 60 分，「南京市金陵中学」只拿 40 分，
     本部被排到第 5。73.9% 的校名带「南京市」，这是系统性偏差。 */
  const cases = [
    ['金陵中学', '南京市金陵中学'],
    ['南师附中', '南京师范大学附属中学'],
    ['第一中学', '南京市第一中学'],
  ];
  for (const [kw, expect] of cases) {
    const r = q(kw);
    assert.ok(r.rows.length > 0, `搜「${kw}」零结果`);
    assert.equal(r.rows[0].name, expect,
      `搜「${kw}」top1 是「${r.rows[0].name}」，应为「${expect}」`);
  }
});

/* ── 别名与组合词 ──────────────────────────────────────── */

test('组合词别名只返回本体，不被分校稀释', { skip: SKIP && WHY }, () => {
  const r = q('拉力琅');
  assert.equal(r.rows.length, 3, `「拉力琅」应只含 3 所，实际 ${r.rows.length} 所`);
  const got = names(r.rows, 3).sort();
  assert.deepEqual(got, ['南京市力学小学', '南京市拉萨路小学', '南京市琅琊路小学'].sort());
});

test('组合词能解析出完整成员，不被分校稀释', { skip: SKIP && WHY }, () => {
  /* 这条替代了原来「alias 所数 ≥ 30」的断言。
     那个指标是错的：525 所已有 short 简称，27 个候选口语词里几乎全部已被覆盖，
     堆别名数量只会产生冗余。真正会丢的是「组合词」——它无法由任何单校字段表达。
     口径来源见 pipeline/aliases.py：四大有档案原文佐证，六大/八大按站长确认口径。 */
  const S4 = ['南京师范大学附属中学', '南京市金陵中学', '南京市第一中学', '南京市中华中学'];
  const cases = [
    ['四大名小', ['南京市琅琊路小学', '南京市拉萨路小学', '南京市力学小学', '南京市芳草园小学']],
    ['四大名校', S4],
    ['六大', [...S4, '南京市第二十九中学', '南京市第十三中学']],
    ['八大', [...S4, '南京市第二十九中学', '南京市第十三中学',
             '南京市第九中学', '南京师范大学附属中学秦淮科技高中']],
  ];
  for (const [kw, expect] of cases) {
    const got = names(q(kw).rows, expect.length).sort();
    assert.deepEqual(got, expect.slice().sort(),
      `「${kw}」解析结果不对（应为 ${expect.length} 所），实际：${got.join('、')}`);
  }
});

/* ── 边界与地址层 ──────────────────────────────────────── */

test('数字边界：「九中」不能带出「二十九中」', { skip: SKIP && WHY }, () => {
  const r = q('九中');
  assert.ok(r.rows.every((s) => s.name !== '南京市第二十九中学'),
    '「九中」把二十九中也搜出来了');
  assert.equal(q('29中').rows[0].name, '南京市第二十九中学');
});

test('地址层：搜路名能出施教区学校，且标记为地址命中', { skip: SKIP && WHY }, () => {
  const r = q('宁海路');
  assert.ok(r.rows.length >= 1, '搜「宁海路」零结果');
  assert.equal(r.level, 2, '地址查询应走第二级检索');
  assert.ok(r.addrMatch, 'addrMatch 标记应为 true，结果卡才能写出「施教区含：X」');
});

test('无关词返回空结果而不是乱命中', { skip: SKIP && WHY }, () => {
  assert.equal(q('查无此校').rows.length, 0);
});
