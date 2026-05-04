# clawithme — Work Scope & TODO v3

> v2 + 陪审团第二轮评审修正。Phase 3&4 互换、schema 前移、新增遗漏任务、安全合规加固。
> 最后更新：2026-05-04

---

## Phase 1：基础验证 🔴 当前

> **目标**：验证核心技术可行性 + 建立 schema 约束 + CI 门禁。
> **交付物**：能探测 10 个中国站 + 查询 Cavalier 的 CLI 工具。schema + CI 已就位。
> **依赖**：无

### 1.1 环境搭建 & Schema

- [ ] **1.1.1** 项目骨架初始化
  - `clawithme/` 包结构（`engine/`, `crawler/`, `report/`, `leak_sources/`, `signals/`）
  - `pyproject.toml` + 依赖声明 + `config.example.toml`
  - `tests/` 目录 + pytest 配置
  - **依赖**：`structlog`（结构化日志）、`pydantic`（BreachRecord）
  - 验收：`pip install -e .` 成功

- [ ] **1.1.2** Scrapling 封装层
  - `engine/http_client.py`：统一 HTTP 接口，底层用 Scrapling Fetcher
  - 支持 GET/POST/HEAD，返回统一 Response 对象
  - 验收：能请求 httpbin.org 并正确返回状态码和 body

- [ ] **1.1.3** `data/schema.json` 编写 ★ schema-first
  - 定义所有字段类型、必填项、枚举值
  - 包含 v3 修正：无 `check.type`，新增 `regex`/`error_flags`/`presence_strs`/`absence_strs`
  - 验收：合法 JSON 通过，非法 JSON 被拦截

- [ ] **1.1.4** `data/taxonomy.json` 分类树定义
  - 包含 5 类 identity_type（含 `public_social`）+ geo_region 枚举 + primary 枚举
  - 验收：分类树通过 schema 校验

- [ ] **1.1.5** HTTP 代理配置
  - `config.example.toml`：代理地址、API keys
  - 验收：配置加载器能读取并注入到 Scrapling Fetcher

- [ ] **1.1.6** 结构化日志初始化
  - `structlog` 配置：每层绑 `trace_id`，入口（CLI/API）生成 UUID
  - `grep <trace_id>` 可看到完整请求链路
  - 验收：一次 `search` 命令产生连贯的日志流

### 1.2 中国站验证

- [ ] **1.2.1** 手动验证 10 个核心中国站探测可行性
  - 知乎、豆瓣、B站、微博、V2EX、掘金、CSDN、简书、网易云音乐、贴吧
  - 每个站记录：探测 URL、检测方式、是否需要登录、反爬程度
  - 结果写入 `data/sites/<primary>/<name>.json`（通过 schema 校验）
  - 验收：10 个站点的 JSON 文件全部创建，`deprecated: false` 的 ≥ 5 个

- [ ] **1.2.2** 微信弱信号实验
  - 研究搜一搜/公众号名称/视频号搜索等间接探测方式
  - 即使命中率低，记录为"实验性策略"保留接口
  - 验收：可行性报告 + 实验代码

- [ ] **1.2.3** 编写验证脚本
  - `scripts/verify_site.py <site_id>`：用 Scrapling 逐站测试探测规则
  - 自动报告状态码、响应体特征
  - 验收：对已知存在的测试账号返回正确结果

### 1.3 Engine 系统 MVP

- [ ] **1.3.1** 实现 `base_http_status` Engine
  - 读取站点 JSON 中的 `check.probe_url`，发 HTTP GET
  - 比较 `check.expected` 与实际 status_code
  - Engine 变量替换：`{username}`, `{e_code}`, `{probe_url}` 等
  - **模板沙箱**：手写字典替换（`str.replace`），不用 Jinja2；变量白名单制
  - 验收：对 GitHub、知乎（API 端点）返回正确结果

- [ ] **1.3.2** `engines.json` 结构定义
  - 至少包含 `base_http_status`
  - 定义 `classifier`（status_code / message / headers）三种检测类型
  - 验收：JSON 通过 schema 校验

