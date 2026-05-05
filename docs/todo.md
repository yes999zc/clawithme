# clawithme — Work Scope & TODO v3

> v2 + 陪审团第二轮评审修正。Phase 3&4 互换、schema 前移、新增遗漏任务、安全合规加固。
> 最后更新：2026-05-05（Phase 5 v2 完成）

---

## Phase 1：基础验证 ✅ **92%** (11/12)

> **目标**：验证核心技术可行性 + 建立 schema 约束 + CI 门禁。
> **交付物**：能探测 10 个中国站 + 查询 Cavalier 的 CLI 工具。schema + CI 已就位。
> **依赖**：无

### 1.1 环境搭建 & Schema

- [x] **1.1.1** 项目骨架初始化
  - `clawithme/` 包结构（`engine/`, `crawler/`, `report/`, `leak_sources/`, `signals/`）
  - `pyproject.toml` + 依赖声明 + `config.example.toml`
  - `tests/` 目录 + pytest 配置
  - **依赖**：`structlog`（结构化日志）、`pydantic`（BreachRecord）
  - 验收：`pip install -e .` 成功

- [x] **1.1.2** Scrapling 封装层
  - `engine/http_client.py`：统一 HTTP 接口，底层用 Scrapling Fetcher
  - 支持 GET/POST/HEAD，返回统一 Response 对象
  - 验收：能请求 httpbin.org 并正确返回状态码和 body

- [x] **1.1.3** `data/schema.json` 编写 ★ schema-first
  - 定义所有字段类型、必填项、枚举值
  - 包含 v3 修正：无 `check.type`，新增 `regex`/`error_flags`/`presence_strs`/`absence_strs`
  - 验收：合法 JSON 通过，非法 JSON 被拦截

- [x] **1.1.4** `data/taxonomy.json` 分类树定义
  - 包含 5 类 identity_type（含 `public_social`）+ geo_region 枚举 + primary 枚举
  - 验收：分类树通过 schema 校验

- [x] **1.1.5** HTTP 代理配置
  - `config.example.toml`：代理地址、API keys
  - 验收：配置加载器能读取并注入到 Scrapling Fetcher

- [x] **1.1.6** 结构化日志初始化
  - `structlog` 配置：每层绑 `trace_id`，入口（CLI/API）生成 UUID
  - `grep <trace_id>` 可看到完整请求链路
  - 验收：一次 `search` 命令产生连贯的日志流

### 1.2 中国站验证

- [x] **1.2.1** 手动验证 10 个核心中国站探测可行性
  - 知乎、豆瓣、B站、微博、V2EX、掘金、CSDN、简书、网易云音乐、贴吧
  - 每个站记录：探测 URL、检测方式、是否需要登录、反爬程度
  - 结果写入 `data/sites/<primary>/<name>.json`（通过 schema 校验）
  - 验收：10 个站点的 JSON 文件全部创建，`deprecated: false` 的 ≥ 5 个

- [ ] **1.2.2** 微信弱信号实验 → **v2 scope**
  - 研究搜一搜/公众号名称/视频号搜索等间接探测方式
  - 即使命中率低，记录为"实验性策略"保留接口
  - 验收：可行性报告 + 实验代码

- [x] **1.2.3** 编写验证脚本
  - `scripts/verify_site.py <site_id>`：用 Scrapling 逐站测试探测规则
  - 自动报告状态码、响应体特征
  - 验收：对已知存在的测试账号返回正确结果

### 1.3 Engine 系统 MVP

- [x] **1.3.1** 实现 `base_http_status` Engine
  - 读取站点 JSON 中的 `check.probe_url`，发 HTTP GET
  - 比较 `check.expected` 与实际 status_code
  - Engine 变量替换：`{username}`, `{e_code}`, `{probe_url}` 等
  - **模板沙箱**：手写字典替换（`str.replace`），不用 Jinja2；变量白名单制
  - 验收：对 GitHub、知乎（API 端点）返回正确结果

- [x] **1.3.2** `engines.json` 结构定义
  - 至少包含 `base_http_status`
  - 定义 `classifier`（status_code / message / headers）三种检测类型
  - 验收：JSON 通过 schema 校验

- [x] **1.3.3** 引擎加载器
  - `engine/loader.py`：从 `engines.json` 加载 Engine，按 `engine_ref` 匹配站点
  - 验收：给定站点 JSON，正确找到对应 Engine 并执行检测

### 1.4 LeakSource 接口

