# Clawithme 架构审计报告

> Claude Code Opus 全面审计 | 2026-05-05
> 范围：全部 .py 文件 + docs/todo.md + docs/technical-roadmap.md

---

## A. 代码逻辑一致性

### A1. 管线连接

CLI → Engine → Crawler → Signals → Report 流程正确，数据沿 Phase 1→5 传递。

**发现 5 个问题：**

| # | 问题 | 影响 |
|---|------|------|
| 1 | `_ALLOWED_VARS` 缺少 `{e_headers}` | 与文档不一致，但实际 headers 不走模板 |
| 2 | `engine.headers` 查 `check.expected_headers` 但 schema 定义是 `check.headers` | headers 引擎永远无法匹配 |
| 3 | `cli.py` 用 `asyncio.run()` — 若嵌入异步上下文会崩溃 | 阻止 SDK 嵌入 |
| 4 | BreachRecord(Pydantic) 与 Profile(dataclass) 需手动映射 | 字段语义不一致 |
| 5 | `report_path` 先 `resolve()` 再检查 `..`，顺序错误 | 路径穿越检查有盲区 |

### A2. 死代码

| 文件 | 代码 | 状态 |
|------|------|------|
| `crawler/client.py:149` | `is_allowed()` (robots.txt) | 零调用 |
| `crawler/base.py:66` | `ProfileExtractor.can_handle()` | 零调用 |
| `signals/extraction.py:74` | `extract_phones()` | 零调用 |
| `engine/http_client.py:73` | `head()` | 零调用 |
| `engine/http_client.py:89` | `post()` | 零调用 |

### A3. 其他

- 变量遮蔽：`cli.py:160` `engine = CorrelationEngine()` 遮蔽循环中的 `engine`
- 类型：`report/generator.py:21` `clusters: list` 应为 `list[Cluster]`
- 竞争条件：`CrawlerClient._last_request_at` 多线程不安全
- 超时截断：`timeout_ms // 1000` 把 1500ms 截为 1s

---

## B. 完成度 vs todo.md

### ✅ 真正完成

20 项核心功能已交付：项目骨架、Scrapling 封装、schema/taxonomy、结构化日志、Engine 系统、BreachRecord、CavalierSource、CLI、爬虫框架、Profile 结构、pHash 头像匹配、关联引擎、置信度评分、HTML/JSON 报告。

### ⚠️ 部分完成

| 任务 | 缺口 |
|------|------|
| 1.1.5 代理配置 | `config.example.toml` 存在，但**无 `load_config()` 读取** |
| 1.2.1 中国站验证 | JSON 文件存在，但 `error_flags` 全空 — 未记录反爬级别 |
| 2.1.1 50+ 中国站 | 49 站点 JSON，其中 ~16 是中国站 |
| 2.2.1 CMS Engine | 缺 phpBB、vBulletin、Discuz! |
| 3.1.2 站点抽取器 | zhihu 提取器文件**不存在** |
| 3.1.3 DynamicFetcher | 代码存在但**没有 extractor 使用**，未实测 |

### ❌ 缺失

CONTRIBUTING.md、微信弱信号、监控探针部署、邮箱反查、手机→平台、SearXNG 搜索、HIBP、LeakSource 管理器、完整度计算、交互式 Web UI。

---

## C. 功能测试视角

### 关键边缘情况

| 模块 | 问题 |
|------|------|
| **cli.py** | Unicode 用户名（中文）被 `_USERNAME_RE` 拒绝 |
| **cli.py** | 用户名含 `{` 或 `}` → `str.format()` 抛 `KeyError` |
| **engines.py** | `message` 分类器空 `presence_strs` 默认 True + 空 `absence_strs` = **全部命中** |
| **engines.py** | `{e_string}` 只取第一个元素，多字符串被忽略 |
| **http_client.py** | `head()` 底层用 GET — 某些端点 HEAD/GET 行为不同 |
| **correlation.py** | O(n²) 比较，100 profile = 4950 对 |
| **correlation.py** | 单例 cluster 置信度 1.0 — 应低置信度（无关联证据） |
| **correlation.py** | username 比较总是运行，即使两个都是同一搜索用户名 |
| **report** | `username` 含 `{` → 报告生成崩溃 |
| **loader.py** | 无 try/except — 损坏的 JSON 导致原始回溯 |
| **leak_sources** | 邮件正则只禁止 `@` 和空格，过于宽松 |

---

## D. 架构质量

### Engine 系统 ✅
44 个站点由 `base_http_status` 一个引擎覆盖。"定义一次，覆盖多个"承诺已兑现。

**弱点**：`engine.params` 从未被运行时读取，超时等设置完全由 HttpClient 构造函数决定。

### 关联引擎 ✅
Union-Find + 路径压缩实现正确，传递闭包正确。SIGNAL_WEIGHTS 设计合理。

**弱点**：单例 cluster 置信度硬编码为 1.0。

---

## 优先开发计划

| 步骤 | 内容 | 理由 | 复杂度 |
|:--:|------|------|:--:|
| **1** | 配置系统 + 错误处理加固 | 代理配置是死代码，JSON 损坏会崩溃。是所有后续工作的基础 | 低 (~80行) |
| **2** | HIBP 接入 + LeakSource 管理器 | Phase 4 最大未完成项。k-anonymity 无需 API key，零障碍 | 中 (~200行) |
| **3** | 站点数据库完善 + CONTRIBUTING.md | 填充 error_flags/known_accounts，防止规则腐烂 | 低但繁琐 (~50文件) |
| **4** | 知乎提取器 + DynamicFetcher 接通 | 完成 Phase 3 最低交付物（≥5站点可爬取，目前仅1个） | 高 (需实测反爬) |

依赖：1 → 2/3 可并行 → 4 需要 1+3