- [ ] **1.3.3** 引擎加载器
  - `engine/loader.py`：从 `engines.json` 加载 Engine，按 `engine_ref` 匹配站点
  - 验收：给定站点 JSON，正确找到对应 Engine 并执行检测

### 1.4 LeakSource 接口

- [ ] **1.4.1** 定义 `BreachRecord` Pydantic Model ★
  - 使用 `pydantic.BaseModel`（非 dataclass），构造时自动校验类型
  - 字段全部 Optional：`email, username, phone, password_sha256, domain, source, breach_date`
  - `model_dump()` 一步序列化
  - 不包含明文密码
  - 验收：Model 创建和序列化正常，非法类型抛 ValidationError

- [ ] **1.4.2** 定义 `LeakSource` 抽象基类 ★
  - `search_by_username(username) → list[BreachRecord]`
  - `search_by_email(email) → list[BreachRecord]`
  - `search_by_phone(phone) → list[BreachRecord]`
  - `is_available() → bool`
  - `rate_limit_remaining() → int`
  - 验收：接口定义清晰，子类实现不报错

- [ ] **1.4.3** 实现 `CavalierSource`
  - 调用 `cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-username`
  - 解析返回的 stealers 列表，映射到 `BreachRecord`
  - 验收：`search_by_username("yes999zc")` 返回正确响应

### 1.5 CLI 入口 + CI

- [ ] **1.5.1** 命令行工具
  - `clawithme search <username>`：依次执行站点探测 + 泄露查询
  - 输出：命中站点列表 + 泄露记录（终端纯文本）
  - 验收：输入已知用户名，看到正确输出

- [ ] **1.5.2** **known_accounts 自动验证 CI** ★ 防止数据库早衰
  - GitHub Actions 每日 cron：对全部 `known_accounts` 执行探测验证
  - 失效规则自动报告（不自动修改，人工确认）
  - 验收：失效检测报告可正常生成

---

## Phase 2：站点数据库扩展

> **目标**：建站护城河——50+ 中国站 + Engine 系统 + CI 门禁。
> **交付物**：50+ 中国站 JSON + 全部 CMS Engine + CI。
> **依赖**：Phase 1 完成

### 2.1 站点扩展

- [ ] **2.1.1** 中国站扩展至 50+
  - 包括：所有 Phase 1 已验证站 + 虎扑、NGA、少数派、什么值得买、AcFun、酷安、站酷、花瓣、LOFTER、百度知道、天涯社区
  - 标注分类维度（identity_type / geo_region / user_scale / tags）
  - 验收：50+ 中国站 JSON 文件，全部通过 schema 校验

- [ ] **2.1.2** maigret 站点迁移脚本
  - 编写 `scripts/migrate_maigret.py`：maigret 格式 → clawithme schema
  - 验收：迁移脚本可重复执行，输出通过 schema 校验

- [ ] **2.1.3** 已知账号库
  - 为每个活跃站点维护至少 1 个 `known_accounts`
  - CI 每日自动验证（Phase 1.5.2 已部署）
  - 验收：`scripts/verify_all.py` 可运行全量验证

- [ ] **2.1.4** 现有 `sites/data.json` 迁移/废弃 ★
  - 清理 legacy 1.2MB 数据文件
  - 有用站点迁移至新 schema，其余归档
  - 验收：legacy 文件已处理，无残留

### 2.2 Engine 系统完善

- [ ] **2.2.1** 实现全部 CMS Engine
  - XenForo、phpBB、Discourse、vBulletin、WordPress/Author、Discuz!
  - 每种 Engine 至少覆盖 3 个已知站点
  - 验收：每个 Engine 的测试用例通过

- [ ] **2.2.2** Engine 指标统计
  - `scripts/stats.py`：输出每个 Engine 覆盖站点数、覆盖率
  - 验收：运行脚本看到完整统计

### 2.3 基础设施

- [ ] **2.3.1** GitHub Actions CI
  - PR 时自动运行 `scripts/validate.py`（JSON Schema 校验）
  - PR 时自动运行 `scripts/verify_all.py`（规则有效性抽查）
  - 验收：非法 JSON 或失效规则被 CI 拦截

