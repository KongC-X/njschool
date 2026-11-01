# 南京中小学档案 · 构建入口
#
#   make            查看全部可用命令
#   make all        完整构建（索引 → 站点 → 导出）
#   make site       仅构建站点（含索引）
#   make export     仅生成导出件（目录 md / 对比表 xlsx）
#   make preview    本地预览（http://127.0.0.1:8788）
#   make clean      清理构建产物
#
# 部署时通过环境变量注入站点基址，sitemap 才会生成：
#   make site BASE=https://nj.example.com

# 优先使用隔离环境（依赖 markdown / openpyxl），不可用时退回系统 python3
VENV_PY := /Users/kongc/.workbuddy/binaries/python/envs/default/bin/python
PY := $(shell [ -x "$(VENV_PY)" ] && echo "$(VENV_PY)" || echo python3)

BASE ?=
PORT ?= 8788

.PHONY: help all site export index validate check audit reconcile sources preview clean verify-web test ingest ingest-fetch discover discover-apply extract expected

help:
	@echo "可用命令："
	@echo "  make all        完整构建（索引 + 站点 + 导出）"
	@echo "  make site       构建站点（自动先建索引）"
	@echo "  make export     生成目录 md 与对比表 xlsx"
	@echo "  make index      仅重建 index.json"
	@echo "  make validate   仅校验数据（不写文件）"
	@echo "  make check      语法检查 + 数据校验"
	@echo "  make test       前端核心单测（node --test）"
	@echo "  make ingest     采集干跑：看源清单与抓取计划（不发请求）"
	@echo "  make ingest-fetch  巡检一轮，报告新增公告（有外部请求，慎用）"
	@echo "  make discover   发现各校公告列表页（会联网，不写文件）"
	@echo "  make discover-apply  发现并保存到 data/source_lists.json"
	@echo "  make extract    S1 抽取：批次线 / 派位计划 / 施教区（只报告）"
	@echo "  make expected   把抽取到的施教区名单转成应收清单 CSV"
	@echo "  make verify-web 体检全部学校官网链接"
	@echo "  make audit      盘点数据缺口与收录遗漏"
	@echo "  make reconcile  按官方名单对账收录完整性"
	@echo "  make sources    重建来源登记表（data/sources.csv）"
	@echo "  make preview    本地预览 127.0.0.1:$(PORT)"
	@echo "  make clean      删除 site/ 与导出件"
	@echo ""
	@echo "部署：make site BASE=https://你的域名"

all: site export

index:
	$(PY) src/build_index.py

site: index sources
	NJ_BASE_URL="$(BASE)" $(PY) src/build_website.py

export: index
	$(PY) src/build_catalog.py
	$(PY) src/build_xlsx.py

validate:
	$(PY) src/validate.py

audit: index
	$(PY) src/audit_data.py

sources:
	$(PY) src/build_sources.py

reconcile:
	$(PY) src/reconcile.py

check:
	$(PY) -m py_compile src/*.py src/pipeline/*.py src/ingest/*.py && echo "语法检查通过"
	$(PY) src/validate.py

verify-web:
	$(PY) src/merge_websites.py
	$(PY) src/verify_websites.py --apply

# 采集层：默认干跑。--fetch 才会真的发请求，而那是对外部站点的动作，
# 所以不放进 all，必须显式调用。
ingest:
	$(PY) src/ingest/run.py --show-unverified

ingest-fetch:
	$(PY) src/ingest/run.py --fetch

# 列表页发现：一次性把 188 个学校源摸一遍，之后 run.py 按 list_url 巡检。
# 会联网（约 200 次请求），默认不写文件；--apply 才落 data/source_lists.json。
discover:
	$(PY) src/ingest/discover.py

discover-apply:
	$(PY) src/ingest/discover.py --apply

# S1 抽取：从官方公告取批次控制线，与站点现值比对。默认只报告，不改任何文件。
extract:
	$(PY) src/ingest/extract.py

# 把抽取结果落成 data/expected_*.csv，接进 reconcile.py 逐校对账
expected:
	$(PY) src/ingest/to_expected.py --apply

# 前端单测：只用固定样本，不依赖 site/ 产物，fresh clone 也能跑
# 传具体文件而不是目录：Node 22 会把目录当模块入口去 require，直接报 MODULE_NOT_FOUND
NODE := $(shell command -v node 2>/dev/null || echo node)

test:
	@echo "── 前端核心（node --test）──"
	@$(NODE) --test tests/*.test.mjs
	@echo "── 数据管道（unittest）──"
	@$(PY) -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -3

preview:
	@echo "预览地址：http://127.0.0.1:$(PORT)/"
	@cd site && $(PY) -m http.server $(PORT) --bind 127.0.0.1

clean:
	rm -rf site index.json 南京中小学档案.md 南京学校对比表.xlsx
	@echo "已清理构建产物"
