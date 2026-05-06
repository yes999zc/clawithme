# clawithme — Work Scope & TODO

> 2026-05-07 | 243 tests ✅ | Ruff 0 (6 pre-existing by-policy) ✅
> Phase 10 全部完成：SSE 数据补全、前端重写、报告下载 API、evidence UX、WebUI i18n。

---

## Phase 1：基础验证 ✅ 100%

> 基础探测 + 泄露库查询 CLI 工具。48 站点 + 9 Engines。

- [x] 项目骨架、Scrapling HTTP、JSON Schema、分类树、代理配置、structlog
- [x] 48 站点定义、verify_site.py 验证
- [x] 3 Engine MVP（status_code / message / headers）+ engines.json + 加载器
- [x] BreachRecord + LeakSource + CavalierSource
- [x] CLI 入口 + GitHub Actions CI

---

## Phase 2：站点数据库扩展 ✅ 100%

> 48 站点 + 9 Engines + 3119 迁移站点。

- [x] maigret 迁移（3120 → 2487 active）、known_accounts 填充、legacy data.json 清理
- [x] 6 CMS Engine（xenforo/discourse/wordpress_author/phpbb/vbulletin/discuz）
- [x] stats.py、CONTRIBUTING.md、healthcheck.py

---

## Phase 3：深度爬虫 ✅ 100%

> 49 extractors + CrawlerClient。

- [x] Profile dataclass（16 字段）、ProfileExtractor ABC、CrawlerClient、entry_points 发现
- [x] P0（7 站）：GitHub/Zhihu/Bilibili/V2ex/Gitlab/Devto/Stackoverflow
- [x] P1（11 站）：Keybase/SegmentFault/CSDN/Coolapk/Cnblogs/Jianshu/Huaban/Behance/Dribbble/Flickr/Patreon
- [x] 天眼查 stub（已取消）
- [x] Playwright DynamicFetcher

---

## Phase 4：多信号关联 ✅ 100%

> 4 信号 Union-Find + Cavalier/HIBP 泄露源。

- [x] avatar.py（pHash + Hamming distance）、extraction.py（email/phone regex）、username.py（Levenshtein）
- [x] correlation.py（Union-Find + 反合并门）
- [x] HIBP v3、parallel manager + 15s timeout + dedup
- [x] SearXNG 回退搜索

---

## Phase 5：全景报告 ✅ 100%

> Geist HTML + JSON 导出 + CSS 图表。

- [x] Profile 完整度、泄露时间线、CSS 图表（柱状图 + 雷达图）
- [x] 站点表格（按分类）、Profile 卡片、Cluster 展示 + 脱敏
- [x] PII 脱敏、XSS 防护、路径遍历防护、伦理门禁

---

## Phase 6：LLM + 缓存 ✅ 100%

> 7 信号 + LLM Verifier（DeepSeek/Kimi/百炼）+ SQLite 缓存。

- [x] 反合并门（#13）、默认头像哈希库（#7）
- [x] LLMProvider、多 provider 自动发现、高冲突 cluster 二分类
- [x] SQLite WAL TTL 缓存、--no-cache flag
- [x] CI/CD 自动发布、extractor 健康监控、复活 deprecated 站

---

## Phase 7：异步流水线 ✅ 100%

> async pipeline（180s→14s）+ 15 新 extractor。

- [x] AsyncPipeline + Semaphore(10) + --sync flag
- [x] LLM 正式化、provider-agnostic、benchmark_llm.py
- [x] 国际站（Reddit/HN/LinkedIn/Medium/YouTube/Telegram/Steam/Quora/ProductHunt）
- [x] CN 站（豆瓣/掘金/百度知道/NGA/站酷/网易云音乐）

---

## Phase 8：Web UI + PDF ✅ 100%

> FastAPI + SSE + Geist 前端 + PDF 导出。

- [x] `/api/search/{username}` SSE 实时推送
- [x] 安全加固：CORS + slowapi + CSP + 路径穿越 + 异常处理
- [x] PDF 报告（WeasyPrint）
- [x] 报告国际化（_STRINGS zh/en、generate_report(lang=)）
- [x] 陪审团审计修复（17 items）

---

## Phase 9：置信度系统 + Extractor 扩展 ✅ 100%

> 置信度打分 + wrong-person 检测 + 17 新 extractor + 报告 UX。

- [x] _compute_hit_confidence() + _is_wrong_person() + 置信度 badge
- [x] 6 P0 extractor（Instagram/Twitter/微博/sspai/Twitch/SlideShare）
- [x] 5 P1 extractor（知乎 REST/Gitee/贴吧/WordPress/Blogger）
- [x] 6 P2 extractor（LeetCode/Goodreads/Chess/Discogs/CodePen/虎扑）
- [x] Stack Overflow 探针修复、YouTube 修复
- [x] 报告 UX：identity assessment 卡片、CSS badge 色值

---

## Phase 10：WebUI 重构 + 体验优化 ✅ 100%

> **交付物**：完整的 WebUI 体验 + 报告下载 API + i18n + CLI 去重。

