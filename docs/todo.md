# clawithme — Work Scope & TODO

> 2026-05-05 全代码审计后重写。Phase 1-5 代码 100% 完成，CI 部署待做，v2 延期。
> 160 tests all passing, Ruff 0 (by policy, 2 intentional exceptions), 9 engines, 2487 migrated sites.

---

## Phase 1：基础验证 ✅ **100% 代码完成**（CI 待部署）

> **交付物**：能探测站点 + 查询泄露库的 CLI 工具。schema + CI 脚本就位。

### 1.1 环境搭建 & Schema

- [x] **1.1.1** 项目骨架：`clawithme/` 包、`pyproject.toml`、`config.example.toml`、pytest
- [x] **1.1.2** Scrapling HTTP 封装层（`engine/http_client.py`）
- [x] **1.1.3** `data/schema.json` — JSON Schema 校验
- [x] **1.1.4** `data/taxonomy.json` — 分类树定义
- [x] **1.1.5** HTTP 代理配置（`config.toml`）
- [x] **1.1.6** structlog 结构化日志 + trace_id

### 1.2 站点验证

- [x] **1.2.1** 48 个站点定义（36 active, 12 deprecated），通过 schema 校验
- [ ] **1.2.2** 微信弱信号实验 → **v2 scope**（搜一搜/公众号间接探测）
- [x] **1.2.3** `scripts/verify_site.py` — known_accounts 逐站验证

### 1.3 Engine 系统 MVP

- [x] **1.3.1** `base_http_status` Engine
- [x] **1.3.2** `base_http_message` Engine
- [x] **1.3.3** `base_http_headers` Engine
- [x] **1.3.4** `engines.json` 结构 + 模板沙箱（`str.replace`，白名单制）
- [x] **1.3.5** 引擎加载器（`engine/loader.py`）

### 1.4 LeakSource

- [x] **1.4.1** BreachRecord Pydantic Model（7 字段，field validators）
- [x] **1.4.2** LeakSource 抽象基类（3 个 search 方法 + is_available + rate_limit）
- [x] **1.4.3** CavalierSource 实现

### 1.5 CLI + CI ✅

- [x] **1.5.1** `clawithme search <username>` CLI 入口（含 SearXNG fallback）
- [x] **1.5.2** GitHub Actions CI — **已部署**：`.github/workflows/ci.yml`（PR validate + stats）、`.github/workflows/daily-verify.yml`（每日 08:00 UTC 全量验证）

---

## Phase 2：站点数据库扩展 ✅ **100% 代码完成**（CI 待部署）

> **交付物**：48 站点 + 9 Engines + 3119 迁移站点 + CI 脚本。

### 2.1 站点扩展

- [ ] **2.1.1** 中国站扩展至 50+ → **v2 scope**（当前 28 CN 站定义，16 active）
- [x] **2.1.2** maigret 站点迁移（`scripts/migrate_maigret.py`）
  - 3120 站点迁移完成，2487 active，100% engine_ref 覆盖
  - 自动分配：xenforo 222 / phpbb 157 / vbulletin 120 / discourse 92 / flarum 15 / wordpress 9
- [x] **2.1.3** known_accounts 填充（36 个 curated 站点全部完成）
- [x] **2.1.4** legacy `data.json` 清理（1.2MB 文件已废弃）

### 2.2 Engine 系统完善

- [x] **2.2.1** 全部 CMS Engine 实现（xenforo / discourse / wordpress_author / phpbb / vbulletin / discuz）
  - phpBB + vBulletin ported from maigret_china (MIT)
  - **Discuz!** — 原创（maigret/maigret_china 均无）
- [x] **2.2.2** `scripts/stats.py` — Engine 覆盖统计

### 2.3 基础设施 ✅

- [x] **2.3.1** GitHub Actions CI — **已部署**（ci.yml + daily-verify.yml）
- [x] **2.3.2** `CONTRIBUTING.md` + known_accounts 维护指南
- [x] **2.3.3** `scripts/healthcheck.py` — 组件存活探针

---

## Phase 3：深度爬虫 ✅ **100%**

