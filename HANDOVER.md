# SlimPDF 交接文档

> 供新会话/新成员快速对接。日常必读内容在前；已完成任务的审计记录统一归档在文末「⛔ 停止标识」之后，按时间倒序排列。

---

## 一、项目现状（2026-08-31 第六次更新）

- **产品**：SlimPDF —— 本地 PDF 压缩桌面应用（Flask + Ghostscript + PyInstaller 打包），Web UI 绑定 127.0.0.1，单用户使用。当前版本 **1.1.2**（`__version__.py`）。
- **主分支状态**：核心压缩链路（上传 → 压缩 → SSE 进度 → 下载）已通过全量修复与真实 Ghostscript 端到端验证；2026-08-30 完成安全加固（归档②）与测试补齐 + SSE 结构化重构（归档①）；2026-08-31 修复 Windows onefile 空壳历史缺陷并重发版（归档：空壳修复）；随后完成分发体验优化（窗口模式 + 应用图标 + 首次运行指引，发版 1.1.2，见文末最新归档）。
- **国际化**：前端已接入 zh/en 双语切换；SSE 进度消息已结构化（后端 `meta` 字段，前端优先用 key 映射，英文正则仅作兼容兑底）。
- **测试**：`pytest` 61/61 通过（新增 test_engine_flow.py 11 例 + test_task_manager.py 7 例，原缺口已补齐）；`mypy`（strict）全量通过（13 文件）。
- **CI**：test 门禁为 Python 3.10/3.11/3.12/3.13 矩阵；release job 仅稳定 tag 触发（含 `-` 的预发布 tag 只跑构建不发 Release）；依赖统一从 `requirements.lock` 安装（已审计无已知 CVE）。

## 二、待办事项

- [x] ~~Windows arm64 CI job 未经真实 tag 触发验证~~ ✅ 已完成：`v1.1.0-rc.3` 全绿（test 3.10-3.13 + macOS + x64 + arm64），release job 正确跳过；正式发版打稳定 tag `v1.1.0` 即可

## 三、环境陷阱（必读）