### 10.1 SSE 数据补全
- [x] Hit 事件增加 status / category / confidence / wrong_person
- [x] Profile 事件扩展至全部 13 个字段
- [x] Cluster 事件增加 evidence（含站点对信息）+ profile_count
- [x] 新增 `leak` 事件类型：逐条泄露记录推送
- [x] 新增 `leakstatus` 事件：按来源统计
- [x] Done 事件增加 sources_used / llm_configured
- [x] Pipeline 执行期间发送 scanning 状态事件

### 10.2 前端重写
- [x] 搜索参数面板（全量搜索/禁用缓存/同步模式/语言）
- [x] 搜索类型自动识别（邮箱/手机/用户名）
- [x] 实时统计栏（6 项）
- [x] 站点命中按分类分组 + 置信度 badge + wrong-person 警告
- [x] Profile 卡片：完整度 donut + 全部字段 + 可折叠详情表
- [x] Cluster 卡片：evidence 去重归纳 + 站点对信息 + 白话信号
- [x] 独立 profile 区块（未匹配账号）
- [x] 泄露记录区块（按来源分组 + 脱敏）
- [x] 报告下载按钮（HTML/JSON/PDF/MD）
- [x] 取消搜索按钮
- [x] Cache-Control: no-cache

### 10.3 报告下载 API
- [x] `GET /api/report/{trace_id}?format=html|json|pdf|md&username=xxx&lang=zh|en`
- [x] 搜索结果内存缓存（5min TTL）
- [x] Markdown 报告：export_markdown()

### 10.4 证据 UX 重写
- [x] 后端 evidence 增加 `siteA ↔ siteB: ` 前缀
- [x] 用户名相同 → 归纳为一条 "All N profiles share the same username"
- [x] 信号名 → 自然语言（avatar_phash → 🖼 头像相似）
- [x] 置信度 → 可读标签（"Very likely same person"）
- [x] 报告 _redact_evidence() 兼容新 evidence 格式
- [x] 报告 _render_clusters() 同步 evidence 去重归纳

### 10.5 WebUI 国际化
- [x] `_STRINGS` zh/en 字典（~60 键）
- [x] 页面顶部语言切换（中文 | EN）
- [x] `data-i18n` 属性 + `applyI18n()` / `L()` 函数
- [x] 报告语言跟随界面语言（downloadReport 传 lang 参数）

### 10.6 报告模块拆分
- [x] `report/i18n.py` — 双语字符串 + 常量
- [x] `report/template.py` — Geist HTML 模板
- [x] `report/renderers.py` — 所有 render 函数
- [x] `report/generator.py` — 精简为协调器（1691→100 行）

### 10.7 CLI 去重
- [x] `_print_search_results()` — 合并三路输出
- [x] `_write_search_report()` — 合并三路报告写入
- [x] `_query_all_leaks()` — 合并三路泄露查询

### 10.8 基础设施
- [x] FastAPI `on_event` → `lifespan` 上下文管理器
- [x] macOS Homebrew WeasyPrint DYLD_LIBRARY_PATH 自动修复
- [x] 死配置清理（dehashed_api_key / dehashed_email）
- [x] webui.sh 启动脚本
- [x] TUI Banner（Hermes 风格全宽头部）
- [x] `clawithme search <username> --format md` 支持

---

## KILLED / DEFERRED

| # | 项 | 状态 | 原因 |
|:--:|------|:----:|------|
| 1 | 自建泄露库 | **KILLED** | 刑法 285 条风险 |
| 6 | 微信弱信号实验 | **KILLED** | 失败率 90%+ |
| 11 | Profile 提取 P1 | **✅ DONE** | 已在 Phase 3 完成 |
| 3 | Louvain 图聚类 | **v3** | 等 face recognition 方向确定 |
| 12 | 天眼查 API | **❌ CANCELLED** | 9 哥决定取消 |

---

## 审计记录

| 轮次 | 方式 | 发现 | 状态 |
|:---:|------|------|:---:|
| 1 | 陪审团（3 视角） | maigret 死代码、空壳站点 | ✅ 已修复 |
| 2 | 陪审团 | 空 stubs、migration artifacts | ✅ 已修复 |
| 3 | code-review-excellence | 29 findings | ✅ 8 项已修复 |
| 4 | 功能 QA 自审 | 7 虚标 + 3 bug | ✅ 已修复 |
| 5 | Claude Code 架构审计 | 5 代码 + 10 边界 | ✅ 全部执行 |
| 6 | 四方 V2 路线评审 | 重新排名、KILL #1/#6 | ✅ Phase 6 执行完毕 |
| 7 | Phase 8 定点审计 | 6 issues | ✅ 全部修复 |
| 8 | Phase 8 陪审团全量审计 | 28 findings → 17 fixed | ✅ 全部修复 |

---

## 总结

| 维度 | 状态 |
|------|:---:|
| Phase 1-9 代码 | **100%** ✅ |
| Phase 10（WebUI 重构 + 体验优化） | **100%** ✅ |
| 测试 (243 tests) | **all passing** ✅ |
| Lint (Ruff, all files) | **0 (6 by-policy)** ✅ |
| Profile extractors | **49** |
| Report formats | **HTML + JSON + PDF + Markdown** |
| WebUI i18n | **zh + en** |
| 启动方式 | **clawithme-web** / **./webui.sh** |
