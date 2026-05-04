# clawithme — Work Scope & TODO

> 每个 Phase 的任务拆解。打勾 = 已完成。
> 最后更新：2026-05-04

---

## Phase 1：基础验证 🔴 当前

> **目标**：验证核心技术可行性，不求完整。
> **交付物**：能探测 10 个中国站 + 查询 Cavalier 的 CLI 工具。
> **依赖**：无
> **预估**：—（待评估）

### 1.1 环境搭建

- [ ] **1.1.1** 项目骨架初始化
  - `clawithme/` 包结构（`engine/`, `crawler/`, `report/`, `leak_sources/`）
  - `pyproject.toml`（或 `setup.py`）+ 依赖声明
  - `tests/` 目录 + pytest 配置
  - 验收：`pip install -e .` 成功

- [ ] **1.1.2** Scrapling 封装层
  - `engine/http_client.py`：统一 HTTP 接口，底层用 Scrapling Fetcher
  - 支持 GET/POST/HEAD，返回统一 Response 对象
  - 验收：能请求 httpbin.org 并正确返回状态码和 body

### 1.2 中国站验证

- [ ] **1.2.1** 手动验证 10 个核心中国站探测可行性
  - 知乎、豆瓣、B站、微博、V2EX、掘金、CSDN、简书、网易云音乐、贴吧
  - 每个站记录：探测 URL、检测方式、是否需要登录、反爬程度
  - 结果写入 `data/sites/<name>.json`
  - 验收：10 个站点的 JSON 文件全部创建，`deprecated: false` 的 ≥ 5 个

- [ ] **1.2.2** 编写验证脚本
  - `scripts/verify_site.py <site_id>`：用 Scrapling 逐站测试探测规则
  - 自动报告状态码、响应体特征
  - 验收：对已知存在的测试账号返回正确结果

### 1.3 Engine 系统 MVP

- [ ] **1.3.1** 实现 `base_http_status` Engine
  - 读取站点 JSON 中的 `check.probe_url`，发 HTTP GET
  - 比较 `check.expected` 与实际 status_code
  - 验收：对 GitHub、知乎（API 端点）返回正确结果

- [ ] **1.3.2** `engines.json` 结构定义
  - 至少包含 `base_http_status`
  - 定义 `classifier`（status_code / message / headers）三种检测类型
  - 验收：JSON 通过 schema 校验

- [ ] **1.3.3** 引擎加载器
  - `engine/loader.py`：从 `engines.json` 加载 Engine，按 `engine_ref` 匹配站点
  - 验收：给定站点 JSON，正确找到对应 Engine 并执行检测

### 1.4 LeakSource 接口

- [ ] **1.4.1** 定义 `LeakSource` 抽象基类
  - `search_by_username(username) → list`
  - `search_by_email(email) → list`
  - 返回统一 Schema：`[{email, username, phone, source, breach_date}]`
  - 验收：接口定义清晰，子类实现不报错

- [ ] **1.4.2** 实现 `CavalierSource`
  - 调用 `cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-username`
  - 解析返回的 stealers 列表，映射到统一 Schema
  - 验收：`search_by_username("yes999zc")` 返回正确响应

### 1.5 CLI 入口

- [ ] **1.5.1** 命令行工具
  - `clawithme search <username>`：依次执行站点探测 + 泄露查询
  - 输出：命中站点列表 + 泄露记录（终端纯文本）
  - 验收：输入已知用户名，看到正确输出

---

## Phase 2：站点数据库扩展

> **目标**：建立护城河——完整的站点数据库 + Engine 系统。
> **交付物**：50+ 中国站 + 精选全球站 + 完整 Engine。
> **依赖**：Phase 1 完成

### 2.1 站点扩展

- [ ] **2.1.1** 中国站扩展至 50+
  - 包括：所有 Phase1 已验证站 + 虎扑、NGA、少数派、什么值得买、AcFun、酷安、站酷、花瓣、LOFTER 等
  - 标注分类维度（identity_type / geo_region / user_scale）
  - 验收：50+ 中国站 JSON 文件