1. **gs ≥ 9.50 默认 SAFER 沙箱**：PostScript `file` 操作符读任意路径会报 `/invalidfileaccess`，必须用 `--permit-file-read=<路径>` 显式授权（`_get_total_pages` 已处理，新增 gs 调用时注意）。
2. **gs 进度输出在 stdout 不在 stderr**：`Page N` / `Processing pages` 均打印到 stdout（本机 gs 10.07.1 实验证实，stderr 为空）。
3. **Popen 双管道只读一个会死锁**：不读的管道缓冲填满（macOS 64KB）后 gs 阻塞；engine.py 现用 `stderr=STDOUT` 单管道 + 后台线程排空。
4. **Werkzeug 3.1+ 测试上传文件字段必须用 `BytesIO` 包装**，裸 `bytes` 不再被识别为文件（表现为 `request.files` 为空 → 返回 NO_FILE）。
5. **Flask `request.get_json()` 对空对象 `{}` 判 falsy**：用 `get_json(silent=True)` + `is None` 判断，否则空 JSON 走错分支。
6. **macOS Monterey+ 5000 端口被 AirPlay Receiver 占用**：可用 `SLIMPDF_PORT` 环境变量换端口。
7. **本地 `vendor/ghostscript/mac/gs` 若存在会优先于系统 PATH 被找到**：mock `find_ghostscript` 相关测试时须先 monkeypatch `config.GS_PATHS`。
8. **build.spec 用 `SPECPATH` 取项目根目录**，不要改回 `os.getcwd()`。
9. **health 探测有模块级缓存**（成功永久缓存、失败 30s TTL）：测试 health 时必须先 monkeypatch 重置 `routes.health._probe_cache` 与 `_probe_failed_at`（参考 tests/test_health.py 的 fixture）。
10. **版本号只改 `__version__.py` 一处**：pyproject（dynamic attr）、build.spec（exec 读取）、config.VERSION、health 接口、页面 data 属性均自动跟随。
11. **上传上限只改 `config.MAX_UPLOAD_MB` 一处**：后端限制、413 文案、HTML 提示、JS 校验均由模板注入（body data-* 属性）派生。
12. **CSRF 防护基于自定义头**：所有状态变更请求（POST）必须携带 `X-Requested-With: XMLHttpRequest`，否则 403 `CSRF_REJECTED`。用 curl/测试客户端手工调 POST 接口、或新增 POST 路由的测试时必须带此头；新增前端 fetch 调用记得合入 `API_HEADERS`。
13. **上传/压缩接口有限流**（默认 60/20 次每分钟每 IP，超限 429 `RATE_LIMITED`）：限流器是模块级单例（`routes.upload._upload_limiter` / `routes.compress._compress_limiter`），高频调用同接口的测试须先 monkeypatch 替换（参考 tests/test_security.py fixture）。
14. **安全审计日志走 `slimpdf.security` logger**：CSRF 拒绝、限流命中、非法 file_id/task_id、非法扩展名/魔数上传、非回环绑定均记录于此；排查异常行为时按该 logger 名过滤。
15. **Linux frozen 数据目录已改为 XDG 规范**（`$XDG_DATA_HOME/SlimPDF` 或 `~/.local/share/SlimPDF`，替代旧 `~/.pdf-compressor`）；CI 从未发布 Linux 包，无存量迁移负担。
16. **SSE 进度事件带 `meta` 结构字段**（`{"key": analyzing|processing|page|complete}`，page 附 `current`/`total`）：前端 `localizeProgressMessage` 优先用 meta，英文 `message` 仅作兼容兑底；新增进度阶段时必须同时产出 meta，并在前端 `META_KEY_TO_LOCALE` 登记。
17. **`compress_pdf` 进度回调为三参** `(progress, message, meta=None)`：mock 该回调的测试/代码需用 `lambda p, m, meta=None` 签名；预发布 tag（含 `-`）不会触发 release job。
18. **windows-11-arm runner 上 x64 仿真安装器会无限挂起**：`choco install`（rc.1 实测 >25 分钟）与官方安装包 `gs10071w64.exe` 的 `/S` 静默安装（rc.2 实测 >20 分钟）均挂起，而同一脚本在 x64 上约 2 分钟。最终方案（`b51234c`）：用 runner 预装的 `C:\Program Files\7-Zip\7z.exe` 直接解包自解压安装包，从 `bin/` 拷出 `gswin64c.exe`/dll/lib，完全不执行安装程序；**已验证**：`v1.1.0-rc.3` 全绿（七项 job 全过，release 正确跳过）。arm64 job 里不要再引入任何安装器型依赖。
19. **PyInstaller 的 `EXE(...)` 只从位置参数收集打包内容**：`binaries`/`zipfiles`/`datas` 若以 `**kwargs` 传入会被**静默忽略**，产出仅剩引导器的空壳 exe（v1.0.0〜v1.1.0 的 Windows 产物均为此类，约 0.3MB；用 `pyi-archive_viewer --brief` 可见 PKG 内无条目）。`build.spec` 已改为位置参数传参（陷阱来源：本地 6.22.2 二分复现）。macOS 用 COLLECT 不受影响；发布前必须核对产物体积（Windows onefile 预期 ≥10MB）。
20. **Windows 打包为窗口模式（`console=False`）后 `sys.stdout`/`sys.stderr` 为 None**：任何 `print()` 或默认 `logging.StreamHandler()` 都会在启动时崩溃；`app.py` 已改为仅在 `sys.stderr is not None` 时加 StreamHandler、空时兼底 `NullHandler`，启动横幅改走 `logger.info`。产物未签名：Windows 首次运行有 SmartScreen 提示、macOS 有 Gatekeeper 拦截，放行步骤已写入两份 README 的「首次运行指引」。

## 四、代码索引

