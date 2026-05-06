# clawithme — Work Scope & TODO

> 2026-05-06 V2 全面完成。Phase 1-8 全部交付，243 tests，34 extractors，async + Web UI + PDF。
> Phase 9 规划中：16-24 extractor expansion + 服务器部署。

---

## Phase 1：基础验证 ✅ 100%

> **交付物**：能探测站点 + 查询泄露库的 CLI 工具。

### 1.1 环境搭建 & Schema

- [x] **1.1.1** 项目骨架：`clawithme/` 包、`pyproject.toml`、`config.example.toml`、pytest
- [x] **1.1.2** Scrapling HTTP 封装层（`engine/http_client.py`）
- [x] **1.1.3** `data/schema.json` — JSON Schema 校验
- [x] **1.1.4** `data/taxonomy.json` — 分类树定义
- [x] **1.1.5** HTTP 代理配置（`config.toml`）
- [x] **1.1.6** structlog 结构化日志 + trace_id

### 1.2 站点验证

- [x] **1.2.1** 48 个站点定义（36 active, 12 deprecated），通过 schema 校验
- [x] **1.2.2** `scripts/verify_site.py` — known_accounts 逐站验证

### 1.3 Engine 系统 MVP

- [x] **1.3.1** `base_http_status` Engine
- [x] **1.3.2** `base_http_message` Engine
- [x] **1.3.3** `base_http_headers` Engine
- [x] **1.3.4** `engines.json` 结构 + 模板沙箱
- [x] **1.3.5** 引擎加载器（`engine/loader.py`）

### 1.4 LeakSource

- [x] **1.4.1** BreachRecord Pydantic Model
- [x] **1.4.2** LeakSource 抽象基类
- [x] **1.4.3** CavalierSource 实现

### 1.5 CLI + CI

- [x] **1.5.1** `clawithme search <username>` CLI 入口
- [x] **1.5.2** GitHub Actions CI（ci.yml + daily-verify.yml）

---

## Phase 2：站点数据库扩展 ✅ 100%

> **交付物**：48 站点 + 9 Engines + 3119 迁移站点 + CI 脚本。

### 2.1 站点扩展

- [x] **2.1.1** maigret 站点迁移（`scripts/migrate_maigret.py`）— 3120 站点，2487 active，100% engine_ref 覆盖
- [x] **2.1.2** known_accounts 填充（36 个 curated 站点全部完成）
- [x] **2.1.3** legacy `data.json` 清理

### 2.2 Engine 系统完善

- [x] **2.2.1** 全部 CMS Engine（xenforo/discourse/wordpress_author/phpbb/vbulletin/discuz）
- [x] **2.2.2** `scripts/stats.py` — Engine 覆盖统计

### 2.3 基础设施

- [x] **2.3.1** GitHub Actions CI 已部署
- [x] **2.3.2** `CONTRIBUTING.md` + known_accounts 维护指南
- [x] **2.3.3** `scripts/healthcheck.py` — 组件存活探针

---

## Phase 3：深度爬虫 ✅ 100%

> **交付物**：19 extractors（7 P0 + 11 P1 + 天眼查 stub），CrawlerClient 完整。

### 3.1 爬虫核心

- [x] **3.1.1** `crawler/base.py` — Profile dataclass（16 字段）+ ProfileExtractor ABC
- [x] **3.1.2** `crawler/client.py` — CrawlerClient：频率控制、UA 轮换、static+dynamic fetch
- [x] **3.1.3** `crawler/registry.py` — entry_points 插件发现
- [x] **3.1.4** `crawler/utils.py` — 共享工具

### 3.2 P0 Extractors（7 站）

- [x] **3.2.1** GitHubExtractor — CSS selector
- [x] **3.2.2** ZhihuExtractor（clawithme-cn 插件）— Playwright
- [x] **3.2.3** BilibiliExtractor — API web-interface/card
- [x] **3.2.4** V2exExtractor — API v1 members
- [x] **3.2.5** GitlabExtractor — API v4 users
- [x] **3.2.6** DevtoExtractor — API by_username
- [x] **3.2.7** StackoverflowExtractor — SE 2.3 API

### 3.3 P1 Extractors（11 站）

- [x] **3.3.1** Keybase / SegmentFault / CSDN / Coolapk / Cnblogs / Jianshu / Huaban / Behance / Dribbble / Flickr / Patreon

### 3.4 天眼查 stub

- [x] **3.4.1** TianyanchaExtractor（token gate，stub 完成）

### 3.5 DynamicFetcher

- [x] **3.5.1** Playwright DynamicFetcher 集成
- [x] **3.5.2** 已知局限：5 个 SPA 站不可探测

---

## Phase 4：多信号关联 ✅ 100%

