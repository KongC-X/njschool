#!/bin/bash
# 每周数据巡检（本地执行）
#
# 为什么在本地跑而不在 CI 跑：GitHub Actions 的 runner 在境外，访问国内
# 政府与学校站点（尤其 gov.cn 各区分站、*.njgljy.com 平台）大量连不通。
# 实测同一份代码本地失败率 4%、CI 上直接顶破 20% 阈值。CI 那条流水线保留
# 作兜底，但「新增公告数」只有在能直连国内网络的机器上才算得准。
#
# 调度方：WorkBuddy 的定时自动化（每周一 05:00 触发本脚本）。
# 试过 launchd 与 crontab，都被本机系统策略拦下——launchctl bootstrap 对最简
# plist 也返回 "5: Input/output error"，crontab 直接 "operation not permitted"。
# 因此改由应用层调度，脚本本身不依赖任何系统定时器，手动执行效果相同：
#     bash scripts/ingest-weekly.sh
#
# 三类产出：
#   1. logs/ingest-YYYY-MM-DD.log   完整过程与报告
#   2. data/source_lists.json       条目基线（自动提交，见文末说明）
#   3. data/facts/                  官方数字快照（只追加，不改档案）

set -uo pipefail

ROOT="/Users/kongc/WorkBuddy/南京学校"
PY="/Users/kongc/.workbuddy/binaries/python/envs/default/bin/python"
LOG_DIR="$ROOT/logs"
STAMP=$(date '+%Y-%m-%d')
LOG="$LOG_DIR/ingest-$STAMP.log"

# launchd 给的 locale 是 C/POSIX，不是 UTF-8。在那种 locale 下，`${RC}）` 这种
# 「变量名紧跟全角字符」会被 bash 解析成变量 `RC\xef`（全角括号的首字节被当成
# 变量名字符），配合 set -u 直接 unbound variable 退出。实测在终端里跑正常、
# 在 launchd 下必挂——这类差异不看日志根本发现不了。
# 两道保险都加上：强制 UTF-8 locale，且所有变量引用一律加花括号。
# 用强制赋值而不是 ${LANG:-默认}：launchd 会显式给一个 LANG=C，带默认值的写法不生效。
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export PYTHONIOENCODING=utf-8

mkdir -p "$LOG_DIR"
cd "$ROOT" || { echo "无法进入 $ROOT" >&2; exit 1; }

# launchd 的环境极简，PATH 里没有 homebrew / node。补上，否则 git 之外的
# 工具（node 跑单测、ruby 校验 yaml）都会找不到。
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

notify() {
    # 只在有图形会话时可用；launchd 跑在用户 session 里，通常没问题，
    # 但 SSH/无头场景会失败，因此不把它当作关键路径。
    osascript -e "display notification \"$2\" with title \"$1\"" 2>/dev/null || true
}

{
    echo "===== $(date '+%Y-%m-%d %H:%M:%S') 开始 ====="

    echo
    echo "--- 一、列表页发现（增量，失败不阻塞）---"
    "$PY" src/ingest/discover.py --apply || echo "发现步骤异常，继续"

    echo
    echo "--- 二、公告巡检 ---"
    "$PY" src/ingest/run.py --fetch --apply
    RC=$?
    echo "巡检退出码：${RC}"

    echo
    echo "--- 三、官方数字抽取（只报告，不改档案）---"
    "$PY" src/ingest/extract.py || echo "抽取步骤异常，继续"

    echo
    echo "===== $(date '+%Y-%m-%d %H:%M:%S') 结束（退出码 ${RC}）====="
} >>"$LOG" 2>&1

# ---------------------------------------------------------------- 基线提交
#
# source_lists.json 记录「已经通知过哪些条目标题」。不推进基线，同一条新增
# 会每周重复被报出来；而它只含标题与 URL，不涉及档案内容，自动提交是安全的。
# 只 add 这一个文件，不会把工作区里其他未完成的改动一起带走。
if ! git diff --quiet -- data/source_lists.json; then
    git add data/source_lists.json
    git commit -m "数据巡检：更新条目基线（${STAMP}）" >>"$LOG" 2>&1
    # 推送失败不影响本地结果，下次手动 push 会把这次提交一起带上去
    git push origin master >>"$LOG" 2>&1 || echo "推送失败（本地已提交，待下次手动推送）" >>"$LOG"
fi

# ---------------------------------------------------------------- 结果摘要
SUMMARY=$(grep -E "^汇总：" "$LOG" | tail -1)
[ -z "$SUMMARY" ] && SUMMARY="巡检未产出汇总行，见 $LOG"

if [ "${RC:-0}" -eq 2 ]; then
    notify "数据巡检：站点异常" "$SUMMARY"
    echo "【需处理】${SUMMARY}" >>"$LOG"
elif echo "$SUMMARY" | grep -qE "新增公告 [1-9]"; then
    notify "数据巡检：发现新公告" "$SUMMARY"
else
    notify "数据巡检：无新增" "$SUMMARY"
fi

# 只保留最近 12 份日志（约三个月），避免 logs/ 无限增长
ls -1t "$LOG_DIR"/ingest-*.log 2>/dev/null | tail -n +13 | xargs -r rm -f

echo "$SUMMARY"
exit "${RC:-0}"