| 文件 | 职责 | 关键点 |
|------|------|--------|
| `app.py` | 入口，create_app + 主程序块 | 413/429 JSON 错误处理器；CSRF before_request 钩子；安全响应头 after_request（CSP/nosniff/X-Frame-Options/Referrer-Policy）；启动清理残留 + atexit 清理；非回环绑定告警；frozen 模式日志落盘 APP_DIR/logs（RotatingFileHandler 1MB×3） |
| `security.py` | 安全中间件 | `check_csrf`（自定义头防护）、`RateLimiter`（固定窗口、线程安全）、`security_logger` 审计日志、`reject_rate_limited` 429 构造 |
| `config.py` | 全局配置，frozen/开发双环境路径 | `SLIMPDF_HOST`/`SLIMPDF_PORT` 环境变量；`VERSION`（源自 \_\_version\_\_.py）；`MAX_UPLOAD_MB` 单一来源；`RATE_LIMIT_*` 限流参数；`ensure_private_dir`（POSIX 0o700）；Linux XDG 数据目录 |
| `__version__.py` | 版本号唯一来源 | pyproject dynamic + build.spec exec + config 均读此处 |
| `utils.py` | 后端共享工具 | `format_size` 唯一后端实现 |
| `routes/upload.py` | POST /api/upload | 扩展名白名单 + `%PDF-` magic bytes 双重校验；拒绝事件写审计日志；限流 60 次/分钟 |
| `routes/compress.py` | /api/compress、/api/progress(SSE)、/api/download | `_UUID_RE` 同时校验 file_id 与 task_id（progress/download 也防路径穿越）；SSE 硬截止时间 + 15s 心跳；限流 20 次/分钟 |
| `routes/health.py` | /api/health | 探测结果缓存（成功永久、失败 30s TTL）；返回应用版本号 |
| `compress/engine.py` | Ghostscript 调用核心 | 单管道 + `_drain_output` 线程；路径校验分离；`--permit-file-read`；页数探测显式 `-dSAFER`；子进程解码 `errors="replace"`；进度回调三参带 `meta`（含回退原文件分支） |
| `compress/task_manager.py` | 任务字典 + 线程池(4) + 清理线程 | 清理跳过 PENDING/PROCESSING，僵死任务宽限期 = 清理时长 + 压缩超时；`stage_meta` 随 to_dict 导出 |
| `compress/profiles.py` | low/medium/high 三档 gs 参数 | 纯数据 |
| `static/js/app.js` | 前端逻辑 | i18n 运行时；`API_HEADERS`（X-Requested-With）随所有 fetch；`RATE_LIMITED`/`CSRF_REJECTED` 错误码映射；`META_KEY_TO_LOCALE` 优先、正则兑底的 SSE 本地化 |
| `static/locales/zh.json`、`en.json` | 双语语言包 | key 集合必须保持一致；含 `errors.rateLimited` |
| `templates/index.html` | 页面结构 | 文案元素均挂 `data-i18n`/`data-i18n-title`；body data-* 注入后端配置 |
| `requirements.lock` | 锁定依赖版本 | CI 全部 job 从此安装；已审计无已知 CVE（Flask 3.1.3/Werkzeug 3.1.8/Jinja2 3.1.6） |
| `tests/` | 61 个用例 | 全部 tmp_path/monkeypatch 隔离；覆盖安全（test_security）、引擎主流程（test_engine_flow，FakePopen 全 mock）、任务管理（test_task_manager） |

## 五、常用命令

```bash
python3 -m pytest                 # 全量测试（31 用例）
python3 -m mypy                   # 类型检查（strict，files 已在 pyproject 配置）
python3 app.py                    # 本地运行（默认 127.0.0.1:5000）
SLIMPDF_PORT=5050 python3 app.py  # 换端口运行
bash scripts/build_mac.sh         # 本地打包 macOS
```

---

# ⛔ 停止标识

> 以下为历史归档，可在 token 清理时安全截断。按时间倒序排列（最新在前）。

---

## ✅ 已完成：2026-08-31 分发体验优化：窗口模式 + 图标 + 首次运行指引（v1.1.2）

### 需求背景（原始记录）

- 用户询问“别人直接下载安装就能用吗？”——结论：基本可用但有两道门槛：Windows SmartScreen（未签名）与 macOS Gatekeeper（未签名/未公证）；另 Windows 产物带黑色控制台窗口（`console=True`）、无应用图标。
- 用户决策：付费方案（代码签名/公证）暂不做，只做零成本改进 + 友好指引。

### 实施内容（逐文件）

