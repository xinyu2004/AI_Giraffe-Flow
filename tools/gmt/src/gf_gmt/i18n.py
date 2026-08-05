"""UI language helper for GMT GUI (zh or en keys)."""

from __future__ import annotations

import sys

_ORG = "GiraffeFlow"
_APP = "gf-gmt"
_LANG = "zh"

# Chinese source → English (menus / dialogs)
_EN: dict[str, str] = {
    '语言': 'Language',
    '中文': '中文',
    'English': 'English',
    '正在切换语言并重启应用…': 'Switching language and restarting…',
    'GMT — 选项目 → Live / 回灌 / Tag / 回放': 'GMT — project → Live / Inject / Tag / Replay',
    '加载项目…': 'Load project…',
    '选择 project.yaml（与 gf-config / codegen 同一入口；SOR 在同目录）': (
        'Pick project.yaml (same entry as gf-config / codegen; SOR alongside)'
    ),
    'SIL / 观测机地址（本机 127.0.0.1；远端填局域网 IP）\nLive 与回灌共用此 Host': (
        'SIL / observer host (127.0.0.1 local; LAN IP remote)\nShared by Live and Inject'
    ),
    '│ Live ws': '│ Live ws',
    '│ 回灌 tcp': '│ Inject tcp',
    '回灌 tcp': 'Inject tcp',
    '连接': 'Connect',
    '断开': 'Disconnect',
    '录制': 'Record',
    '录制中': 'Recording',
    '空闲': 'Idle',
    '已连接': 'Connected',
    '跟随最新': 'Follow latest',
    '仅影响 playhead：开=贴最新；关=停在当前帧（与是否录制落盘无关）': (
        'Live view: ON=stick display to newest; OFF=freeze display (still receive & record; independent of Inject)'
    ),
    'Live 旁观（未录制）': 'Live observe (not recording)',
    'Live 录制中': 'Live recording',
    ' [跟随]': ' [follow]',
    ' [不跟播]': ' [no follow]',
    ' [冻屏]': ' [frozen]',
    '·录制': '·rec',
    'Live WebSocket 端口（默认 {port}）': 'Live WebSocket port (default {port})',
    'Live WebSocket 端口（默认 {port})': 'Live WebSocket port (default {port})',
    'inject 控制口（默认 {port}，GF_INJECT_PORT）': (
        'Inject control port (default {port}, GF_INJECT_PORT)'
    ),
    '高级：不连 WS，只尾随已有 JSONL': 'Advanced: tail an existing JSONL (no WS)',
    '跟随最新 OFF — 冻屏：继续收流/录制，视图不跳': (
        'Follow latest OFF — freeze view: still receive/record, UI stays put'
    ),
    '跟随最新 ON — 贴最新事件': 'Follow latest ON',
    '回灌成功：#{idx} {topic} 已 Send': 'Injected #{idx} {topic}',
    '回灌跳过：#{idx} {topic}': 'Skipped #{idx} {topic}',
    'Inject 已连接 tcp://{host}:{port}': 'Inject connected tcp://{host}:{port}',
    'Live 旁观 ws://{host}:{port}（保留 session/回灌；可录制落盘，不写入时间轴）': (
        'Live observe ws://{host}:{port} (keep session/inject; Record to save, no timeline write)'
    ),
    'Live 已连接 ws://{host}:{port}（{mode}；落盘请点「录制」）': (
        'Live connected ws://{host}:{port} ({mode}; Record to save)'
    ),
    'Live 已断开 · 保留 session（{n} events）': 'Live disconnected · kept session ({n} events)',
    '无法连接 ws://{host}:{port}\n{exc}\n\n': (
        'Cannot connect ws://{host}:{port}\n{exc}\n\n'
    ),
    '无法连接 inject ctrl tcp://{host}:{port}\n{exc}\n\n': (
        'Cannot connect inject ctrl tcp://{host}:{port}\n{exc}\n\n'
    ),
    '打开 session…': 'Open session…',
    '从日志录制…': 'Record from logs…',
    '仅跟随文件…': 'Follow file only…',
    '加载 SOR…': 'Load SOR…',
    '播放': 'Play',
    '暂停': 'Pause',
    '导出 MCAP': 'Export MCAP',
    '倍速%': 'Speed %',
    '播放速度：越大越快。100%=默认；未勾「按 Δt」时约 200ms/事件；勾选后按事件时间缩放。': (
        'Playback speed: higher=faster. 100%=default; ~200ms/event without Δt; scales event time with Δt.'
    ),
    '按 Δt': 'Use Δt',
    '播放间隔按相邻事件真实 Δt，再乘倍速%': 'Interval from event Δt, then scaled by speed %',
    '跟随文件': 'Follow file',
    '轮询 JSONL 新行（「仅跟随 live 文件」用）。是否跳到最新由上方「跟随最新」决定。': (
        'Tail JSONL lines (file-follow mode). Jump-to-latest is controlled by Follow latest above.'
    ),
    '先后 / 竞态': 'Order',
    '动画 DAG': 'DAG',
    '变量轨': 'Graphics',
    '图形': 'Graphics',
    '缩放': 'Zoom',
    '时间放大': 'Zoom in (time)',
    '时间缩小': 'Zoom out (time)',
    '适应': 'Fit',
    '适应全部信号时窗': 'Fit all signals in view',
    'Tag 编辑': 'Tag',
    '回灌': 'Inject',
    '请先加载项目 → 填 Host → Live(ws:8766) 或 回灌(tcp:8767) 点「连接」': (
        'Load project → set Host → Connect Live (ws:8766) or Inject (tcp:8767)'
    ),
    '请先加载项目 → 填 Host → Live(ws:8766) / 回灌(tcp:8767) / OTA(DoIP)「连接」': (
        'Load project → Host → Connect Live(ws:8766) / Inject(tcp:8767) / OTA(DoIP)'
    ),
    '项目={name} · OTA：DoIP Host:Port →「连接」→ Start OTA': (
        'project={name} · OTA: DoIP Host:Port → Connect → Start OTA'
    ),
    'OTA：请先加载项目，再填 DoIP Host:Port「连接」': (
        'OTA: load a project first, then DoIP Host:Port → Connect'
    ),
    '项目={name} · 回灌：Host + tcp 端口 →「连接」': 'project={name} · Inject: Host + tcp port → Connect',
    '项目={name} · Live ws / 回灌 tcp →「连接」': 'project={name} · Live ws / Inject tcp → Connect',
    '请先加载项目（与 Live/回灌相同）': 'Load a project first (same as Live/Inject)',
    '请先加载项目，再连接 DoIP': 'Load a project, then connect DoIP',
    '请先连接 DoIP': 'Connect DoIP first',
    '需加载项目': 'Need project',
    '文件': 'File',
    '加载项目目录…': 'Load project folder…',
    '备选：直接选 SKU 目录（等价于该目录下的 project.yaml）': (
        "Alt: pick SKU folder (same as that folder's project.yaml)"
    ),
    '打开 session JSONL…': 'Open session JSONL…',
    '从 SIL 日志录制…': 'Record from SIL logs…',
    '从 tap NDJSON 导入…': 'Import tap NDJSON…',
    '仅跟随 live 文件…': 'Follow live file only…',
    '加载 gf.sor.json…': 'Load gf.sor.json…',
    '导出 MCAP…': 'Export MCAP…',
    '导出 VCD（GTKWave）…': 'Export VCD (GTKWave)…',
    '导出 Graphviz .dot…': 'Export Graphviz .dot…',
    '退出': 'Quit',
    '连接 Live (ws)': 'Connect Live (ws)',
    '断开 Live': 'Disconnect Live',
    '连接回灌 (tcp)': 'Connect Inject (tcp)',
    '断开回灌': 'Disconnect Inject',
    '回放': 'Replay',
    '播放 / 暂停': 'Play / Pause',
    '前进一步': 'Step forward',
    '后退一步': 'Step back',
    '跳到开头': 'Jump to start',
    '跳到末尾': 'Jump to end',
    '打开 Foxglove 回放…': 'Start Foxglove replay…',
    '停止 Foxglove 回放进程': 'Stop Foxglove replay',
    '切换跟随最新': 'Toggle follow latest',
    'Tag': 'Tag',
    '钉标记点 ●': 'Pin mark ●',
    '片段 from ← playhead': 'Range from ← playhead',
    '片段 to ← playhead 并保存': 'Range to ← playhead & save',
    '视图': 'View',
    '⚠ 请先「加载项目…」选择 project.yaml（回灌已禁用；Live 仍可旁观）': (
        '⚠ Load project… (project.yaml) first — Inject disabled; Live still works'
    ),
    '⚠ 请先「加载项目…」选择 project.yaml（回灌 / OTA 已禁用；Live 仍可旁观）': (
        '⚠ Load project… (project.yaml) first — Inject / OTA disabled; Live still works'
    ),
    '项目': 'Project',
    'Wall': 'Wall',
    'Height': 'Height',
    'Order': 'Order',
    'DAG': 'DAG',
    'Vars': 'Graphics',
    'Graphics': 'Graphics',
    'Inject': 'Inject',
    'Available': 'Available',
    'Added': 'Added',
    'Add →': 'Add →',
    '← Remove': '← Remove',
    'Result': 'Result',
    'Note': 'Note',
    'Current: —': 'Current: —',
    'Published': 'Published',
    'Skipped': 'Skipped',
    'Marker': 'Marker',
    'Range': 'Range',
    'Label': 'Label',
    'Type': 'Type',
    'Notes': 'Notes',
    'Save': 'Save',
    'Delete': 'Delete',
    'Jump': 'Jump',
    'Export clip…': 'Export clip…',
    'Pin mark ●': 'Pin mark ●',
    'Follow playhead': 'Follow playhead',
    'Loop at end': 'Loop at end',
    'Order: events by time (Δt). Click to seek; yellow = same t_ns.': (
        'Order: events by time (Δt). Click to seek; yellow = same t_ns.'
    ),
    'DAG: highlight the playhead event. Orange=1 hop; blue+FAN=fan-out.': (
        'DAG: highlight the playhead event. Orange=1 hop; blue+FAN=fan-out.'
    ),
    'Inject via top bar tcp:8767. Follow-playhead drives EgoMotion frames.': (
        'Inject via top bar tcp:8767. Follow-playhead drives EgoMotion frames.'
    ),
    'Marker ● = M; Range ▬ = [ / ].': 'Marker ● = M; Range ▬ = [ / ].',
    'Shrink all rows': 'Shrink all rows',
    'Grow all rows': 'Grow all rows',
    'no samples': 'no samples',
    'out of view — fit row': 'out of view — fit row',
    'Open a session, then ▼ to pick variables': 'Open a session, then ▼ to pick variables',
    'No variables yet — ▼ then Add →': 'No variables yet — ▼ then Add →',
    'Toggle variable picker': 'Toggle variable picker',
    'Inject: disconnected': 'Inject: disconnected',
    'Inject: connected': 'Inject: connected',
    'Inject: connected (playhead)': 'Inject: connected',
    '窗口重载 session_idx≈{idx}（A/B）': 'Window reload session_idx≈{idx} (A/B)',
    '\n（检测到 :8765 已被占用，多半是 SIL live；离线回放改用本端口，勿与 live 混连。）': (
        '\n(:8765 busy — usually SIL live; offline replay uses this port.)'
    ),
    ' 录制': ' recording',
    ' 跟随': ' follow',
    'Inject 已断开': 'Inject disconnected',
    'Inject 已断开 — 播放已停': 'Inject disconnected — playback stopped',
    'Inject 连接已断开': 'Inject connection lost',
    'Inject: 已连接（playhead）— 用下方播放/单步控制灌入': 'Inject: connected (playhead)',
    'Inject: 未连接（请用顶栏连接）': 'Inject: disconnected',
    'Live = tap 旁路 WebSocket（默认 8766）。\n回灌 playhead 时 SIL 默认仍开 live（只订下游）；若连不上请看 run_sil 是否打印 downstream tap。\n回灌控制请用顶栏「回灌 tcp:8767」。': (
        'Live = tap bypass WebSocket (default 8766).\nWith playhead inject SIL still opens live (downstream only).\nInject control: top bar Inject tcp:8767.'
    ),
    'Live 录制': 'Live record',
    'Live 录制已停止': 'Live recording stopped',
    'Live 无项目：仅旁观（动画 DAG 为空）': 'Live without project: observe only (empty DAG)',
    'MVP 仅 EgoMotion': 'MVP: EgoMotion only',
    'MVP 仅灌 EgoMotion，本 topic 跳过': 'MVP injects EgoMotion only; topic skipped',
    'SOR 失败': 'SOR failed',
    'eof — 已停止': 'eof — stopped',
    'eof（未勾选循环）': 'eof (loop unchecked)',
    'inject seek 失败': 'inject seek failed',
    'inject session 重置失败': 'inject session reset failed',
    'to_ns（标记点可留空或同 from）': 'to_ns (empty OK for markers)',
    '不跟播': 'frozen',
    '保存': 'Save',
    '保存 session.jsonl': 'Save session.jsonl',
    '保存为 session.jsonl': 'Save as session.jsonl',
    '先后 / 竞态：按时间列出事件与 Δt（墙钟=方案1锚点）。单击行跳转；同 t_ns 标黄=并发。': (
        'Order: events by time (Δt). Click to seek; yellow = same t_ns.'
    ),
    '删除': 'Delete',
    '加载 gf.sor.json': 'Load gf.sor.json',
    '取消': 'Cancel',
    '回灌 session 不一致': 'Inject session mismatch',
    '回灌「跟 playhead 灌」已开 → Live 跟随已禁用（仍可连 Live 旁观/录制）': (
        'Inject follow-playhead ON → Live follow disabled'
    ),
    '回灌到结尾': 'Inject reached end',
    '回灌失败': 'Inject failed',
    '回灌已连且跟 playhead → Live 跟随已关（可另连 Live 旁观/录制）': (
        'Inject connected + follow playhead → Live follow off'
    ),
    '回灌错误': 'Inject error',
    '回灌需要先加载 project.yaml（SOR / 事件对齐）。\n是否现在打开？': (
        'Inject needs project.yaml first.\nOpen now?'
    ),
    '在 playhead 打一个标记点（热键 M）': 'Drop a marker at playhead (M)',
    '填窗失败': 'Window fill failed',
    '墙钟': 'Wall',
    '备注': 'Notes',
    '导入': 'Import',
    '导入 tap NDJSON': 'Import tap NDJSON',
    '导入失败': 'Import failed',
    '导出': 'Export',
    '导出 Graphviz .dot': 'Export Graphviz .dot',
    '导出 VCD（GTKWave）': 'Export VCD (GTKWave)',
    '导出 clip…': 'Export clip…',
    '导出失败': 'Export failed',
    '将 Live 流落盘；已有 session_live.jsonl 时可新建或覆盖': (
        'Write Live stream to disk; new or overwrite if exists'
    ),
    '尚未加载项目（SOR / 动画 DAG / 变量轨对齐）。\n是否现在打开 project.yaml？\n\n选「否」仍可旁观连接（无 DAG）。': (
        'No project loaded.\nOpen project.yaml now?\n\nNo = observe without DAG.'
    ),
    '已写入': 'Wrote',
    '已到 session 结尾。是否从开头继续循环？': 'End of session. Loop from start?',
    '已加载 SOR': 'Loaded SOR',
    '已加载 clip': 'Loaded clip',
    '已加载 session': 'Loaded session',
    '已加载项目': 'Loaded project',
    '已发布': 'Published',
    '已开「跟 playhead 灌」→ Live 跟随已关': 'Follow-playhead ON → Live follow off',
    '已开回灌 playhead → Live 以旁观方式连接（不跟随最新）': 'Inject playhead ON → Live observe mode',
    '已有 session/回灌 → Live 旁观（不覆盖时间轴）': 'Session/inject open → Live observe',
    '开：时间轴 seek/播放/单步 → inject 发对应帧；关：只保持 TCP 连接': (
        'On: seek/play/step → inject; Off: TCP only'
    ),
    '录制失败': 'Record failed',
    '循环（到结尾确认）': 'Loop at end',
    '循环播放': 'Loop at end',
    '打开 project.yaml': 'Open project.yaml',
    '打开 session JSONL': 'Open session JSONL',
    '打开 session？': 'Open session?',
    '打开失败': 'Open failed',
    '新建': 'New',
    '新建时间戳文件，还是覆盖？': 'New timestamped file, or overwrite?',
    '无 whitelist（全量解析）': 'No whitelist (parse all)',
    '无法写入': 'Cannot write',
    '板端 eof 时弹窗：继续则 seek 0 并清空结果表；停止则保持在结尾': (
        'On eof: confirm → seek 0; stop → stay at end'
    ),
    '播放到结尾自动从 #0 再灌（无限循环）：重置板端 A/B、清空结果表。取消勾选则停在结尾。': (
        'At end, auto-wrap to #0 (infinite): reset board A/B, clear results. Uncheck to stop at end.'
    ),
    '循环：已回到开头': 'Loop: back to start',
    '回灌循环 → #0': 'Inject loop → #0',
    '打开 session JSONL（回灌 / 时间轴权威源；加载项目后常用）': (
        'Open session JSONL (inject / timeline authority; usual after Load project)'
    ),
    '标签': 'Label',
    '标记点 (marker)': 'Marker',
    '标记点 ●：热键 M 在 playhead 钉一下，方便回头找；片段 ▬：热键 [ / ] 定 from/to，可导出 clip。列表显示墙钟（方案 1）。': (
        'Marker ● = M; Range ▬ = [ / ].'
    ),
    '检查日志目录或 record.services / mode=off。': 'Check log dir or record.services / mode=off.',
    '片段 (range)': 'Range',
    '类型': 'Type',
    '跳过': 'Skipped',
    '非可灌 / injected=false': 'not injectable / injected=false',
    '逗号分隔 topic，可选': 'comma-separated topics (optional)',
    '跟 playhead 灌（使用下方播放/单步/滑块）': 'Follow playhead',
    '请先加载 SOR / 项目': 'Load SOR / project first',
    '请先加载 project.yaml 后再连接回灌': 'Load project.yaml before Inject',
    '请先打开 session': 'Open a session first',
    '请先打开 session JSONL（GMT 为权威源）。\nstream 模式下板端不必再设 GF_INJECT_SESSION。': (
        'Open session JSONL first (GMT is authority).'
    ),
    '请确认 GF_INJECT_SESSION 与 GUI 同一文件': 'Ensure GF_INJECT_SESSION matches GUI file',
    '请选 SKU 目录或其 project.yaml（与 gf-config 同一入口）。': 'Pick SKU folder or its project.yaml.',
    '跟随 live': 'Following live',
    '跟随 live session JSONL': 'Follow live session JSONL',
    '跟随文件 OFF': 'Follow file OFF',
    '跟随文件 ON': 'Follow file ON',
    '跟随最新 OFF — playhead 不跟播（可 scrub / Tag）': 'Follow latest OFF',
    '路径不存在': 'Path not found',
    '跳转到': 'Jump to',
    '远端请确认：\n1) SIL 机 GF_INJECT_MODE=playhead，且 ss 能看到 0.0.0.0:8767\n2) 防火墙放行 TCP 8767\n3) 用本页「连接 inject」，不要点上方 Live（那是 ws://8766）': (
        'Remote checklist:\n1) GF_INJECT_MODE=playhead, :8767 listening\n2) Firewall TCP 8767\n3) Use Inject connect, not Live'
    ),
    '连 live_tap 旁路（ws:8766）；默认只看流不落盘，需落盘请点「录制」': 'live_tap bypass (ws:8766); Record to save',
    '连 playhead inject（TCP JSON）；需 GF_INJECT_MODE=playhead': (
        'playhead inject (TCP); needs GF_INJECT_MODE=playhead'
    ),
    '选择 SIL main-chain / iox_*_logs 目录': 'Pick SIL main-chain / iox_*_logs folder',
    '选择项目目录（备选）': 'Pick project folder (alt)',
    '（不跟播）': '(no follow)',
    '（旁观模式未改时间轴）': '(observe mode)',
    '（跟随最新）': '(follow latest)',
    '顶栏连回灌 tcp:8767。stream 模式：GMT 打开的 session 是权威源（板端 A/B 小窗，不必再设 GF_INJECT_SESSION）。\nMVP 仅 Send /gf/EgoMotion：绿=已灌，粉=跳过（如 Trajectory）。「跟 playhead 灌」时会关 Live 跟随。': (
        'Inject via top bar tcp:8767. Follow-playhead drives EgoMotion frames.'
    ),
    '白名单未命中 / Send 失败': 'Whitelist miss / Send failed',
    '覆盖': 'Overwrite',
    '打开项目 SOR 后显示拓扑': 'Open a project SOR to show topology',
    'SOR 无 deployments/dataflows': 'SOR has no deployments/dataflows',
    'UDS 交互': 'UDS traffic',
    '展开/收起 UDS traffic，给 DEM / Collector 表格腾空间': (
        'Expand/collapse UDS traffic to free space for DEM / Collector tables'
    ),
    'DoIP / UDS 过程日志（各模块操作细节都写在这里）': 'DoIP / UDS log (all module steps appear here)',
    'OTA/UDS：共用 DoIP 连接与下方 UDS 日志。上方单选切换 OTA / DEM / Collector 模块。先加载项目 → 连接 → 再操作对应模块。': (
        'OTA/UDS: shared DoIP + UDS log below. Radio switches OTA / DEM / Collector. Load project → Connect → use the module.'
    ),
    'DEM-lite：经 DoIP 读/清 DTC（0x19 / 0x14）。事件环缓请切到 Collector。': (
        'DEM-lite: read/clear DTCs over DoIP (0x19 / 0x14). Event ring → Collector.'
    ),
    '读取 DTC（0x19）': 'Read DTCs (0x19)',
    '清除全部（0x14）': 'Clear all (0x14)',
    '已读取 {n} 条 DTC': 'Read {n} DTCs',
    '0 条 DTC。需 SIL 先产生故障（如 PHM AliveMissed）且 GF_PER_DIR 与 DoIP 共享；也可用 Collector 看事件。': (
        '0 DTCs. Need a SIL PHM fault (e.g. AliveMissed) written to shared GF_PER_DIR; DoIP 0x19 reloads from PER. run_sil+DoIP defaults a short PHM fault on uss.'
    ),
    '未连接时此表为空。顶栏「回灌 tcp」连接后，勾选 Follow playhead 并回放/单步，结果才会出现。': (
        'Table stays empty until Inject is connected. Then enable Follow playhead and play/step to see results.'
    ),
    '未连接 — 连接回灌并回放后才显示结果': 'Disconnected — connect Inject and play/step to see results',
    '确认清除全部 DTC（0x14 0xFFFFFF）？': 'Clear all DTCs (0x14 0xFFFFFF)?',
    '已清除': 'Cleared',
    '请先连接 DoIP，再读取。': 'Connect DoIP first, then read.',
    '需先连接 DoIP；步骤见下方 UDS 日志': 'Connect DoIP first; steps go to the UDS log below',
    '切换到 UDS：点「从 UDS 读取」（先连 DoIP）': 'UDS mode: click Read via UDS (connect DoIP first)',
    '使用已连接的 DoIP：0x31 01 F201 拉取环缓事件': (
        'Uses connected DoIP: 0x31 01 F201 dumps the event ring'
    ),
    'Event Collector：本机 NDJSON（同机 SIL）或 UDS RID F201（板端）。DoIP 在上方连接；UDS 步骤写入下方日志。DTC 请切 DEM。': (
        'Event Collector: local NDJSON (co-located SIL) or UDS RID F201 (board). Connect DoIP above; UDS steps go to the log below. DTCs → DEM.'
    ),
    '项目={name} · OTA/UDS：DoIP 连接后选 OTA / DEM / Collector': (
        'project={name} · OTA/UDS: connect DoIP, then OTA / DEM / Collector'
    ),
    '刷新': 'Refresh',
    '自动刷新': 'Auto-refresh',
    'Logging（DLT）：连接板端/SIL 的 dlt-daemon（标准协议 TCP）。不读 log 文件。也可用 dlt-viewer / dlt-receive。': (
        'Logging (DLT): connect to board/SIL dlt-daemon (standard TCP). '
        'Does not read log files. dlt-viewer / dlt-receive also work.'
    ),
    '过滤 APP/CTX/文本（如 RUNT,Offer）': 'Filter APP/CTX/text (e.g. RUNT,Offer)',
    '自动滚屏': 'Auto-scroll',
    '清空': 'Clear',
    '未连接': 'Disconnected',
    'Logging（DLT）：Host {host} → 连接 dlt-daemon（默认 TCP 3490）': (
        'Logging (DLT): Host {host} → connect dlt-daemon (TCP 3490 default)'
    ),
    'Logging': 'Logging',
    '本机文件': 'Local file',
    'UDS（板端）': 'UDS (board)',
    '从 UDS 读取': 'Read via UDS',
    '使用 OTA/UDS 页已连接的 DoIP：0x31 01 F201 拉取环缓事件': (
        'Uses DoIP from OTA/UDS tab: 0x31 01 F201 dumps the event ring'
    ),
    '需先在 OTA/UDS 连接 DoIP；步骤见该页日志': 'Connect DoIP on OTA/UDS first; steps appear in that log',
    '切换到 UDS：点「从 UDS 读取」（先连 OTA/UDS）': 'UDS mode: click Read via UDS (connect OTA/UDS first)',
    '请先在「OTA/UDS」页连接 DoIP，再回来读取。': 'Connect DoIP on the OTA/UDS tab, then read here.',
    '未连接 DoIP': 'DoIP not connected',
    'UDS 已加载 {n} 条（RID F201）': 'UDS loaded {n} rows (RID F201)',
    '打开 Collector NDJSON': 'Open Collector NDJSON',
    '文件不存在（先跑 SIL / 设置 GF_COLLECTOR_STORE）': (
        'File missing (run SIL first / set GF_COLLECTOR_STORE)'
    ),
    '已加载 {n} 条 · {path}': 'Loaded {n} rows · {path}',
    'Collector：本机 NDJSON 或 UDS RID F201（先连 OTA/UDS）': (
        'Collector: local NDJSON or UDS RID F201 (connect OTA/UDS first)'
    ),
    '项目={name} · OTA/UDS：DoIP Host:Port →「连接」→ Start OTA / 供 Collector 读': (
        'project={name} · OTA/UDS: DoIP Host:Port → Connect → Start OTA / Collector read'
    ),
    'OTA/UDS：请先加载项目，再填 DoIP Host:Port「连接」': (
        'OTA/UDS: load a project, then DoIP Host:Port → Connect'
    ),
    'Event Collector：本机文件（同机 SIL）或经 DoIP/UDS RID F201 从板端拉取。远程时请先在「OTA/UDS」页连接 DoIP；UDS 步骤会写到该页日志。表格列与 NDJSON 一致。DTC 仍用 0x19。': (
        'Event Collector: local file (co-located SIL) or DoIP/UDS RID F201 from board. Remote: connect DoIP on OTA/UDS first; UDS steps go to that log. Same columns as NDJSON. DTC still uses 0x19.'
    ),
    '经 DoIP TCP 驱动板端/SIL 的 UCM（gf_doip_ota_server）。非真刷写；失败事件进 Collector。': (
        'Drive board/SIL UCM over DoIP TCP (gf_doip_ota_server). No real flash; failures → Collector.'
    ),
    'OTA 进行中': 'OTA in progress',
    '运行中…': 'Running…',
    'OTA Activate 成功': 'OTA Activate OK',
    'OTA 序列完成（Activate OK）': 'OTA sequence done (Activate OK)',
    'OTA 序列完成（传输/Activate OK）': 'OTA sequence done (transfer/Activate OK)',
    '传输模式': 'Transfer mode',
    '会话时序': 'Session timing',
    '只读：gf-config → diag.yaml → ota_transfer.mode': (
        'Read-only: gf-config → diag.yaml → ota_transfer.mode'
    ),
    '只读：gf-config → diag.yaml → ota_transfer.mode\n• request_file_transfer = 0x38→0x36→0x37（推荐）\n• request_download = 0x34→0x36→0x37\n• routine_sil = 0x31 F100 捷径（无字节管道）': (
        'Read-only: gf-config → diag.yaml → ota_transfer.mode\n• request_file_transfer = 0x38→0x36→0x37 (recommended)\n• request_download = 0x34→0x36→0x37\n• routine_sil = 0x31 F100 shortcut (no byte pipe)'
    ),
    '只读：diag.yaml timing；0x3E 周期须小于 S3Server': (
        'Read-only: diag.yaml timing; 0x3E period must be < S3Server'
    ),
    '只读：diag.yaml timing。\n连接后 GMT 按 tester_present_period_ms 发 0x3E keep-alive；周期须小于 s3_server_ms。P2* 用作收包超时。': (
        'Read-only: diag.yaml timing.\nAfter connect, GMT sends 0x3E keep-alive at tester_present_period_ms; period must be < s3_server_ms. P2* is the receive timeout.'
    ),
    '按 diag.yaml 传输模式发 UDS（过程写在下方日志）': (
        'Send UDS per diag.yaml transfer mode (steps in the log below)'
    ),
    '按 diag.yaml 传输模式发 UDS（过程写在下方日志）：\n默认 0x10 → 0x27 → 0x38/0x34 → 0x36… → 0x37 → Activate': (
        'Send UDS per diag.yaml transfer mode (steps in the log below):\ndefault 0x10 → 0x27 → 0x38/0x34 → 0x36… → 0x37 → Activate'
    ),
    'DoIP / UDS 过程日志（0x10 → 0x27 → 0x38/0x34 → 0x36 → 0x37）': (
        'DoIP / UDS step log (0x10 → 0x27 → 0x38/0x34 → 0x36 → 0x37)'
    ),
    '断开 DoIP TCP；停止 0x3E keep-alive': 'Disconnect DoIP TCP; stop 0x3E keep-alive',
    '主机侧产物路径。0x38/0x34 模式会按块经 DoIP 下发；SIL 可用 bash scripts/make_sil_swu.sh 生成假包（magic GFSW）。真 RAUC 刷写 → P3z。': (
        'Host-side artifact path. 0x38/0x34 modes stream blocks over DoIP; SIL: bash scripts/make_sil_swu.sh makes a fake package (magic GFSW). Real RAUC flash → P3z.'
    ),
    '配置在 gf-config（diag.yaml）；本页只读跟从传输模式与时序。流程：run_sil（起 DoIP）→ 加载项目 → 连接 → Start OTA。非真刷写；失败进 Collector ota_failed。': (
        'Configure in gf-config (diag.yaml); this page follows mode & timing read-only. Flow: run_sil (starts DoIP) → Load project → Connect → Start OTA. No real flash; failures → Collector ota_failed.'
    ),
    'OTA 失败（见板端 Collector ota_failed）': 'OTA failed (see board Collector ota_failed)',
    'SIL / 板端 DoIP 地址（本机 127.0.0.1；远端填局域网 IP）': (
        'SIL / board DoIP host (127.0.0.1 locally; LAN IP remotely)'
    ),
    'DoIP TCP 端口（默认 13400，与 diag.yaml / GF_DOIP_PORT 一致）': (
        'DoIP TCP port (default 13400; match diag.yaml / GF_DOIP_PORT)'
    ),
    '连 SIL gf_doip_ota_server（需先 run_sil）': (
        'Connect to SIL gf_doip_ota_server (start run_sil first)'
    ),
    '依次发 0x10 → 0x27 → 0x31（过程写在下方日志）': (
        'Send 0x10 → 0x27 → 0x31 (steps appear in the log below)'
    ),
    'DoIP / UDS 过程日志（0x10 → 0x27 → 0x31）': 'DoIP / UDS step log (0x10 → 0x27 → 0x31)',
    'ISO 14229 UDS（父）': 'ISO 14229 UDS (parent)',
    'ISO 13400 DoIP（依赖 14229）': 'ISO 13400 DoIP (requires 14229)',
    '请先勾选 ISO 14229 UDS': 'Enable ISO 14229 UDS first',
    '仅 14229：无 DoIP 远端路径。请用进程内 UDS smoke，或同时勾选 13400。': (
        'UDS-only: no DoIP remote path. Use in-process UDS smoke, or also enable 13400.'
    ),
    'DoIP → UCM（SIL，非真刷写）。ISO 能力只读，来自 gf-config / diag.yaml。': (
        'DoIP → UCM (SIL, no real flash). ISO flags are read-only from gf-config / diag.yaml.'
    ),
    '只读：在 gf-config 诊断页配置': 'Read-only: configure in gf-config Diagnostics',
    '未连接': 'Disconnected',
    '连接中…': 'Connecting…',
    '连接失败': 'Connect failed',
    '连接丢失': 'Connection lost',
    '已连接 {host}:{port}': 'Connected {host}:{port}',
    '请先连接 DoIP（Host:Port 旁「连接」）': 'Connect DoIP first (Connect next to Host:Port)',
    '项目未启用 ISO 14229（请在 gf-config 诊断页打开）': (
        'ISO 14229 is off in the project (enable in gf-config Diagnostics)'
    ),
    '项目未启用 ISO 13400 DoIP（请在 gf-config 诊断页打开）': (
        'ISO 13400 DoIP is off in the project (enable in gf-config Diagnostics)'
    ),
    'ISO 14229 为基础；勾选 ISO 13400 才走 DoIP TCP→UCM（gf_doip_ota_server）。13400 依赖 14229。非真刷写；失败进 Collector。': (
        'ISO 14229 is the base; enable ISO 13400 for DoIP TCP→UCM (gf_doip_ota_server). 13400 requires 14229. No real flash; failures → Collector.'
    ),
    '0x27/0x29 插件': '0x27/0x29 plugin',
    '空=板端用内置 SIL stub；按 OEM 记本地路径': 'empty = board SIL stub; remember OEM path locally',
    '只保存在 GMT 本地设置，不写 diag.yaml。板端/SIL 启动时可用环境变量 GF_DIAG_SEC_PLUGIN 指向同一路径。': (
        'Stored in GMT settings only (not diag.yaml). Board/SIL can use env GF_DIAG_SEC_PLUGIN for the same path.'
    ),
    'UCM 包逻辑名（PackageInfo.id），随 Routine 发给板端；与磁盘上的 Artifact 文件路径分开，便于同一文件换不同包名做 SIL。': (
        'UCM logical package id (PackageInfo.id), sent with the routine; separate from the on-disk Artifact path.'
    ),
    'UCM 包逻辑名（PackageInfo.id）。0x38/0x34 路径随传输元数据下发；routine_sil 随 0x31 发给板端。与磁盘 Artifact 路径分开，便于同一文件换不同包名做 SIL。': (
        'UCM logical package id (PackageInfo.id). Sent with transfer metadata on 0x38/0x34; with 0x31 on routine_sil. Separate from the on-disk Artifact path for SIL renaming.'
    ),
    '选择 OTA 产物文件': 'Select OTA artifact file',
    '软件包 (*.swu *.zip *.bin);;所有文件 (*)': 'Packages (*.swu *.zip *.bin);;All (*)',
    '浏览…': 'Browse…',
    '选择 0x27/0x29 安全插件（.so / .dll）': 'Select 0x27/0x29 security plugin (.so / .dll)',
    '动态库 (*.so *.dll);;所有文件 (*)': 'Libraries (*.so *.dll);;All (*)',
    '已存在 {name}（{n} 字节）。\n新建时间戳文件，还是覆盖？': (
        'File {name} already exists ({n} bytes).\nNew timestamped file, or overwrite?'
    ),
    'stream session/reset 失败：{exc}': 'stream session/reset failed: {exc}',
    '\n⚠ 事件数不一致：inject={n_inj} GUI={n_gui}（请用同一 session）': (
        '\n⚠ event count mismatch: inject={n_inj} GUI={n_gui} (use same session)'
    ),
    'inject 侧事件数 = {n_inj}，GMT 当前 session = {n_gui}。\n\n': (
        'inject events = {n_inj}, GMT session = {n_gui}.\n\n'
    ),
    '超出 session（{err}）': 'past session end ({err})',
    '超出 inject session（{err}）— ': 'past inject session ({err}) — ',
    '跳过 #{index} {topic}（MVP 仅 EgoMotion）': 'skip #{index} {topic} (MVP EgoMotion only)',
    '{dir}\n下未找到 project.yaml\n请选 SKU 目录或其 project.yaml（与 gf-config 同一入口）。': (
        '{dir}\nproject.yaml not found\nPick SKU folder or its project.yaml.'
    ),
    '请选择 project.yaml，而不是：\n{name}': (
        'Select project.yaml, not:\n{name}'
    ),
    '未找到 {sor}\n请先在 gf-config Verify / Compose。': (
        'Missing {sor}\nRun gf-config Verify / Compose first.'
    ),
    '项目={dir}（无 SOR）': 'project={dir} (no SOR)',
    '发现 {cand}\n是否加载？（也可先 run_sil 再 GUI「连接」）': (
        'Found {cand}\nLoad it? (or run_sil then Connect)'
    ),
    '写入 {path}\n事件数=0\n({note})\n检查日志目录或 record.services / mode=off。': (
        'Wrote {path}\nevents=0\n({note})\nCheck log dir or record.services / mode=off.'
    ),
    '写入 {path}\n事件数={n}\n{note}': (
        'Wrote {path}\nevents={n}\n{note}'
    ),
    '写入 {path}\n事件数={n}': (
        'Wrote {path}\nevents={n}'
    ),
    '已写入 {path}\nvars={n_vars} events={n_ev}\n打开：gtkwave {path}': (
        'Wrote {path}\nvars={n_vars} events={n_ev}\nOpen: gtkwave {path}'
    ),
    '进程已退出（码 {code}）。\n检查端口 {port} 是否被占用，或用 CLI 调试。': (
        'Process exited (code {code}).\nCheck port {port} or debug via CLI.'
    ),
    '已启动 WS 回放：ws://127.0.0.1:{port}\n': (
        'WS replay started: ws://127.0.0.1:{port}\n'
    ),
    'Foxglove 回放已启动 ws://127.0.0.1:{port}': 'Foxglove replay started ws://127.0.0.1:{port}',
    '无 session（先打开或跟随 live）': 'No session (open or follow live first)',
    '无 playhead': 'No playhead',
    '● 标记 {label} @ {t_ns} → {path}': '● marker {label} @ {t_ns} → {path}',
    '无 session': 'No session',
    '▬ 片段 {label} [{a}…{b}] → {path}': '▬ range {label} [{a}…{b}] → {path}',
    '先选中一个标记/片段': 'Select a marker/range first',
    '该条目没有时间点': 'Entry has no timestamp',
    '标记': 'Marker',
    'from_ns / to_ns 必须是整数': 'from_ns / to_ns must be integers',
    '已保存 {path}': 'Saved {path}',
    '无 playhead（先加载并 scrub session）': 'No playhead (load and scrub session first)',
    '片段需要 from_ns 与 to_ns': 'Range needs from_ns and to_ns',
    '已写入 {path}\nkept={kept}/{total}\n是否加载到时间轴？': (
        'Wrote {path}\nkept={kept}/{total}\nLoad onto timeline?'
    ),
    '当前 session 暂无此字段（曾出现过，仍可添加/保留）': (
        'Field absent in current session (seen before; still addable)'
    ),
    'inject ctrl hello timeout @ {host}:{port}\n请确认：GF_INJECT_MODE=playhead、端口 8767（TCP）、防火墙放行；\n不要用上方 Live 的 ws://8766。': (
        'inject ctrl hello timeout @ {host}:{port}\nCheck: GF_INJECT_MODE=playhead, TCP 8767, firewall;\nDo not use Live ws://8766 above.'
    ),
    '▬ from={t_ns} → {label}': '▬ from={t_ns} → {label}',
    '当前是标记点 ●，不是时间窗。\n请把类型改成「片段」并填 from/to，或用 [ / ] 定窗后再导出。': (
        'This is a marker ●, not a time window.\nChange type to Range and set from/to, or use [ / ] then export.'
    ),
    'Foxglove Studio → Open connection。': 'Foxglove Studio → Open connection.',
}

