# SlimPDF 交接文档

> 供新会话/新成员快速对接。日常必读内容在前；已完成任务的审计记录统一归档在文末「⛔ 停止标识」之后，按时间倒序排列。

---

## 一、项目现状（2026-07-30 第二次更新）

- **产品**：SlimPDF —— 本地 PDF 压缩桌面应用（Flask + Ghostscript + PyInstaller 打包），Web UI 绑定 127.0.0.1，单用户使用。
- **主分支状态**：核心压缩链路（上传 → 压缩 → SSE 进度 → 下载）已通过全量修复与真实 Ghostscript 端到端验证；原待办清单 9 项已全部处理完毕（详见文末归档「2026-07-30 待办清单九项集中处理」）。
- **国际化**：前端已接入 zh/en 双语切换（语言包在 `static/locales/`，顶栏有切换按钮，localStorage 持久化，默认跟随浏览器语言）。
- **测试**：`pytest` 31/31 通过（新增 health 缓存 3 例 + utils.format_size 4 例）；`mypy`（strict）全量通过。
- **CI**：`.github/workflows/build.yml` 含 test（前置门禁）+ macOS + Windows x64 + Windows arm64 四个 job；tag `v*` 触发发布；依赖统一从 `requirements.lock` 安装。

## 二、待办事项

- [ ] Windows arm64 CI job 未经真实 tag 触发验证（`windows-11-arm` runner + choco 安装链路纸面可行，首次发版时需盯一下）
- [ ] 测试缺口：`compress_pdf` 主流程、`task_manager` 模块仍无单元测试
- [ ] 后端 SSE stage_message 仍输出英文，前端靠正则映射成当前语言（`localizeProgressMessage`）；若后端消息文案变动需同步前端正则

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

## 四、代码索引

| 文件 | 职责 | 关键点 |
|------|------|--------|
| `app.py` | 入口，create_app + 主程序块 | 413 JSON 错误处理器；启动清理残留 + atexit 清理；frozen 模式日志落盘 APP_DIR/logs（RotatingFileHandler 1MB×3）；index 注入 max_upload_mb/cleanup_minutes/version |
| `config.py` | 全局配置，frozen/开发双环境路径 | `SLIMPDF_HOST`/`SLIMPDF_PORT` 环境变量；`VERSION`（源自 \_\_version\_\_.py）；`MAX_UPLOAD_MB` 单一来源 |
| `__version__.py` | 版本号唯一来源 | pyproject dynamic + build.spec exec + config 均读此处 |
| `utils.py` | 后端共享工具 | `format_size` 唯一后端实现 |
| `routes/upload.py` | POST /api/upload | 扩展名白名单 + `%PDF-` magic bytes 双重校验；uuid + secure_filename 落盘 |
| `routes/compress.py` | /api/compress、/api/progress(SSE)、/api/download | `_UUID_RE` 校验 file_id 防 glob 注入；SSE 有硬截止时间（压缩超时+60s）+ 15s 心跳 |
| `routes/health.py` | /api/health | 探测结果缓存（成功永久、失败 30s TTL）；返回应用版本号 |
| `compress/engine.py` | Ghostscript 调用核心 | 单管道 + `_drain_output` 线程；`_validate_pdf_path`（输入）与 `_validate_output_path`（输出）分离；`--permit-file-read` |
| `compress/task_manager.py` | 任务字典 + 线程池(4) + 清理线程 | 清理跳过 PENDING/PROCESSING，僵死任务宽限期 = 清理时长 + 压缩超时 |
| `compress/profiles.py` | low/medium/high 三档 gs 参数 | 纯数据 |
| `static/js/app.js` | 前端逻辑 | i18n 运行时（t()/applyI18n/错误码映射/SSE 消息本地化）；EventSource 接 SSE；配置读自 body data-* 属性 |
| `static/locales/zh.json`、`en.json` | 双语语言包 | key 集合必须保持一致；`{maxMB}`/`{minutes}`/`{current}`/`{total}` 占位符插值 |
| `templates/index.html` | 页面结构 | 文案元素均挂 `data-i18n`/`data-i18n-title`；body data-* 注入后端配置 |
| `requirements.lock` | 锁定依赖版本 | CI 全部 job 从此安装；改 requirements.txt 后需重新生成 |
| `tests/` | 31 个用例 | 全部 tmp_path/monkeypatch 隔离；缺口：compress_pdf 主流程、task_manager 模块无测试 |

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
