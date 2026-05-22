# Web 控制面板设计

日期:2026-05-21

## 目标

给 ICBC 自动预约工具加一个图形界面,让用户不碰命令行就能完成全部操作:编辑配置、启停监控、查看实时状态和日志。

**约束(用户明确提出)**

- 跨平台:Windows / macOS / Linux 都能跑。
- 让用户尽量少折腾:不新增任何 `pip install` 依赖。

## 方案选型

界面形式选了**本地网页控制面板**:`webui.py` 用 Python 标准库 `http.server` 起一个只绑定 `127.0.0.1` 的本地服务,前端是浏览器里的单页应用。

- 浏览器每个系统都有,跨平台最稳。
- Tkinter 在 Linux 上常需额外装 `python3-tk`,终端 TUI 的 `curses` 在 Windows 上不原生支持——两者都有隐藏安装摩擦,故排除。
- 用标准库 `http.server` 而非 Flask,做到**零新依赖**。

技术方案:标准库后端 + 静态前端文件(非 Flask、非单文件内嵌)。

## 架构与文件

### 新增文件

- `webui.py` — 本地服务器。用 `http.server.ThreadingHTTPServer`,做两件事:① 提供 `webui/` 里的静态前端;② 提供 `/api/*` 的 JSON 接口。启动时用 `webbrowser.open()` 自动弹出浏览器。
- `webui/index.html` — 前端单页面板的 HTML。
- `webui/app.js` — 前端逻辑(fetch 调接口、轮询、渲染)。
- `webui/style.css` — 样式。

### 复用现有代码(不重写)

- `configure.py` — `webui.py` 直接 import 其纯函数 `read_lines` / `write_lines` / `get_value` / `set_value` / `_find` / `ensure_config_exists` / `readiness_issues`,用来读写 `config.yml`,保留注释和引号风格。`configure.py` 的交互式 `main()` 只在 `__main__` 下运行,不受影响,仍可作为命令行后备。
- `road.py` — 由 `webui.py` 以子进程方式启动(`python3 road.py config.yml`),其 stdout 被捕获供面板显示。`road.py` 自身不改动。
- 状态文件(`booking_status.json`、`last_run.txt`、日志)由 `webui.py` 直接读取。

### 数据流

```
浏览器 ──HTTP──> webui.py ──┬── 读/写 config.yml   (借 configure.py 的函数)
  ▲                          ├── 启/停 road.py 子进程
  └──轮询 /api/status────────┴── 读 booking_status.json / last_run.txt / 日志
```

### 安全边界

服务器只绑定 `127.0.0.1`,不对外暴露。`config.yml` 含驾照号和 Gmail 应用密码,绑定本地即为安全边界,不再额外做登录认证。

## UI 布局

采用**分标签页**布局。