- `build.spec`：`console=True` → `console=False`（窗口模式）；从 `static/images/logo.png` 生成 `logo.ico`（PIL 多尺寸 16〜256）与 `logo.icns`（sips + iconutil），分别接入 Windows `EXE icon=` 与 macOS `BUNDLE icon=`（均带文件存在性保护）。
- `app.py`（窗口模式防崩）：`_setup_logging()` 仅在 `sys.stderr is not None` 时添加 StreamHandler，无任何 handler 时兼底 `NullHandler`；启动横幅 6 行 `print()` 改为单条 `logger.info`（frozen 模式日志落盘 APP_DIR/logs）。
- `README.md` / `README.en.md`：新增「首次运行指引（只需一次）」——SmartScreen「更多信息 → 仍要运行」、Gatekeeper「右键 → 打开」及「隐私与安全性 → 仍要打开」，并说明离线/开源背景消除用户顾虑。
- `__version__.py`：1.1.1 → 1.1.2（产物形态变化，需重新发版）。
- 签名类方案（Apple 开发者 $99/年、Windows OV 证书）已在对话中向用户说明，待其后续决策。

### 验证结果（原始记录）

- `pytest` 61/61；`mypy` strict Success（13 文件）；本机构建 macOS 分支成功且 `dist/SlimPDF.app/Contents/Resources/logo.icns` 已嵌入。
- 待确认：`v1.1.2` 流水线全绿、产物体积正常（≥10MB）、CI 日志出现 `Copying icons from ...logo.ico`。

### 未处理遗留

- 代码签名/公证（付费）待用户决策；未做前用户需按 README 首次运行指引手动放行。

---

## ✅ 已完成：2026-08-31 Windows onefile 空壳缺陷修复与重发版（v1.1.1）

### 需求与发现过程

- 用户报告 `git push origin v1.1.0` 超时（网络抖动，重试后成功）；v1.1.0 流水线全绿并发出 Release，但例行核对发现产物异常：`SlimPDF-Windows-x64.exe`/`-arm64.exe` 仅 0.3MB（macOS dmg 17.1MB 正常）。
- 解剖：`file` 显示 PE32+ console 可执行；`strings`/`xxd` 确认只有引导器（尾邻 `python312.dll`，无 CArchive cookie）；`pyi-archive_viewer --brief` 显示 PKG 内除 `pyi-contents-directory _internal` 选项外无任何条目。
- 拉取 CI 日志（钥匙串 GitHub 凭据）：Analysis/PYZ 均正常（flask/werkzeug 已入图、python312.dll 已收集），但 `Building PKG (CArchive)` 仅耗时约 1ms → TOC 为空；rc.3 的 x64 与 arm64 同样症状。
- 历史回溯：v1.0.0 的 `PDFCompressor.exe` 同为 0.34MB → 确认是从未好过的历史缺陷（此前下载量 0 未被发现）；macOS 用 COLLECT（onedir）不受影响。
- 本地复现二分（PyInstaller 6.22.2，与 CI 同版本）：位置参数传 `a.binaries/a.zipfiles/a.datas` → 12MB 正常；`exe_options` dict + `EXE(**exe_options)` kwargs 传参 → 107KB 空壳；`cipher` 参数非原因。源码确认：`EXE.__init__` 仅遍历 `*args` 收集内容，`kwargs.get` 列表里没有 binaries/zipfiles/datas。

### 修复内容（逐文件）

- `build.spec`：Windows/Linux 分支改为 `EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [], **exe_options)`（位置参数）；移除已废弃的 `block_cipher`/`cipher=` 参数；加注释警示勿改回 kwargs。
- `__version__.py`：1.1.0 → 1.1.1。
- 发布处置：删除远端 `v1.1.0` tag 与对应 Release（产物全部损坏且下载量 0），改发 `v1.1.1`。

### 验证结果

- 本地用 `platform.system` 补丁模拟 Windows 分支跑修复后的 `build.spec`：PKG 构建 1.8s、产物 12.1MB（本地无 gs 供应商目录故未含 gs，实机含 gs 约 40MB）；空壳时 PKG 仅 1ms。
- **`v1.1.1` 流水线全绿**（run 33349239640）：Release 三产物体积正常——macOS dmg 17.1MB、Windows-x64.exe **26.0MB**、Windows-arm64.exe **25.9MB**（空壳时代为 0.3MB）；CI 日志确认 PKG 构建耗时 5.15s（空壳时 1ms）。远端 `v1.1.0` tag 与 Release 已删除（产物损坏且下载量 0）。

### 未处理遗留

- 无（若 v1.1.1 流水线异常再跟进）。

---

## ✅ 已完成：2026-08-30 测试补齐、SSE 结构化重构与 1.1.0 版本发布准备（归档①）

### 背景与需求（原始记录）