- [ ] **2.1.2** 引入 maigret 3156 站点
  - 编写迁移脚本：maigret 格式 → clawithme schema
  - 筛选活跃站点（known_accounts 仍可验证的保留，其他标记 deprecated）
  - 去掉重复和死站，目标保留 ~2000 站点
  - 验收：迁移脚本可重复执行，输出通过 schema 校验

- [ ] **2.1.3** 已知账号库
  - 为每个活跃站点维护至少 1 个 `known_accounts`
  - 用于 CI 自动验证检测规则是否失效
  - 验收：`scripts/verify_all.py` 可运行全量验证

### 2.2 Engine 系统完善

- [ ] **2.2.1** 实现全部 CMS Engine
  - XenForo、phpBB、Discourse、vBulletin、WordPress/Author、Discuz!
  - 每种 Engine 至少覆盖 3 个已知站点
  - 验收：每个 Engine 的测试用例通过

- [ ] **2.2.2** Engine 指标统计
  - `scripts/stats.py`：输出每个 Engine 覆盖站点数、覆盖率
  - 验收：运行脚本看到完整统计

### 2.3 基础设施

- [ ] **2.3.1** JSON Schema 校验
  - `data/schema.json` 定义所有字段格式、必填、枚举值
  - CI（GitHub Actions）：PR 时自动运行 `scripts/validate.py`
  - 验收：非法 JSON 被 CI 拦截

- [ ] **2.3.2** CONTRIBUTING.md
  - 站点提交模板 + 示例
  - 新增站点的步骤说明
  - 验收：按文档操作可无歧义完成站点贡献

---

## Phase 3：多信号关联

> **目标**：从「用户名枚举」升级为「多信号身份关联」。
> **交付物**：多信号关联引擎。
> **依赖**：Phase 2 站点数据库可用

### 3.1 信号源实现

- [ ] **3.1.1** 邮箱 → 平台关联
  - 用泄露数据库查到邮箱
  - 对已知邮箱在支持的平台上检查注册状态
  - 验收：输入已知邮箱，返回关联的平台列表

- [ ] **3.1.2** 手机号 → 平台关联
  - 类似邮箱流程
  - 附加：手机号归属地查询（运营商 + 城市）
  - 验收：输入已知手机号，返回关联结果

- [ ] **3.1.3** 头像哈希跨平台匹配
  - 对命中站点下载头像，计算 perceptual hash（如 pHash）
  - 不同平台间比较头像哈希，判断是否为同一人
  - 验收：同一人不同平台头像 → 哈希距离 < 阈值；不同人头像 → 哈希距离 > 阈值

- [ ] **3.1.4** 搜索引擎辅助
  - 对未命中站点，用 SearXNG 执行 `site:v2ex.com "username"`
  - 解析搜索结果判断是否存在
  - 验收：对已知存在但 HTTP 探测失败的案例，搜索结果能发现

### 3.2 关联引擎

- [ ] **3.2.1** 信号聚合器
  - 输入用户名 → 并行调用所有信号源 → 聚合去重
  - 按信号强度排序输出
  - 验收：输出包含 {email, phone, platforms, confidence}

- [ ] **3.2.2** 置信度评分
  - 单一信号：低置信度（30-50%）
  - 邮箱+手机号+头像三信号命中同一人：高置信度（90%+）
  - 验收：评分逻辑文档化 + 单元测试覆盖

### 3.3 泄露数据库扩展

- [ ] **3.3.1** 实现 `HIBPSource`
  - 封装 HaveIBeenPwned API v3
  - 按邮箱查询泄露记录
  - 验收：查询已知泄露邮箱返回正确的 breach 记录

- [ ] **3.3.2** LeakSource 管理器
  - 统一管理多个数据源，按优先级查询
  - 自动降级（Cavalier 超时 → HIBP → 返回已有结果）
  - 验收：多数据源并行查询 + 超时降级

---

## Phase 4：深度爬虫