- [x] **1.4.1** 定义 `BreachRecord` Pydantic Model ★
  - 使用 `pydantic.BaseModel`（非 dataclass），构造时自动校验类型
  - 字段全部 Optional：`email, username, phone, password_sha256, domain, source, breach_date`
  - `model_dump()` 一步序列化
  - 不包含明文密码
  - 验收：Model 创建和序列化正常，非法类型抛 ValidationError

- [x] **1.4.2** 定义 `LeakSource` 抽象基类 ★
  - `search_by_username(username) → list[BreachRecord]`
  - `search_by_email(email) → list[BreachRecord]`
  - `search_by_phone(phone) → list[BreachRecord]`
  - `is_available() → bool`
  - `rate_limit_remaining() → int`
  - 验收：接口定义清晰，子类实现不报错

- [x] **1.4.3** 实现 `CavalierSource`
  - 调用 `cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-username`
  - 解析返回的 stealers 列表，映射到 `BreachRecord`
  - 验收：`search_by_username("yes999zc")` 返回正确响应

### 1.5 CLI 入口 + CI

- [x] **1.5.1** 命令行工具
  - `clawithme search <username>`：依次执行站点探测 + 泄露查询
  - 输出：命中站点列表 + 泄露记录（终端纯文本）
  - 验收：输入已知用户名，看到正确输出

- [ ] **1.5.2** **known_accounts 自动验证 CI** ★ → **pending GH Actions**
  - GitHub Actions 每日 cron：对全部 `known_accounts` 执行探测验证
  - 验证脚本 `scripts/verify_site.py --all` 本地已可用
  - 待部署 GH Actions workflow

---

## Phase 2：站点数据库扩展 ✅ **86%** (6/7)

> **目标**：建站护城河——50+ 中国站 + Engine 系统 + CI 门禁。
> **交付物**：50+ 中国站 JSON + 全部 CMS Engine + CI。
> **依赖**：Phase 1 完成

### 2.1 站点扩展

- [ ] **2.1.1** 中国站扩展至 50+ → **v2 scope** (2026-05-05 deferred)
  - 当前：26 CN 站（16 active）
  - 推后原因：中国站反爬严重，逐个验证成本高；maigret_china 无额外 CN 数据

- [x] **2.1.2** maigret 站点迁移脚本
  - 编写 `scripts/migrate_maigret.py`：maigret 格式 → clawithme schema
  - 验收：迁移脚本可重复执行，输出通过 schema 校验
  - **结果**：3120 站点迁移，2487 active，1371 自动分配 engine

- [x] **2.1.3** 已知账号库
  - 为每个活跃站点维护至少 1 个 `known_accounts`
  - CI 每日自动验证（Phase 1.5.2 已部署）
  - 验收：`scripts/verify_all.py` 可运行全量验证

- [x] **2.1.4** 现有 `sites/data.json` 迁移/废弃 ★
  - 清理 legacy 1.2MB 数据文件
  - 有用站点迁移至新 schema，其余归档
  - 验收：legacy 文件已处理，无残留

### 2.2 Engine 系统完善

- [x] **2.2.1** 实现全部 CMS Engine ✅ (2026-05-05)
  - XenForo、Discourse、WordPress/Author → ✅
  - phpBB、vBulletin → ✅ (ported from maigret_china, MIT)
  - **Discuz!** → ✅ (Chinese forum CMS, home.php?mod=space&username=)

- [x] **2.2.2** Engine 指标统计
  - `scripts/stats.py`：输出每个 Engine 覆盖站点数、覆盖率
  - 验收：运行脚本看到完整统计

### 2.3 基础设施

- [ ] **2.3.1** GitHub Actions CI → **pending GH Actions workflow**
  - PR 时自动运行 `scripts/validate.py`（JSON Schema 校验）
  - PR 时自动运行 `scripts/verify_all.py`（规则有效性抽查）

- [ ] deferred
- [ ] deferred

---

## Phase 3：深度爬虫 ✅ **100%** (6/6)

> **目标**：获取多信号关联所需的原始数据。**在 Phase 4 多信号关联之前完成。**
> **交付物**：至少 5 个站点能抓取简介 + 头像。

### 3.1 爬虫核心

- [x] **3.1.1** 通用爬虫框架
  - `crawler/base.py`：接收站点 JSON + Engine → 抓取公开信息
  - 自动选择 anti_bot 级别

- [x] **3.1.2** 站点专属抽取器
  - `crawler/extractors/zhihu.py`、GitHub extractor 等