安全加固提交后的后续收尾：用户确认按建议顺序逐项执行——提交改动 → 补齐测试缺口 → 打预发布 tag 验证 CI，并将最低优先级的 SSE 本地化重构一并完成。

### 实施内容（原始记录）

- 提交：安全加固 15 文件 → `4421ee6`
- 新建 `tests/test_engine_flow.py`（11 例）：FakePopen 全 mock gs（可配进度行/退出码/超时/输出文件），覆盖成功、压缩变大回退原文件、gs 未找到、输入缺失、路径穿越输入/非法输出路径、超时 kill、非零退出尾部报错、无输出文件、页数探测（含 `-dSAFER`/`--permit-file-read` 断言）及其失败分支；验证 meta 契约（完成事件 `{"key": "complete"}`、page 事件带 current/total）
- 新建 `tests/test_task_manager.py`（7 例）：任务创建布局、成功生命周期（结果发布 + 输入文件清理）、引擎错误透传、异常不杀线程池、过期清理（删除任务+输出文件）、新任务保留、PROCESSING 宽限期（窗口内保留/超宽限回收）
- SSE 结构化：`compress_pdf` 进度回调改三参 `(progress, message, meta)`，meta key 为 analyzing/processing/page/complete；`Task.stage_meta` 随 SSE `meta` 字段下发；前端 `localizeProgressMessage` 优先 meta（`META_KEY_TO_LOCALE`），英文正则保留作兼容兑底（待办第 3 项消除）
- 【冒烟发现并修复】回退原文件早退分支未发完成事件 → done 事件 meta 残留 processing；已在该分支补 `progress_callback(100, ..., {"key": "complete"})` 并加回归断言（陷阱 16/17 的来源）
- 版本与发布策略：`__version__.py` 1.0.1 → 1.1.0；release job 条件追加 `!contains(github.ref, '-')`，预发布 tag 只跑构建不发 Release，可安全验证 arm64 job
- 【rc.1 实测发现】windows-11-arm 上 `choco install ghostscript` 无限挂起（>25 分钟，同步骤 x64 约 2 分钟）→ `0b9e02a` 将 arm64 job 改为直下官方 `gs10071w64.exe` 静默安装（`/S`），打 `v1.1.0-rc.2` 重新验证；rc.1 run 可在 GitHub UI 手动取消
- 【rc.2→rc.3 闭环】rc.2 实测 `/S` 静默安装同样挂起（>20 分钟）→ `b51234c` 改用 7-Zip 解包直取二进制；**`v1.1.0-rc.3` 全绿**（run 33323656731）：test 3.10/3.11/3.12/3.13 ✅、build-macos ✅、build-windows-x64 ✅、build-windows-arm64 ✅、release 正确 skipped（预发布策略验证通过）。rc.2 挂起 run 可在 GitHub UI 手动取消；正式发版只需打稳定 tag `v1.1.0`

### 验证结果（原始记录）

- `pytest` 61/61（43 + 新增 18）；`mypy` strict Success（13 文件）；`node --check` app.js 通过；workflow YAML 合法
- 真实冒烟（SLIMPDF_PORT=5061）：SSE 事件确认携带 `meta`（analyzing → 修复后 complete）；修复前的残留 processing 问题即由此发现
- 待验证：`v1.1.0-rc.1` tag 推送后的 CI 四版本矩阵与 arm64 构建（待办第 1 项）

### 未处理遗留

见文档前部「二、待办事项」（arm64 CI 待预发布 tag 验证）。

---

## ✅ 已完成：2026-08-30 全方位安全加固与跨平台兼容性增强（归档②）

### 背景与需求（原始记录）

用户要求：① 安全面——审查修复潜在漏洞（SQL 注入/XSS/CSRF）、文件上传安全、异常行为日志追踪、依赖库风险检查；② 兼容面——主流 OS、Python 版本与浏览器兼容、跨平台路径处理、构建脚本稳定性。处理方式：逐项对照源码审计（多数防护已存在，补齐缺口）→ 实施 → 全量回归 + 真实启动冒烟。

### 审计结论（原始记录）