> **目标**：对命中站点抓取公开信息，丰富报告内容。
> **交付物**：深度爬虫模块。
> **依赖**：Phase 2 站点数据库可用

### 4.1 爬虫核心

- [ ] **4.1.1** 通用爬虫框架
  - `crawler/base.py`：接收站点 JSON + Engine → 抓取公开信息
  - 自动选择 anti_bot 级别
  - 验收：对 GitHub 爬取用户简介和头像

- [ ] **4.1.2** 站点专属抽取器
  - 为高频站点编写 CSS/XPath 规则
  - `crawler/extractors/zhihu.py`、`crawler/extractors/github.py` 等
  - 验收：每个专属抽取器有测试用例

- [ ] **4.1.3** DynamicFetcher 集成
  - SPA 站点（React/Vue 渲染的页面）用 Playwright Chromium
  - 验收：对 React 站点正确提取 JS 渲染后的内容

### 4.2 反爬对抗

- [ ] **4.2.1** 频率控制
  - 每个站点独立的请求间隔（`min_interval_ms`）
  - 429 响应自动退避
  - 验收：模拟 429 响应触发退避

- [ ] **4.2.2** User-Agent 轮换
  - 维护 UA 池，Scrapling 默认已支持
  - 验收：连续 10 次请求 UA 不完全相同

### 4.3 提取信息 Schema

- [ ] **4.3.1** 统一 Profile 结构
  ```json
  {
    "platform": "github",
    "username": "yes999zc",
    "display_name": "9哥",
    "avatar_hash": "a3f8c2d...",
    "bio": "...",
    "url": "https://github.com/yes999zc",
    "joined_date": "2018-03-15",
    "last_active": "2026-05-01",
    "follower_count": 42,
    "recent_posts": ["title1", "title2"]
  }
  ```
  - 验收：schema 定义完整，至少覆盖 3 类平台

---

## Phase 5：泄露数据库自建（远期）

> **目标**：摆脱外部 API 依赖，建立真正的数据护城河。
> **交付物**：NAS 本地泄露数据库查询服务。
> **依赖**：Phase 3 的 LeakSource 接口已定义

### 5.1 基础设施

- [ ] **5.1.1** NAS PostgreSQL 部署
  - Docker Compose 部署 PostgreSQL 15+
  - 存储挂载至 NAS 大容量卷
  - 验收：`psql -h 192.168.5.170` 连接成功

- [ ] **5.1.2** 数据库 Schema
  - 单表：`id, email, username, password_hash, domain, source, breach_date`
  - 验收：建表语句执行成功

### 5.2 数据导入

- [ ] **5.2.1** 下载至少一个泄露数据集
  - 优先 Collection #1 或 BreachCompilation
  - 通过磁力链或 archive.org
  - 验收：原始文件下载完成，MD5 校验通过

- [ ] **5.2.2** 数据清洗与导入
  - 解析 `email:password` 格式
  - 过滤非目标域（如 `.ru` 站）
  - 批量导入（参考 Tevora 方案：batch_size=1M）
  - 验收：导入记录数 > 1 亿

- [ ] **5.2.3** 索引建立
  - BTree 索引：email, domain
  - GIN Trigram 索引：username（模糊搜索）
  - 验收：`EXPLAIN ANALYZE` 确认索引生效，查询 < 100ms

### 5.3 服务封装

- [ ] **5.3.1** 查询 API
  - FastAPI 或 Django REST 封装 SQL 查询
  - 端点：`GET /search?username=xxx` `GET /search?email=xxx`
  - 验收：HTTP 请求返回 JSON，响应 < 200ms

- [ ] **5.3.2** 实现 `SelfHostedSource`
  - 遵循 LeakSource 接口
  - 调用本地查询 API
  - 验收：与 CavalierSource 行为一致

---

## Phase 6：全景报告（终局）

> **目标**：对标 nuwa.world Deep Research，生成身份全景报告。
> **交付物**：Web UI + 报告导出。
> **依赖**：Phase 3 + Phase 4 可用