> **交付物**：4 信号 Union-Find 关联引擎 + Cavalier/HIBP 双泄露源。

### 4.1 信号模块

- [x] **4.1.1** `signals/avatar.py` — pHash + Hamming distance ≤ 10
- [x] **4.1.2** `signals/extraction.py` — 国际手机号 regex + 邮件提取 + 一次性邮箱过滤
- [x] **4.1.3** `signals/username.py` — Levenshtein + 词缀/数字后缀
- [x] **4.1.4** `signals/correlation.py` — Union-Find，4 信号加权匹配

### 4.2 泄露源

- [x] **4.2.1** `leak_sources/hibp.py` — HIBP v3
- [x] **4.2.2** `leak_sources/manager.py` — 并行 + 15s timeout + 去重
- [x] **4.2.3** 泄露域名→平台反向映射
- [x] **4.2.4** SearXNG 回退搜索

---

## Phase 5：全景报告 ✅ 100%

> **交付物**：Geist 灰白 HTML + JSON 导出 + CSS 图表。

### 5.1 报告引擎

- [x] **5.1.1** 数据聚合
- [x] **5.1.2** Profile 完整度进度条
- [x] **5.1.3** 泄露时间线（CSS timeline）
- [x] **5.1.4** 平台分布 + 关联信号柱状图（纯 CSS）

### 5.2 可视化

- [x] **5.2.1** 站点表格（按 classification 分组）
- [x] **5.2.2** Profile 卡片
- [x] **5.2.3** Cluster 展示 + 脱敏证据

### 5.3 安全和导出

- [x] **5.3.1** PII 脱敏（`_redact_evidence()`）
- [x] **5.3.2** HTML 转义（XSS 防护）
- [x] **5.3.3** 路径遍历防护
- [x] **5.3.4** 自包含 HTML 报告
- [x] **5.3.5** JSON 结构化导出
- [x] **5.3.6** 伦理使用门禁（`--acknowledge-ethical-use`）

---

## Phase 6：关联引擎加固 + 基础建设 ✅ 100%

> **交付物**：7 信号规则引擎 + LLM Verifier（DeepSeek Flash）+ SQLite 缓存 + 默认头像过滤 + 4 CN 站复活 + extractor 健康监控 + CI/CD 自动发布。
> **209 tests** all passing。

### 6.1 正确性修复