1. **SQL 注入**：项目无任何数据库/ORM，无注入面，无需修复。
2. **XSS**：Jinja2 自动转义开启（默认）；前端所有动态内容均走 `textContent`/属性赋值，无 `innerHTML` 拼接外部数据 → 无注入点。仍补 CSP 等响应头作纵深防御。
3. **CSRF**：原无防护 → 本次新增自定义头防护（见下）。恶意网页的 HTML 表单无法设置自定义头，跨源 fetch 带自定义头会触发 CORS 预检而本服务从不返回 CORS 头 → 伪造请求被阻断。
4. **上传安全**：扩展名白名单 + `%PDF-` 魔数 + `secure_filename` + uuid 命名已完备；本次补目录 0o700 权限与拒绝事件审计。
5. **依赖风险**：Flask 3.1.3（CVE-2025-47278 已在 3.1.1 修复）、Werkzeug 3.1.8（2026-04-02 最新版，CVE-2024-34069/49766/49767 及后续修复均已含）、Jinja2 3.1.6（CVE-2025-27516 修复版）、MarkupSafe 3.0.3/click 8.4.2/blinker 1.9.0/itsdangerous 2.2.0 均为最新 → 无已知 CVE，lock 无需重生成。
6. **跨平台**：路径处理全部 `os.path.join`/`os.path.realpath`，无硬编码分隔符；发现的真实缺口：Windows 下 gs 输出用区域编码（cp936/cp1252）可能解码崩溃、旧版 gs 页数探测无显式沙箱、Linux 数据目录不符合 XDG、CI 只测单一 Python 版本、构建脚本无 Python 版本门槛。
7. **浏览器兼容**：前端仅用 fetch/EventSource/localStorage/matchMedia 等现代浏览器标配 API，无兼容风险项。

### 实施内容（逐文件）

- 新建：`security.py`（`check_csrf` 自定义头防护、线程安全固定窗口 `RateLimiter`、`slimpdf.security` 审计 logger、`reject_rate_limited`）、`tests/test_security.py`（12 例）
- `app.py`：CSRF before_request 钩子；安全响应头 after_request（CSP default-src 'self' + frame-ancestors 'none'、nosniff、X-Frame-Options DENY、no-referrer）；429 JSON 错误处理器；非回环绑定启动告警（双写安全日志）；目录创建改 `ensure_private_dir`
- `config.py`：`RATE_LIMIT_UPLOAD/COMPRESS/WINDOW_SECONDS` 参数；`ensure_private_dir`（POSIX chmod 0o700，Windows no-op）；Linux frozen 目录改 XDG（`$XDG_DATA_HOME/SlimPDF` 或 `~/.local/share/SlimPDF`）
- `routes/upload.py`：上传限流（60/分钟）；非法扩展名/魔数拒绝写审计日志（文件名截断 80 字符防日志膨胀）
- `routes/compress.py`：压缩限流（20/分钟）；`_UUID_RE` 校验扩展到 progress/download 的 task_id（防路径穿越/非法格式）；非法 level/file_id 审计日志；429 构造走 security 模块
- `compress/engine.py`：页数探测显式 `-dSAFER`（旧版 gs 沙箱兼容）；三处子进程解码加 `errors="replace"`（Windows 区域编码容错，不再因乱码中断压缩）
- `static/js/app.js`：`API_HEADERS` 常量随所有 fetch 携带 `X-Requested-With`；`ERROR_CODE_KEYS` 新增 `RATE_LIMITED`/`CSRF_REJECTED` 映射
- `static/locales/zh.json`、`en.json`：新增 `errors.rateLimited`（key 集合保持一致）
- `scripts/build_mac.sh`：`set -euo pipefail`；Python ≥ 3.10 门槛校验；删除无用的 universal binary 探测，改为与 CI 一致的 gs Resource 拷贝（本地打包不再缺字体）
- `scripts/build_windows.bat`：Python ≥ 3.10 门槛校验（解析 `python --version`）
- `.github/workflows/build.yml`：test job 扩展为 Python 3.10/3.11/3.12/3.13 矩阵（fail-fast: false）
- `pyproject.toml`：mypy files 新增 `security.py`

### 验证结果（原始记录）