_ZH: dict[str, str] = {
    'Wall': '时间',
    'Height': '行高',
    'Order': '先后',
    'DAG': 'DAG',
    'Vars': '图形',
    'Graphics': '图形',
    'Zoom': '缩放',
    'Zoom in (time)': '时间放大',
    'Zoom out (time)': '时间缩小',
    'Fit': '适应',
    'Fit all signals in view': '适应全部信号时窗',
    'Inject': '回灌',
    'OTA': 'OTA',
    'OTA/UDS': 'OTA/UDS',
    'DEM': 'DEM',
    'Collector': 'Collector',
    'Logging': 'Logging',
    'status_mask': 'status_mask',
    'Store': 'Store',
    'DoIP Host': 'DoIP Host',
    'DoIP Port': 'DoIP Port',
    'Package id': 'Package id',
    'Artifact path': 'Artifact path',
    'Start OTA': 'Start OTA',
    'require ProgrammingSession': 'require ProgrammingSession',
    'require SecurityAccess': 'require SecurityAccess',
    'ISO 14229': 'ISO 14229',
    'ISO 13400 DoIP': 'ISO 13400 DoIP',
    'Standards': 'Standards',
    'Host:Port': 'Host:Port',
    'Available': '可选',
    'Added': '已选',
    'Add →': '添加 →',
    '← Remove': '← 移除',
    'Result': '结果',
    'Note': '说明',
    'Current: —': '当前：—',
    'Published': '已发布',
    'Skipped': '跳过',
    'Marker': '标记',
    'Range': '片段',
    'Label': '标签',
    'Type': '类型',
    'Notes': '备注',
    'Save': '保存',
    'Delete': '删除',
    'Jump': '跳转',
    'Export clip…': '导出 clip…',
    'Pin mark ●': '钉标记 ●',
    'Follow playhead': '跟 playhead 灌',
    'Loop at end': '循环播放',
    'Order: events by time (Δt). Click to seek; yellow = same t_ns.': (
        '按时间列出事件与 Δt。单击跳转；同 t_ns 标黄。'
    ),
    'DAG: highlight the playhead event. Orange=1 hop; blue+FAN=fan-out.': (
        '只点亮当前 playhead 事件。橙=单跳；蓝+FAN=fan-out。'
    ),
    'Inject via top bar tcp:8767. Follow-playhead drives EgoMotion frames.': (
        '顶栏回灌 tcp:8767。跟 playhead 灌 EgoMotion。'
    ),
    'Marker ● = M; Range ▬ = [ / ].': '标记 ● = M；片段 ▬ = [ / ]。',
    'Shrink all rows': '整体变矮',
    'Grow all rows': '整体变高',
    'no samples': '无样本',
    'out of view — fit row': '不在时窗内',
    'Open a session, then ▼ to pick variables': '先打开 session，再点 ▼ 选变量',
    'No variables yet — ▼ then Add →': '尚未添加变量 — ▼ 后「添加 →」',
    'Toggle variable picker': '展开 / 收起选变量',
    'Inject: disconnected': 'Inject: 未连接',
    'Inject: connected': 'Inject: 已连接',
    'Inject: connected (playhead)': 'Inject: 已连接',
    '窗口重载 session_idx≈{idx}（A/B）': '窗口重载 session_idx≈{idx}（A/B）',
}


def get_language() -> str:
    return _LANG


def load_language() -> str:
    global _LANG
    try:
        from PySide6.QtCore import QSettings

        raw = str(QSettings(_ORG, _APP).value("ui/language", "zh"))
    except Exception:
        raw = "zh"
    _LANG = "en" if raw == "en" else "zh"
    return _LANG


def save_language(lang: str) -> None:
    global _LANG
    _LANG = "en" if lang == "en" else "zh"
    try:
        from PySide6.QtCore import QSettings

        QSettings(_ORG, _APP).setValue("ui/language", _LANG)
    except Exception:
        pass


def t(key: str) -> str:
    if _LANG == "en":
        return _EN.get(key, key)
    return _ZH.get(key, key)


def switch_language_and_restart(lang: str) -> None:
    from PySide6.QtCore import QProcess
    from PySide6.QtWidgets import QApplication, QMessageBox

    save_language(lang)
    QMessageBox.information(
        None,
        t("语言"),
        t("正在切换语言并重启应用…"),
    )
    QProcess.startDetached(sys.executable, sys.argv)
    app = QApplication.instance()
    if app is not None:
        app.quit()