- [x] **6.1.1** 拆分误合并 cluster (#13) — `_match_signals()` 反合并门。username-only 匹配时必须有额外支撑信号。
- [x] **6.1.2** 默认头像哈希库 (#7) — `data/default_avatars.json`。`is_default_avatar()` 白名单过滤。

### 6.2 LLM 身份推理

- [x] **6.2.1** `signals/llm_verifier.py` — LLMProvider dataclass, provider-agnostic API。DeepSeek/Kimi/百炼 自动发现。
- [x] **6.2.2** 高冲突 cluster 二分类 — `verdict()` 返回 (identity_match: bool, confidence: float, reasoning: str)。
- [x] **6.2.3** LLM identity summary — 替代 `_compose_summary()`。

### 6.3 基础设施

- [x] **6.3.1** 结果缓存层 — SQLite WAL mode, TTL 24h, `--no-cache` flag。
- [x] **6.3.2** CI/CD 自动发布 — `.github/workflows/release.yml`：wheel → PyPI → GitHub Release。
- [x] **6.3.3** Extractor 健康监控 — `scripts/extractor_health.py` + cron。
- [x] **6.3.4** 修复误判 deprecated CN 站 — Gitee, 掘金, 网易云音乐, AcFun 复活。

### 6.4 审计

- [x] **6.4.1** 两轮陪审团审计 — 🔴🟡 已全修。

---

## Phase 7：引擎升级 + 站点扩展 ✅ 100%

> **交付物**：async pipeline（180s→14s）+ LLM 推理正式化 + 15 个新 extractor（国际 9 + CN 6）。
> **224 tests** all passing。E2E cold ~14s。

### 7.1 架构升级

- [x] **7.1.1** AsyncPipeline — `asyncio.gather` + `asyncio.Semaphore(10)`。同步回退 `--sync` flag。
- [x] **7.1.2** 配置层增强 — concurrency 可配, cache TTL, provider 切换。

### 7.2 LLM 推理正式化

- [x] **7.2.1** 多 provider API — DeepSeek/Kimi/百炼，provider-agnostic `LLMProvider` 接口。
- [x] **7.2.2** `scripts/benchmark_llm.py` — 5 test cases 横评工具。
- [x] **7.2.3** Fallback 到规则引擎 — LLM API 不可用时自动降级。

### 7.3 国际站扩展（9 站）

- [x] **7.3.1** Reddit, HackerNews, LinkedIn, Medium, YouTube
- [x] **7.3.2** Telegram, Steam, Quora, ProductHunt

### 7.4 CN 站扩展（6 站）

- [x] **7.4.1** 豆瓣, 掘金, 百度知道, NGA, 站酷 Zcool, 网易云音乐

---

## Phase 8：表面层扩展 ✅ 100%

> **交付物**：Web UI（FastAPI + SSE）+ PDF 导出（WeasyPrint）+ 审计修复。
> **243 tests** all passing。0 ruff errors on Phase 8 files。

### 8.1 Web UI

- [x] **8.1.1** FastAPI + SSE streaming — `/api/search/{username}` 实时推送 hits/profiles/clusters。
- [x] **8.1.2** Geist 前端 — 搜索框 → 实时卡片 → cluster 可视化。Vanilla JS。
- [x] **8.1.3** 安全加固 — CORS 配置、路径穿越防护、catch-all 异常处理、前端 SSE 自动重连。

### 8.2 多格式报告

- [x] **8.2.1** PDF 报告 — WeasyPrint 渲染同一 Geist HTML。`--report report.pdf --format pdf`。
- [x] **8.2.2** HTML/JSON 报告 — 已有（Phase 5）。

### 8.3 审计修复（6 issues → 17 issues after jury）

- [x] **8.3.1** DRY 修复 — 删除 `cli_web.py`，统一从 `cli` 导入。
- [x] **8.3.2** SSE 异常处理 — 外层 catch-all。
- [x] **8.3.3** 前端重连 — EventSource 断连 3s 自动 retry（jury 后改为 max 1 retry）。
- [x] **8.3.4** 死代码移除 — `/api/report` 空壳 endpoint。
- [x] **8.3.5** Web 测试 — 8 tests（SSE/error/edge）。
- [x] **8.3.6** PDF 测试 — 5 tests（skip-safe）。
- [x] **8.3.7** 陪审团全量审计修复（17 items）：
  - 🔴 C1-C7：XSS quot 转义 / 服务端认证 / slowapi 限流 / SSE 断连检测 / 超时 / 天眼查删除 / startup 预加载
  - 🟠 H1-H5：clawithme-web CLI / SSE retry 计数器 / 路径泄露脱敏 / setup_class ImportError / JSON.parse try/catch
  - 🟡 M1,M2,M3,M5,M6：/health 端点 / username 校验 / CSP header / NaN 计数器 / 优雅关闭

### ❌ 天眼查

- [x] ~~天眼查 API~~ — **已取消**。9 哥决定。

---

## KILLED / DEFERRED

| # | 项 | 状态 | 原因 |
|:--:|------|:----:|------|
| 1 | 自建泄露库 | **KILLED** | 刑法 285 条风险 + 无合法数据源 |
| 6 | 微信弱信号实验 | **KILLED** | 失败率 90%+，无公开 API |
| 11 | Profile 提取 P1 | **✅ DONE** | 已从 v2 移除 |
| 3 | Louvain 图聚类 | **v3** | 等 face recognition 方向确定 |
| 12 | 天眼查 API | **❌ CANCELLED** | 9 哥决定取消 |

---

## 审计记录

| 轮次 | 方式 | 发现 | 状态 |
|:---:|------|------|:---:|
| 1 | 陪审团（3 视角） | maigret 死代码 4500 行、7 空壳站点 | ✅ 已修复 |
| 2 | 陪审团 | 4 空 stubs、迁移 artifacts | ✅ 已修复 |
| 3 | code-review-excellence | 29 findings | ✅ 8 项已修复 |
| 4 | 功能 QA 自审 | 7 虚标 + 3 bug | ✅ 已修复 |
| 5 | Claude Code 架构审计 | 5 代码 + 10 边界 | ✅ 全部执行 |
| **6** | **四方 V2 路线评审** | **重新排名 V2、KILL #1/#6、新增 LLM POC** | ✅ **Phase 6 执行完毕** |
| **7** | **Phase 8 定点审计** | **6 issues（3 🔴 + 3 🟡），13 新 tests** | ✅ **全部修复（290a41e）** |
| **8** | **Phase 8 陪审团全量审计** | **28 findings → 17 fixed（3 agents cross-ref）** | ✅ **全部修复（211cd2a）** |

---

## 总结

| 维度 | 状态 |
|------|:---:|
| Phase 1-8 代码 | **100%** ✅ |
| 测试 (243 tests) | **all passing** ✅ |
| Lint (Ruff, Phase 8 files) | **0** ✅ |
| CI 部署 | **已部署** ✅ |
| Phase 9 (expansion) | **🔜 16-24 extractors + 服务器部署** |
| Phase 10+ (backlog) | **TBD** |
| **V2 已完成** | **~181h** |
| v3 scope | Louvain, 人脸识别, 天眼查对接(已取消), SaaS 上线 |