- `pytest` 43/43 通过（存量 31 + 新增 12）；`mypy` strict Success（13 文件）
- 真实启动冒烟（SLIMPDF_PORT=5059，gs 10.07.1）：四个安全响应头均在 / 返回；无头 POST → 403 CSRF_REJECTED；带头 → 正常业务分支；真实上传 200；端到端压缩 → SSE done（含「压缩变大回退原文件」分支）；`slimpdf.security` 日志如实记录 CSRF 拒绝与非法扩展名上传；`bash -n` 脚本语法、workflow YAML 均合法
- 依赖审计：见上文结论第 5 条，无已知 CVE，lock 无需变更（本机环境 Flask/Werkzeug 版本低于 lock 不影响结论，CI 从 lock 安装）
- 未在本机验证项（环境限制）：Windows/Linux 真实运行、CI 四版本矩阵、bat 脚本实机执行（已做逻辑复查）

### 未处理遗留

见文档前部「二、待办事项」（arm64 CI 未经真实发版验证、compress_pdf/task_manager 测试缺口、SSE 英文消息靠前端正则映射），另：Windows/Linux 实机与 CI 多版本矩阵待下次发版验证。

---

## ✅ 已完成：2026-07-30 待办清单九项集中处理

### 原始待办清单（处理结果）

1. ✅ locales 死资源 → 已接入国际化：语言包迁至 `static/locales/`（zh/en），前端运行时切换（顶栏按钮 + localStorage 持久化 + 默认跟随浏览器语言），旧 `locales/` 目录已删除
2. ✅ 版本号四处不一致 → 收敛为单一来源 `__version__.py`：pyproject `dynamic = ["version"]`、build.spec exec 读取、`config.VERSION`、health 接口与页面 data 属性均自动跟随
3. ✅ 依赖未锁定 → 生成 `requirements.lock`（pip freeze），CI 全部 job 改从 lock 安装
4. ✅ mypy strict 未通过 → 全量类型注解补齐（app/config/utils/routes/compress），`Success: no issues found in 12 source files`；`[tool.mypy] files` 已在 pyproject 配置
5. ✅ frozen 模式日志不落盘 → `app.py:_setup_logging()`：打包运行时 RotatingFileHandler（1MB×3）写 APP_DIR/logs/slimpdf.log
6. ✅ health 每次请求都探测 gs → 模块级缓存 + threading.Lock（成功永久缓存、失败 30s TTL），响应新增 `version` 字段
7. ✅ format_size 两处重复、100MB 上限四处硬编码 → `utils.format_size` 唯一后端实现；`config.MAX_UPLOAD_MB` 单一来源，前端经模板 body data-* 属性派生
8. ✅ CI 缺 Windows arm64 → 新增 `build-windows-arm64` job（`windows-11-arm` runner；捆绑 x64 Ghostscript，依赖 Windows-on-ARM x64 模拟，Artifex 无官方 arm64 gs）；产物重命名 SlimPDF-Windows-x64.exe / SlimPDF-Windows-arm64.exe 避免 release 冲突
9. ✅ README 链接存疑 → 用户确认 `kkxwz/PDFCompressor` 地址无误，直接划掉

### 实施内容（逐文件）

- 新建：`utils.py`、`requirements.lock`、`static/locales/zh.json`、`static/locales/en.json`、`tests/test_health.py`（3 例）、`tests/test_utils.py`（4 例）
- 删除：`locales/zh.json`、`locales/en.json`（死资源，已由 static/locales 取代）
- `config.py`：VERSION / MAX_UPLOAD_MB 单一来源；`getattr(sys, "_MEIPASS")` 修 mypy
- `pyproject.toml`：dynamic version + `[tool.setuptools.dynamic]` + mypy files
- `build.spec`：exec 读 `__version__.py` 得 APP_VERSION，info_plist 使用
- `app.py`：_setup_logging、413 handler 用 MAX_UPLOAD_MB、index 注入 max_upload_mb/cleanup_minutes/version
- `routes/health.py`：探测缓存重写；`routes/upload.py`：format_size 改 import utils；`routes/compress.py`、`compress/*`：类型注解补齐（task_manager pop 显式 `Optional[Task]`）
- `templates/index.html`：文案挂 `data-i18n`/`data-i18n-title`、语言切换按钮、body data-* 注入配置（弃用 `<script>` 内嵌 Jinja，避免 IDE lint 误报）
- `static/js/app.js`：全量重写 i18n 运行时——`t()` 点号路径 + `{placeholder}` 插值、`applyI18n`、`setLanguage`、`ERROR_CODE_KEYS` 后端错误码映射、`localizeProgressMessage` 正则本地化 SSE 英文消息、上限读 `APP_CONFIG.maxUploadMB`
- `static/css/style.css`：`.lang-toggle` 样式
- `.github/workflows/build.yml`：lock 安装、arm64 job、exe 重命名、release 三产物