```
┌─────────────────────────────────────────────┐
│ 🚗 ICBC 自动预约控制面板        ● 监控中      │  顶栏:标题 + 监控状态指示
├─────────────────────────────────────────────┤
│ [ 监控 ]   [ 配置 ]                          │  两个标签
├─────────────────────────────────────────────┤
│ (监控标签)                                    │
│  状态:预约状态 / 上次运行 / 日志摘要          │
│  [启动监控] [停止监控]                        │
│  小字提示:关闭面板程序会同时停止监控          │
│  ┌─ 实时输出 ───────────────────────────┐   │
│  │ road.py 的滚动输出,每 2-3 秒刷新       │   │
│  └────────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

- **顶栏**:标题 + 监控运行状态指示点(绿=运行中 / 灰=已停止)。
- **监控标签**:状态卡(预约状态、上次运行时间、日志摘要的错误/警告/无名额计数)、启动/停止按钮、实时输出区。
- **配置标签**:按 section 分组的表单(ICBC 账户 / 日期时间 / Gmail / 自动预约 / 通知 / 高级),含保存按钮,顶部显示就绪检查警告(哪些必填项还没填)。

## 后端接口

全部走 `127.0.0.1`。

| 方法 + 路径 | 作用 |
|---|---|
| `GET /` `/app.js` `/style.css` | 返回静态前端文件 |
| `GET /api/config` | 读 `config.yml`,返回各字段 JSON,附就绪检查结果 |
| `POST /api/config` | 保存改动字段(走 `configure.set_value` 的行级写入,保留注释/引号) |
| `POST /api/monitor/start` | 启动 `road.py` 子进程;若已在跑则忽略 |
| `POST /api/monitor/stop` | 停止该子进程 |
| `GET /api/status` | 监控是否在跑 + `pid` + `booking_status.json` + `last_run.txt` + 日志摘要 |
| `GET /api/console` | `road.py` 最近的输出行 |

### 配置字段清单

`webui.py` 与前端共享一份字段清单(section、key、标签、类型:文本/布尔/日期/整数),来源对应 `configure.py` 已覆盖的字段:`icbc`、`gmail`、`autoBooking`、`pushdeer`、`ntfy`、`pushsms`、`pushsound`、`pushlocal`,以及顶层的 `pauseTimeMin`、`skip0Clock`、`data_directory` 和 `requestLimit`。

- `GET /api/config`:读 lines,对每个字段调 `get_value` 取值,返回 JSON。
- `POST /api/config`:收到改动字段的 JSON,对每个字段调 `set_value`,再 `write_lines` 写回。

## 进程管理

`webui.py` 管理单个 `road.py` 子进程。

- 用 `subprocess.Popen([sys.executable, 'road.py', 'config.yml'], stdout=PIPE, stderr=STDOUT)` 启动。用 `sys.executable` 而非硬编码 `python3`,保证在 Windows(那里通常是 `python`)上也能正确调用当前 Python 解释器。
- 一个后台线程持续读子进程 stdout,逐行存入内存环形缓冲 `collections.deque(maxlen=500)`;`/api/console` 返回该缓冲内容。
- 启动:若进程已在跑(`popen.poll()` 为 `None`)则忽略请求。
- 停止:先 `terminate()`,等待数秒;未退出再 `kill()`。
- 监控状态:`popen.poll()` 为 `None` 表示运行中。
- `road.py` 成功预约后会自行退出 → `webui.py` 的 `poll()` 检测到进程结束,面板状态转为"已停止",并展示 `booking_status.json` 中的成功结果。

### 关闭面板即停止监控

`webui.py` 进程退出(终端 Ctrl+C)时,若 `road.py` 子进程仍在跑,会先打印 `⏹ 正在停止监控...` 再将其终止,避免留下用户察觉不到的孤儿进程。

为让这个连锁反应对用户透明,设三处提示:

1. **启动时终端提示** — `webui.py` 启动即打印:`ℹ️ 注意:停止此面板程序(Ctrl+C)会一并停止正在运行的监控`。
2. **浏览器内常驻提示** — 监控运行时,「监控」标签页启停按钮旁显示小字:`关闭面板程序会同时停止监控(仅关浏览器标签页不影响,服务仍在后台)`。
3. **退出时可见** — Ctrl+C 退出时打印 `⏹ 正在停止监控...` 后再终止子进程。

说明:此处"关面板"指关闭 `webui.py` 程序本身;仅关闭浏览器标签页不会停止监控,服务仍在后台运行。提示语会写明这一区别。

## 前端刷新

「监控」标签页打开时,前端每 2-3 秒轮询一次 `/api/status` 和 `/api/console`,实现"实时"效果。切到「配置」标签页时停止轮询。

## 整合与边界情况

- **跨平台入口**:`webui.py` 本身是跨平台入口,任意系统上 `python3 webui.py`(Windows 上 `python webui.py`)即可。`start.sh` 仅为 Linux/macOS 提供便捷封装。
- **start.sh** 新增菜单项 `5. 🖥️ 打开控制面板 (web UI)` → 执行 `python3 webui.py`;原有选项 1-4 保留,提示文案中的选择范围相应更新。
- **首次运行**:`webui.py` 启动时调用 `configure.ensure_config_exists()`,保证 `config.yml` 存在(缺失则从 `config.example.yml` 复制),使配置表单首次运行即可用。
- **端口**:默认用固定端口 `8787`;若被占用则自动 +1 重试若干次,最终地址打印到终端并用于 `webbrowser.open()`。
- **状态文件路径**:按 `config.yml` 的 `data_directory`(默认 `./log`)解析 `booking_status.json` / `last_run.txt` / 日志路径,与 `road.py` 的 `get_data_file_path` 行为一致。
- **依赖检查**:`webui.py` 启动时沿用 `start.sh` 的依赖检查思路;若缺包,在终端提示 `pip3 install -r requirements.txt`。

## 不做的事(YAGNI)

- 不做登录/认证(本地绑定即边界)。
- 不做多用户、多 `road.py` 实例。
- 不做 WebSocket / SSE,用简单轮询即可。
- 不做打包成单可执行文件(PyInstaller 等);保持 `python3 webui.py` 启动方式。
- 不重写 `configure.py` 或 `road.py`,仅复用与最小整合。

## 测试方式

- **后端单元**:`config.yml` 读写往返(改值后 PyYAML 能正确解析、注释保留);端口占用时的重试逻辑。
- **进程管理**:用一个短命的假脚本代替 `road.py`,验证 start / stop / 状态检测 / stdout 捕获 / 退出时清理子进程。
- **接口**:对每个 `/api/*` 端点做 HTTP 级测试(起服务器、发请求、校验响应)。
- **手动**:在浏览器里完整走一遍——编辑配置并保存、启动监控看实时输出、停止、Ctrl+C 退出确认子进程被清理。