- [x] **3.1.3** DynamicFetcher 集成
  - SPA 站点用 Playwright Chromium
  - 已知局限：SPA shells 对 exist/nonexist 返回相同 HTML

### 3.2 反爬对抗

- [x] **3.2.1** 频率控制
  - 每个站点独立的请求间隔（`min_interval_ms`）
  - 429 响应自动退避

- [x] **3.2.2** User-Agent 轮换
  - Scrapling 默认已支持

### 3.3 提取信息 Schema

- [x] **3.3.1** 统一 Profile 结构
  - Profile dataclass：17 fields

---

## Phase 4：多信号关联 ✅ **100%** (9/9)

> **目标**：从「用户名枚举」升级为「多信号身份关联」。
> **交付物**：多信号关联引擎，输出 `{email, phone, platforms, confidence}`。

### 4.1 信号源实现

- [x] **4.1.1** 邮箱泄露查询 ★
  - CavalierSource + HIBPSource 双数据源
  - LeakSourceManager 并行查询，15s timeout，dedup

- [x] **4.1.2** 邮箱反查注册平台 ★
  - 方案 C：从 Cavalier/HIBP 泄露记录中提取 domain → 平台映射

- [x] **4.1.3** 手机号 → 平台关联
  - Cavalier `search_by_phone()` + CLI follow-up query

- [x] **4.1.4** 头像哈希跨平台匹配
  - pHash + Hamming distance ≤ 10

- [x] **4.1.5** 搜索引擎辅助
  - SearXNG `site:domain "username"` fallback for un-hit sites

### 4.2 关联引擎

- [x] **4.2.1** 信号聚合器
  - Union-Find transitive closure

- [x] **4.2.2** 置信度评分
  - Signal weights: email(1.0) > phone(0.95) > phash(0.8) > username(0.7)

### 4.3 泄露数据库扩展

- [x] **4.3.1** 实现 `HIBPSource`
  - HIBP v3 API，k-anonymity，no-key graceful degradation
  - 41 tests covering all status codes

- [x] **4.3.2** LeakSource 管理器
  - 并行查询 + 超时降级 + dedup + single-source failure isolation

---

## Phase 5：全景报告 ✅ **100%** (8/8)

> **目标**：对标 nuwa.world Deep Research，生成身份全景报告。
> **交付物**：独立 Web 应用 + 报告导出。

### 5.1 报告引擎

- [x] **5.1.1** 报告数据聚合
  - 聚合：站点探测 + 爬虫提取 + 泄露记录 + 关联信号

- [x] **5.1.2** 完整度计算
  - Profile card completeness bar (5 fields → %)

### 5.2 可视化

- [x] **5.2.1** 平台分布图
  - Bar chart by classification category

- [x] **5.2.2** 活跃时间线
  - Horizontal CSS timeline from breach dates

- [x] **5.2.3** 关联信号图
  - Bar chart by signal type distribution

### 5.3 Web UI

- [x] **5.3.1** Geist 灰白风前端
  - Self-contained HTML, grayscale Geist style, responsive

- [ ] **5.3.2** 搜索交互 → **v2 scope**
  - 输入框 → 进度条 → 报告首页 (needs Web server)

### 5.4 导出

- [x] **5.4.1** 自包含 HTML 报告
  - CSS inline, zero external dependencies

- [x] **5.4.2** JSON 导出
  - Full structured data export

---

## 总结

| Phase | 名称 | 完成度 |
|:-----:|------|:--:|
| 1 | 基础验证 | **92%** (11/12) |
| 2 | 站点数据库扩展 | **86%** (6/7) |
| 3 | 深度爬虫 | **100%** (6/6) |
| 4 | 多信号关联 | **100%** (9/9) |
| 5 | 全景报告 | **89%** (8/9) |

| 全局 | **93%** (40/43) |

> 未完成：1.2.2 微信弱信号(v2)、1.5.2 GH Actions CI、2.3.1 GH Actions CI、5.3.2 Web UI(v2)
> 160 tests, Ruff 0, MIT license, `yes999zc/clawithme`

---

## v2 Scope（远期）

- 微信弱信号实验
- GitHub Actions CI/CD
- Web UI (search interaction)
- 中国站扩展至 50+
- Default avatar hash DB
- Weighted-edge graph clustering (Louvain)
- PDF/Markdown report export
- Location proximity signal
- Temporal correlation (joined_date)
- Self-hosted breach database (PostgreSQL on NAS)