### 验证结果

- `pytest` 31/31 通过（新增 7 例）；`mypy` strict Success（12 文件）
- zh/en 语言包 JSON 合法且 key 集合完全一致
- 真实启动冒烟（SLIMPDF_PORT=5057）：body data-* 正确渲染（100/5/1.0.0）、`/api/health` 返回 version 且 gs 10.07.1 ok、两个 locale 文件均 200

### 未处理遗留

见文档前部「二、待办事项」（arm64 CI 未经真实发版验证、compress_pdf/task_manager 测试缺口、SSE 英文消息靠前端正则映射）。

---

## ✅ 已完成：2026-07-30 全面健康审计与核心链路修复

### 背景与需求（原始记录）

用户要求审查项目可完善之处 → 逐条核实真实性 → 修复。审计共提出 15 项问题，经源码复读 + 本机真实 gs 实验（生成多页 PDF 分别捕获 stdout/stderr）全部核实成立，其中 2 项（file_id glob 注入、startswith 前缀绕过）降级为低危（本地单用户 + 多层兜底）。

### 根因分析（原始记录）

1. **subprocess 四合一 bug（engine.py）**：gs 进度实际输出在 stdout，代码只迭代 stderr → 进度条永远卡 10%；stdout PIPE 打开不读 → 大文件死锁；`wait(timeout)` 在 stderr EOF 后才调用 → 超时失效；失败分支重读已耗尽的 stderr → 错误信息恒为空。
2. **清理误删（task_manager.py）**：`_cleanup_expired` 只看 `created_at` 不看状态，处理中/排队中任务满 5 分钟即被删。与 bug 1 超时失效构成连环故障。
3. **SSE 无限循环（routes/compress.py）**：`while True` 仅 DONE/ERROR 退出；进度不变时不 yield，客户端断开无法感知（GeneratorExit 只在 yield 时抛出）。
4. **【验证阶段新发现】输出路径校验必失败（engine.py）**：`_validate_pdf_path` 要求 `os.path.isfile`，但被用于校验尚不存在的输出文件 → `compress_pdf` 恒返回 "Invalid output path"，**压缩功能整体不可用**。
5. **【验证阶段新发现】页数恒为 0（engine.py）**：gs ≥ 9.50 SAFER 沙箱拒绝 PostScript `file` 读文件，异常被静默吞掉。
6. **测试存量失败 4 项**：空 JSON `{}` 被 `if not data` 误判；Werkzeug 3.1 需 BytesIO；断言 `"19.0 B"` 本身写错（实际 21 字节且无小数格式）；mock 全局 `os.path.isfile` 被本地 vendor gs 干扰。

### 实施内容（原始记录）

- engine.py：`stderr=subprocess.STDOUT` 单管道 + `_drain_output` 后台线程（deque 保留尾部 50 行供错误报告）；`process.wait(timeout)` 恢复实效；超时后 `kill()+wait()`；`_validate_output_path` 独立函数；`--permit-file-read`；PostScript 路径转义；路径校验加 `os.sep`
- task_manager.py：清理跳过活跃任务，僵死宽限期 `FILE_CLEANUP_SECONDS + COMPRESS_TIMEOUT`
- routes/compress.py：`_UUID_RE` 校验；SSE deadline + 心跳；`get_json(silent=True)`
- routes/upload.py：`%PDF-` magic bytes 校验
- app.py：413 JSON handler；启动清理残留
- config.py：HOST/PORT 环境变量
- templates/index.html：10 分钟 → 5 分钟
- tests：tmp_path + monkeypatch 隔离、BytesIO、删死导入、新增 3 个回归用例（magic bytes / glob 注入 / 兄弟目录绕过）
- CI：test job 前置

### 验证结果（原始记录）

- `pytest` 24/24 通过（修复前基线 4 项存量失败）
- 真实 gs 10.07.1 端到端：30 页 PDF 压缩成功，27 个逐页进度事件（13%→99%），压缩变大时回退拷贝原文件的兜底正常触发

### 未处理遗留

见文档前部「二、待办事项」。
