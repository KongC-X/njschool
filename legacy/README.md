# legacy/ — 已停用脚本与历史产物

保留原因：数据处理逻辑（投档线、梯队、政策条目）仍有参考价值，且历史产物需可追溯。
**不要再运行这里的脚本**——它们与当前站点链路并行维护会造成数据分叉。

## 停用清单

| 文件 | 原用途 | 停用原因 | 替代 |
|---|---|---|---|
| `build_site.py` | 生成根目录 `南京中小学全景档案.html` | 与站点列表页重复，两套 CSS 并行 | `src/build_website.py` |
| `build_html.py` | 同上（更早版本） | 同上，且被 `build_site.py` 覆盖 | `src/build_website.py` |
| `build_md.py` | 生成 `南京中小学档案.md` | 数据源为 `data_*.py`，与档案脱节 | `src/build_catalog.py` |
| `build_csv.py` | 由 `data_*.py` 导出 15 个 CSV | 已不参与站点构建 | 无（历史参考） |
| `data_high.py` / `data_mid.py` / `data_pri.py` / `data_policy.py` | 手工维护的结构化数据 | 与 204 份 Markdown 档案重复，且已停止更新 | 档案本身 + `index.json` |
| `export/南京中小学全景档案.html` | 单文件版全景档案 | 被 `site/` 取代 | `site/` |
| `data/*.csv` | 旧版结构化导出 | 数据已过期 | 无 |

## 为什么停用

这四组脚本构成「第二套数据源」：`data_*.py` 手工维护 → `build_*.py` 生成产物。
而站点链路是「Markdown 档案 → index.json → 页面」。

两套数据源同时存在时：
- 同一事实要在两处更新，必然漏改一处（已实际发生：`christian书院` → `基督中学` 的修正一度只改了档案，脚本里仍是旧值）
- 三套 CSS 各自演化，视觉无法保持一致

**当前唯一链路**：`content（档案 md）→ index.json → site/`

## 如果确实需要旧数据

CSV 与数据字典在 `legacy/data/`，仅供查阅。若需复用，请先核对是否与档案一致。