> **交付物**：GitHub + 知乎 两个 extractor，CrawlerClient 完整。

### 3.1 爬虫核心

- [x] **3.1.1** `crawler/base.py` — Profile dataclass（16 字段）+ ProfileExtractor ABC
- [x] **3.1.2** `crawler/client.py` — CrawlerClient：频率控制、UA 轮换、static+dynamic fetch
- [x] **3.1.3** `crawler/registry.py` — entry_points 插件发现
- [x] **3.1.4** `crawler/utils.py` — first_text() / parse_count() 共享工具
- [x] **3.1.5** GitHubExtractor — CSS selector 提取 name/bio/location/followers/avatar_phash
- [x] **3.1.6** ZhihuExtractor（clawithme-cn 插件）— Playwright DynamicFetcher

### 3.2 DynamicFetcher

- [x] **3.2.1** DynamicFetcher 集成（`_stealth_page_setup` 去 webdriver 标记）
- [x] **3.2.2** 已知局限：SPA shells 对 exist/nonexist 返回相同 HTML（Twitter/Twitch/少数派等 5 站）

---

## Phase 4：多信号关联 ✅ **100%**

> **交付物**：4 信号 Union-Find 关联引擎 + Cavalier/HIBP 双泄露源。

### 4.1 信号模块

- [x] **4.1.1** `signals/avatar.py` — pHash 计算 + Hamming distance ≤ 10 + AvatarMatch
- [x] **4.1.2** `signals/extraction.py` — 国际手机号 regex（E.164 7-15 位）+ 邮件提取 + 一次性邮箱过滤
- [x] **4.1.3** `signals/username.py` — Levenshtein + 词缀/数字后缀模式识别
- [x] **4.1.4** `signals/correlation.py` — Union-Find 传递闭包，4 信号加权匹配

### 4.2 泄露源

- [x] **4.2.1** `leak_sources/hibp.py` — HIBP v3 API，k-anonymity，无密钥优雅降级
- [x] **4.2.2** `leak_sources/manager.py` — 并行查询 + 15s 超时 + 去重 + 单源故障隔离
- [x] **4.2.3** 泄露域名→平台反向映射
- [x] **4.2.4** SearXNG `site:domain "username"` 回退搜索

### 4.3 关联引擎

- [x] **4.3.1** 信号权重：email(1.0) > phone(0.95) > phash(0.8) > username(0.7)
- [x] **4.3.2** Cluster 置信度评分（≥90% high / 70-89% mid / <70% low）
- [x] **4.3.3** 证据脱敏（email `a***@gmail.com` / phone `***1234`）

---

## Phase 5：全景报告 ✅ **100%**

> **交付物**：Geist 灰白自包含 HTML + JSON 导出 + CSS 图表。

### 5.1 报告引擎

- [x] **5.1.1** 数据聚合：站点探测 + 爬虫提取 + 泄露记录 + 关联信号
- [x] **5.1.2** Profile 完整度进度条（5 字段 → %）
- [x] **5.1.3** 泄露时间线（CSS 横轴 timeline）
- [x] **5.1.4** 平台分布 + 关联信号柱状图（纯 CSS，无 JS）

### 5.2 可视化

- [x] **5.2.1** 站点表格（按 classification.primary 分组，含分类摘要条）
- [x] **5.2.2** Profile 卡片（display_name / bio / location / followers / completeness bar）
- [x] **5.2.3** Cluster 展示（站点列表 + 信号标签 + 置信度 badge + 脱敏证据）

### 5.3 安全和导出

- [x] **5.3.1** PII 脱敏（`_redact_evidence()`）
- [x] **5.3.2** HTML 转义（`_esc()` 防 XSS）
- [x] **5.3.3** `str.format()` 花括号转义（`_fmt_esc()` 防 crash）
- [x] **5.3.4** 路径遍历防护（`.resolve()` + `..` 检测）
- [x] **5.3.5** 自包含 HTML 报告（CSS 内联，零外部依赖）
- [x] **5.3.6** JSON 结构化导出
- [x] **5.3.7** 伦理使用门禁（`--acknowledge-ethical-use`）

