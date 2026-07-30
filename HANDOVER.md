# SlimPDF 交接文档

> 供新会话/新成员快速对接。日常必读内容在前；已完成任务的审计记录统一归档在文末「⛔ 停止标识」之后，按时间倒序排列。

---

## 一、项目现状（2026-07-30）

- **产品**：SlimPDF —— 本地 PDF 压缩桌面应用（Flask + Ghostscript + PyInstaller 打包），Web UI 绑定 127.0.0.1，单用户使用。
- **主分支状态**：核心压缩链路（上传 → 压缩 → SSE 进度 → 下载）已通过全量修复与真实 Ghostscript 端到端验证。**注意：修复前 main 分支的压缩功能是完全坏的**（输出路径校验必失败 + SAFER 沙箱导致页数恒为 0），详见文末归档「2026-07-30 修复审计」。
- **测试**：`pytest` 24/24 通过；测试已全部隔离到 `tmp_path`，不再污染真实 uploads/outputs 目录。
- **CI**：`.github/workflows/build.yml` 已增加 `test` job（ubuntu + Python 3.12 + pytest），macOS/Windows 打包 job 均以其为前置；tag `v*` 触发发布。

## 二、待办事项

- [ ] locales 国际化接入或删除：`locales/en.json`、`zh.json` 目前是死资源（全仓库无引用），且 HTML 中文文案与 JS 英文提示混杂
- [ ] 版本号统一：`__version__.py`（无人 import）、`pyproject.toml` L7、`build.spec` info_plist 三处各自硬编码 1.0.0
- [ ] 依赖锁定：requirements.txt 仅范围约束，无 lock 文件
- [ ] mypy strict 补齐：pyproject 配置了 strict，但 routes/app.py 视图基本无类型注解，跑不过
- [ ] 日志落盘：桌面 frozen 模式仅控制台日志，用户侧问题无法排查
- [ ] health 接口缓存：每次请求都探测文件系统 + 起子进程取 gs 版本
- [ ] `format_size` 前后端重复实现；100MB 上限在 config/JS/HTML 三处硬编码
- [ ] Windows arm64：config.py 与 build.spec 有 arm64 分支，CI 无对应构建 job
- [ ] README 仓库链接指向 `kkxwz/PDFCompressor`，需确认与实际仓库是否一致

## 三、环境陷阱（必读）

1. **gs ≥ 9.50 默认 SAFER 沙箱**：PostScript `file` 操作符读任意路径会报 `/invalidfileaccess`，必须用 `--permit-file-read=<路径>` 显式授权（`_get_total_pages` 已处理，新增 gs 调用时注意）。
2. **gs 进度输出在 stdout 不在 stderr**：`Page N` / `Processing pages` 均打印到 stdout（本机 gs 10.07.1 实验证实，stderr 为空）。
3. **Popen 双管道只读一个会死锁**：不读的管道缓冲填满（macOS 64KB）后 gs 阻塞；engine.py 现用 `stderr=STDOUT` 单管道 + 后台线程排空。
4. **Werkzeug 3.1+ 测试上传文件字段必须用 `BytesIO` 包装**，裸 `bytes` 不再被识别为文件（表现为 `request.files` 为空 → 返回 NO_FILE）。
5. **Flask `request.get_json()` 对空对象 `{}` 判 falsy**：用 `get_json(silent=True)` + `is None` 判断，否则空 JSON 走错分支。
6. **macOS Monterey+ 5000 端口被 AirPlay Receiver 占用**：可用 `SLIMPDF_PORT` 环境变量换端口。
7. **本地 `vendor/ghostscript/mac/gs` 若存在会优先于系统 PATH 被找到**：mock `find_ghostscript` 相关测试时须先 monkeypatch `config.GS_PATHS`。
8. **build.spec 用 `SPECPATH` 取项目根目录**，不要改回 `os.getcwd()`。

## 四、代码索引

| 文件 | 职责 | 关键点 |
|------|------|--------|
| `app.py` | 入口，create_app + 主程序块 | 413 JSON 错误处理器；启动时清理残留文件 + atexit 清理 |
| `config.py` | 全局配置，frozen/开发双环境路径 | `SLIMPDF_HOST`/`SLIMPDF_PORT` 环境变量；清理 5min、压缩超时 5min、上限 100MB |
| `routes/upload.py` | POST /api/upload | 扩展名白名单 + `%PDF-` magic bytes 双重校验；uuid + secure_filename 落盘 |
| `routes/compress.py` | /api/compress、/api/progress(SSE)、/api/download | `_UUID_RE` 校验 file_id 防 glob 注入；SSE 有硬截止时间（压缩超时+60s）+ 15s 心跳 |
| `routes/health.py` | /api/health | 每次实时探测 gs（无缓存，见待办） |
| `compress/engine.py` | Ghostscript 调用核心 | 单管道 + `_drain_output` 线程；`_validate_pdf_path`（输入，须存在）与 `_validate_output_path`（输出，仅校验目录）分离；`--permit-file-read` |
| `compress/task_manager.py` | 任务字典 + 线程池(4) + 清理线程 | 清理跳过 PENDING/PROCESSING，僵死任务宽限期 = 清理时长 + 压缩超时 |
| `compress/profiles.py` | low/medium/high 三档 gs 参数 | 纯数据 |
| `static/js/app.js` | 前端逻辑 | EventSource 接 SSE；断线用 HEAD /api/download 探测后重连 |
| `tests/` | 24 个用例 | 全部 tmp_path 隔离；缺口：compress_pdf 主流程、task_manager 模块无测试 |

## 五、常用命令

```bash
python3 -m pytest                 # 全量测试
python3 app.py                    # 本地运行（默认 127.0.0.1:5000）
SLIMPDF_PORT=5050 python3 app.py  # 换端口运行
bash scripts/build_mac.sh         # 本地打包 macOS
```

---

# ⛔ 停止标识

> 以下为历史归档，可在 token 清理时安全截断。按时间倒序排列（最新在前）。

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