- [ ] **2.3.2** CONTRIBUTING.md
  - 站点提交模板 + 示例
  - 新增站点的步骤说明 + schema 校验要求
  - 验收：按文档操作可无歧义完成站点贡献

- [ ] **2.3.3** 监控存活探针 ★
  - 部署 healthchecks.io 或自建 cron 定时 ping 采集器状态
  - 中国站隔离路径独立健康检查
  - 验收：采集器离线 5 分钟内收到告警

---

## Phase 3：深度爬虫（原 Phase 4，提前）

> **目标**：获取多信号关联所需的原始数据。**在 Phase 4 多信号关联之前完成。**
> **交付物**：至少 5 个站点能抓取简介 + 头像。
> **依赖**：Phase 2 站点数据库可用

### 3.1 爬虫核心

- [ ] **3.1.1** 通用爬虫框架
  - `crawler/base.py`：接收站点 JSON + Engine → 抓取公开信息
  - 自动选择 anti_bot 级别
  - 验收：对 GitHub 爬取用户简介和头像

- [ ] **3.1.2** 站点专属抽取器（与 Phase 2 站点扩展同步编写）
  - 为高频站点编写 CSS/XPath 规则
  - `crawler/extractors/zhihu.py`、`crawler/extractors/github.py` 等
  - 验收：每个专属抽取器有测试用例

- [ ] **3.1.3** DynamicFetcher 集成
  - SPA 站点（React/Vue 渲染的页面）用 Playwright Chromium
  - 验收：对 React 站点正确提取 JS 渲染后的内容

### 3.2 反爬对抗

- [ ] **3.2.1** 频率控制
  - 每个站点独立的请求间隔（`min_interval_ms`）
  - 429 响应自动退避
  - 验收：模拟 429 响应触发退避

- [ ] **3.2.2** User-Agent 轮换
  - 维护 UA 池，Scrapling 默认已支持
  - 验收：连续 10 次请求 UA 不完全相同

### 3.3 提取信息 Schema

- [ ] **3.3.1** 统一 Profile 结构
  - `crawler/schema.py`：定义 `Profile` dataclass
  - 字段：platform, username, display_name, avatar_url, avatar_hash, bio, url, joined_date, last_active, follower_count, recent_posts
  - 验收：至少 3 类平台可正确序列化

---

## Phase 4：多信号关联（原 Phase 3，后移）

> **目标**：从「用户名枚举」升级为「多信号身份关联」。
> **交付物**：多信号关联引擎，输出 `{email, phone, platforms, confidence}`。
> **依赖**：Phase 3 爬虫数据 + Phase 1 LeakSource 接口

### 4.1 信号源实现

- [ ] **4.1.1** 邮箱 → 平台关联
  - 用泄露数据库查到邮箱
  - 对已知邮箱在支持的平台上检查注册状态
  - 验收：输入已知邮箱，返回关联的平台列表

- [ ] **4.1.2** 手机号 → 平台关联
  - 类似邮箱流程
  - 附加：手机号归属地查询（运营商 + 城市）
  - 验收：输入已知手机号，返回关联结果

- [ ] **4.1.3** 头像哈希跨平台匹配
  - 使用 Phase 3 抓回的 `avatar_hash`（perceptual hash / pHash）
  - 不同平台间比较头像哈希，判断是否为同一人
  - 验收：同一人不同平台头像 → 哈希距离 < 阈值；不同人头像 → 哈希距离 > 阈值

- [ ] **4.1.4** 搜索引擎辅助
  - 对未命中站点，用 SearXNG 执行 `site:v2ex.com "username"`
  - 解析搜索结果判断是否存在
  - 验收：对已知存在但 HTTP 探测失败的案例，搜索结果能发现

### 4.2 关联引擎

- [ ] **4.2.1** 信号聚合器
  - 输入用户名 → 并行调用所有信号源 → 聚合去重
  - 按信号强度排序输出
  - 验收：输出包含 {email, phone, platforms, confidence}