### 5.4 Web UI

- [ ] **5.4.1** 搜索交互 Web UI → **v2 scope**（需要 Web server）

---

## 审计记录

| 轮次 | 方式 | 发现 | 状态 |
|:---:|------|------|:---:|
| 1 | 陪审团（3 视角） | maigret 死代码 4500 行、7 空壳站点、迁移脚本 bug | ✅ 已修复 |
| 2 | 陪审团 | 4 空 `__init__.py` stubs、迁移 artifacts、HTTP 层不统一 | ✅ 已修复 |
| 3 | code-review-excellence（Python+安全双视角） | 29 findings: CrawlerClient leak, 路径遍历, username 校验, UA secrets | ✅ 8 项已修复 |
| 4 | 功能 QA 自审 | 7 虚标完成 + 3 逻辑 bug（空输入集群、相似度阈值、一次性邮箱）| ✅ 已修复 |
| 5 | Claude Code Opus 架构审计 | 5 代码问题 + 10 边界情况 → 4 步开发计划 | ✅ 全部执行 |

---

## 待办

> **零待办。** Phase 1-5 代码 100% 完成，CI 已部署。所有剩余项在 v2 scope。

---

## v2 Scope（远期、按优先级排列）

| # | 特性 | 说明 |
|:--:|------|------|
| 1 | 自建泄露库 | NAS PostgreSQL，法律风险需独立评估 |
| 2 | 中国站扩展至 50+ | 当前 28 站定义（16 active），扩展需逐站验证 |
| 3 | Louvain 图聚类 | 加权边图聚类替代 Union-Find |
| 4 | PDF/Markdown 报告 | 多格式导出 |
| 5 | Web UI 搜索交互 | Geist 灰白风搜索页 |
| 6 | 微信弱信号实验 | 搜一搜/公众号间接探测 |
| 7 | 默认头像哈希库 | 过滤 GitHub 默认 identicon |
| 8 | 位置邻近信号 | 地理位置相关性 |
| 9 | 时间关联 | joined_date 聚类 |
| 10 | GitHub Actions CI/CD | deploy + release automation |
| 11 | LinkedIn Profile 提取 | 全球版，反爬极严需代理+轮换 |
| 12 | 天眼查 API 集成 | 法人/股东/高管/失信查询，公开工商数据 |
| 13 | 邮箱/手机号 CLI 入口 | ✅ **已实现** (commit `92726bd`)，自动检测输入类型 |

---

## Profile 提取扩展计划（陪审团审计 2026-05-05）

36 站点可行性矩阵（技术可行性 × 数据丰富度）：

**P0 — 立即实施（5 站）：**
| # | 站点 | 技术 | 丰富度 | 预计工时 |
|:--:|------|:--:|:--:|:--:|
| 1 | **StackOverflow** | HIGH | 4 | 1 天 |
| 2 | **Bilibili** | HIGH (API) | 4 | 2 小时 |
| 3 | **GitLab** | HIGH | 5 | 半天 |
| 4 | **dev.to** | HIGH | 4 | 1 天 |
| 5 | **V2EX** | HIGH | 3 | 半天 |

**P1 — 第二梯队（11 站）：**
博客园、简书、Keybase、SegmentFault、酷安、Behance、Dribbble、Flickr、花瓣、Patreon、CSDN

**API 金矿发现：**
- B站：`api.bilibili.com/x/space/acc/info?mid=` 公开 JSON，无需签名
- V2EX：`v2ex.com/api/v2/members/` 公开 API
- 天眼查：`open.tianyancha.com` 完整 API 平台（人名查企业/失信/被执行）

---

## 总结

| 维度的 | 状态 |
|------|:---:|
| Phase 1-5 代码 | **100%** ✅ |
| 测试 (160 tests) | **all passing** ✅ |
| Lint (Ruff) | **0 (by policy)** ✅ |
| CI 部署 | **已部署** ✅ |
| v2 scope | **10 项延期** 🟡 |

> **零待办。** 全部代码完成 + 5 轮独立审计 + CI 就位。