### 6.1 报告引擎

- [ ] **6.1.1** 报告数据聚合
  - 聚合：站点探测结果 + 爬虫提取信息 + 泄露记录 + 关联信号
  - 去重 + 排序 + 置信度标注
  - 验收：输入用户名，输出完整的报告数据 dict

- [ ] **6.1.2** 完整度计算
  - 根据信号数量和质量计算百分比
  - 类似 nuwa 的 "96% 完整度"
  - 验收：公式文档化，不同场景有区分度

### 6.2 可视化

- [ ] **6.2.1** 平台分布图
  - 哪些平台有账号（✅ / ❌ / ⚠️ 需验证）
  - 按分类维度分组展示
  - 验收：一目了然的平台地图

- [ ] **6.2.2** 活跃时间线
  - 各平台首次出现和最后活跃时间
  - 标注关键时间节点
  - 验收：时间线清晰可读

- [ ] **6.2.3** 关联信号图
  - 展示用户名 → 邮箱 → 手机号 → 平台的关联链
  - 验收：血缘关系一目了然

### 6.3 Web UI

- [ ] **6.3.1** Geist 灰白风前端
  - 纯白底 + 灰文字 + 黑线框 + 无渐变无 emoji
  - 移动端响应式
  - 验收：视觉审查通过

- [ ] **6.3.2** 搜索交互
  - 输入框 → 进度条 → 报告首页
  - 各板块展开/折叠
  - 验收：交互流畅，无闪烁

### 6.4 导出

- [ ] **6.4.1** HTML 报告
  - 自包含 HTML（CSS 内联）
  - 可直接分享 / 打印
  - 验收：浏览器打开完整渲染

- [ ] **6.4.2** JSON 导出
  - 完整结构化数据
  - 供下游工具消费
  - 验收：JSON Schema 校验通过

---

## 附录 A：文件结构全貌

```
clawithme/
├── docs/
│   ├── discussion-log.md      # 讨论记录
│   ├── technical-roadmap.md   # 技术路线
│   └── todo.md                # 本文件
├── data/
│   ├── schema.json            # JSON Schema 校验
│   ├── taxonomy.json          # 分类树
│   ├── engines.json           # Engine 定义
│   └── sites/                 # 一个站点一个 JSON
│       ├── social/
│       ├── devtools/
│       ├── forum/
│       ├── media/
│       └── ...
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
│   ├── crawler/               # 深度爬虫
│   │   ├── __init__.py
│   │   ├── base.py            # 通用爬虫
│   │   └── extractors/        # 站点专属抽取
│   ├── report/                # 全景报告
│   │   ├── __init__.py
│   │   ├── aggregator.py      # 数据聚合
│   │   └── renderer.py        # 报告渲染
│   ├── leak_sources/          # 泄露数据库
│   │   ├── __init__.py        # LeakSource 抽象接口
│   │   ├── cavalier.py
│   │   ├── hibp.py
│   │   └── self_hosted.py
│   └── signals/               # 多信号关联
│       ├── __init__.py
│       ├── email.py
│       ├── phone.py
│       ├── avatar.py
│       └── search_engine.py
├── scripts/
│   ├── verify_site.py         # 单站验证
│   ├── verify_all.py          # 全量验证
│   ├── validate.py            # JSON Schema 校验
│   ├── stats.py               # 统计
│   └── migrate_maigret.py     # maigret → clawithme 迁移
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

## 附录 B：验收标准速查

| Phase | 核心验收标准 |
|-------|-------------|
| 1 | `clawithme search <username>` 返回 10 个中国站结果 + Cavalier 泄露记录 |
| 2 | 50+ 中国站 JSON，2000+ 全球站，全部通过 schema 校验 |
| 3 | 多信号关联引擎输出 `{email, phone, platforms, confidence}` |
| 4 | 至少 5 个站点能抓取简介 + 头像 |
| 5 | NAS PostgreSQL 查询 < 200ms |
| 6 | Web UI 生成可分享的 HTML 全景报告 |