- [ ] **4.2.2** 置信度评分
  - 单一信号：低置信度（30-50%）
  - 邮箱+手机号+头像三信号命中同一人：高置信度（90%+）
  - 验收：评分逻辑文档化 + 单元测试覆盖

### 4.3 泄露数据库扩展

- [ ] **4.3.1** 实现 `HIBPSource`
  - 封装 HaveIBeenPwned API v3
  - 按邮箱查询泄露记录
  - 验收：查询已知泄露邮箱返回正确的 breach 记录

- [ ] **4.3.2** LeakSource 管理器
  - 统一管理多个数据源，按优先级查询
  - 自动降级（Cavalier 超时 → HIBP → 返回已有结果）
  - 验收：多数据源并行查询 + 超时降级

---

## Phase 5：全景报告（终局）

> **目标**：对标 nuwa.world Deep Research，生成身份全景报告。
> **交付物**：独立 Web 应用 + 报告导出。
> **依赖**：Phase 3 + Phase 4 可用

### 5.1 报告引擎

- [ ] **5.1.1** 报告数据聚合
  - 聚合：站点探测结果 + 爬虫提取信息 + 泄露记录 + 关联信号
  - 去重 + 排序 + 置信度标注
  - 验收：输入用户名，输出完整的报告数据 dict

- [ ] **5.1.2** 完整度计算
  - 根据信号数量和质量计算百分比
  - 类似 nuwa 的 "96% 完整度"
  - 验收：公式文档化，不同场景有区分度

### 5.2 可视化

- [ ] **5.2.1** 平台分布图
  - 哪些平台有账号（✅ / ❌ / ⚠️ 需验证）
  - 按分类维度分组展示
  - 验收：一目了然的平台地图

- [ ] **5.2.2** 活跃时间线
  - 各平台首次出现和最后活跃时间
  - 标注关键时间节点
  - 验收：时间线清晰可读

- [ ] **5.2.3** 关联信号图
  - 展示用户名 → 邮箱 → 手机号 → 平台的关联链
  - 验收：血缘关系一目了然

### 5.3 Web UI

- [ ] **5.3.1** Geist 灰白风前端
  - 纯白底 + 灰文字 + 黑线框 + 无渐变无 emoji
  - 移动端响应式
  - 验收：视觉审查通过

- [ ] **5.3.2** 搜索交互
  - 输入框 → 进度条 → 报告首页
  - 各板块展开/折叠
  - 验收：交互流畅，无闪烁

### 5.4 导出

- [ ] **5.4.1** 自包含 HTML 报告
  - CSS 内联，可直接分享/打印
  - 验收：浏览器打开完整渲染，无外部依赖

- [ ] **5.4.2** JSON 导出
  - 完整结构化数据
  - 供下游工具消费
  - 验收：JSON Schema 校验通过

---

## v2 Scope（远期）

> 以下功能从主线 Phase 移入 v2 范围。

### V2.1 泄露数据库自建（原 Phase 5）

- [ ] NAS PostgreSQL 部署
- [ ] 数据库 Schema（password_sha256 替代明文）
- [ ] 下载泄露数据集
- [ ] 数据清洗与批量导入
- [ ] GIN Trigram 索引
- [ ] 查询 API
- [ ] `SelfHostedSource` 实现

**推后原因**：法律风险需独立评估（中国《刑法》第285条）；v1 以 API 聚合层替代。

### V2.2 2000+ 全球站点迁移

- [ ] maigret 3156 站点全量迁移
- [ ] 活跃站点筛选 + known_accounts 验证
- [ ] deprecated 标记 + 死站清理

**推后原因**：单人维护 2000+ 站点不可持续；v1 聚焦中国站。

### V2.3 中国站插件独立仓库

- [ ] `clawithme-cn` 独立仓库
- [ ] 中国站 JSON 文件
- [ ] 中国站专属抽取器
- [ ] 微信弱信号实验模块
- [ ] 用户自行安装即承担合规责任

---

## 附录 A：文件结构全貌 v3

```
clawithme/
├── docs/
│   ├── discussion-log.md      # 讨论记录
│   ├── technical-roadmap.md   # 技术路线（本文件）
│   └── todo.md                # Work scope（本文件）
├── data/
│   ├── schema.json            # JSON Schema 校验（Phase 1 即写）
│   ├── taxonomy.json          # 分类树（Phase 1 即写）
│   ├── engines.json           # Engine 定义
│   └── sites/                 # 一个站点一个 JSON（全球站，不含 cn）
│       ├── social/
│       ├── devtools/
│       ├── forum/             # 统一单数
│       ├── media/
│       └── ...
├── config.example.toml        # 代理/API keys 配置
├── clawithme/                 # Python 包
│   ├── __init__.py
│   ├── cli.py                 # CLI 入口
│   ├── orchestrator.py        # 编排层
│   ├── engine/                # 探测引擎
│   │   ├── __init__.py
│   │   ├── http_client.py     # Scrapling 封装
│   │   ├── loader.py          # Engine 加载
│   │   ├── checker.py         # 检测逻辑
│   │   └── engines.py         # Engine 类定义
│   ├── crawler/               # 深度爬虫（Phase 3）
│   │   ├── __init__.py
│   │   ├── base.py            # 通用爬虫
│   │   ├── schema.py          # Profile dataclass
│   │   └── extractors/        # 站点专属抽取
│   ├── signals/               # 多信号关联（Phase 4）
│   │   ├── __init__.py
│   │   ├── email.py
│   │   ├── phone.py
│   │   ├── avatar.py
│   │   └── search_engine.py
│   ├── report/                # 全景报告（Phase 5）
│   │   ├── __init__.py
│   │   ├── aggregator.py      # 数据聚合
│   │   └── renderer.py        # 报告渲染
│   └── leak_sources/          # 泄露数据库
│       ├── __init__.py        # LeakSource ABC + BreachRecord
│       ├── cavalier.py
│       ├── hibp.py
│       └── self_hosted.py     # v2 scope
├── scripts/
│   ├── verify_site.py         # 单站验证
│   ├── verify_all.py          # 全量验证
│   ├── validate.py            # JSON Schema 校验
│   ├── stats.py               # 统计
│   └── migrate_maigret.py     # maigret → clawithme 迁移
├── .github/
│   └── workflows/
│       ├── ci.yml             # PR: schema校验 + 规则抽查
│       └── daily-verify.yml   # 每日: known_accounts 全量验证
├── tests/
│   ├── test_engines.py
│   ├── test_leak_sources.py
│   ├── test_signals.py
│   └── test_crawler.py
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
└── .gitignore
```

---

## 附录 B：Phase 对比 v2 → v3

| Phase | v2 | v3 | 变更原因 |
|-------|-----|-----|----------|
| 1 | 基础验证 | 基础验证 + **schema/taxonomy 前移** + **CI 门禁** | 陪审团：schema 太晚会导致返工；规则腐烂是最大风险 |
| 2 | 站点数据库 | 站点数据库（**2000 全球站 → v2**） | 残酷实用主义者：单人 6-12 月不可行 |
| 3 | 多信号关联 | **深度爬虫**（原 Phase 4） | 残酷实用主义者：关联需要爬虫数据先到位 |
| 4 | 深度爬虫 | **多信号关联**（原 Phase 3） | 同上 |
| 5 | 泄露自建 | **全景报告**（原 Phase 6） | 泄露自建 → v2 scope（法律风险） |
| 6 | 全景报告 | —（并入 Phase 5） | Phase 总数从 6 减至 5 |
| v2 | — | **泄露自建 + 2000 全球站 + cn 插件** | 远期范围 |

---

## 附录 C：验收标准速查 v3

| Phase | 核心验收标准 |
|-------|-------------|
| 1 | `clawithme search <username>` 返回 10 个中国站结果 + Cavalier 泄露记录；schema + CI 已就位 |
| 2 | 50+ 中国站 JSON，全部通过 schema 校验；全部 CMS Engine 可用 |
| 3 | 至少 5 个站点能抓取简介 + 头像哈希 |
| 4 | 多信号关联引擎输出 `{email, phone, platforms, confidence}` |
| 5 | Web UI 生成可分享的自包含 HTML 全景报告 |
