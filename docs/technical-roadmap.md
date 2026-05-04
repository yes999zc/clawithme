# clawithme — 技术路线 v3

> v2 + 陪审团第二轮评审修正。Phase 3&4 互换、schema 前移、去冗余字段、安全合规加固。
> 2026-05-04

---

## 版本说明

| 版本 | 变更 |
|------|------|
| v1 | 初始路线（maigret 研究 + fork 对比） |
| v2 | 陪审团第一轮 + 9 哥修正（多信号关联、Scrapling、泄露数据库） |
| **v3** | 陪审团第二轮修正（Phase 重排、schema 去冗余、安全加固） |
| v2 scope | Phase 5（泄露自建）和 2000 全球站迁移 → v2 远期范围 |

---

## 一、产品定位

```
               用户名 / 邮箱 / 手机号 / 真实姓名
                          │
                          ▼
┌─────────────────────────────────────────────────┐
│                  clawithme                        │
│                                                   │
│  开源 OSINT 工具                                  │
│  输入 → 全网身份发现 → 全景报告                    │
│                                                   │
│  护城河：中国站探测知识 + 泄露数据库查询            │
└─────────────────────────────────────────────────┘
```

**一句话**：中国互联网的 maigret，但不止于用户名枚举——多信号关联 + 泄露数据库 + 全景报告。

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────┐
│                     clawithme 架构 v3                      │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────────┐  │
│  │ CLI 入口  │   │ Web UI   │   │ Python API / SDK     │  │
│  │ (优先)    │   │ (Geist)  │   │ (供外部集成)          │  │
│  └────┬─────┘   └────┬─────┘   └──────────┬───────────┘  │
│       └──────────────┼───────────────────┘              │
│                      ▼                                    │
│  ┌───────────────────────────────────────────────────┐   │
│  │              编排层 (Orchestrator)                  │   │
│  │  ┌─────────┐  ┌─────────┐  ┌───────────────────┐  │   │
│  │  │ 探测引擎 │  │ 深度爬虫 │  │ 泄露数据库查询      │  │   │
│  │  │ Engine  │  │ Crawler │  │ LeakSources       │  │   │
│  │  └────┬────┘  └────┬────┘  └────────┬──────────┘  │   │
│  └───────┼────────────┼───────────────┼──────────────┘   │
│          ▼            ▼               ▼                   │
│  ┌───────────────────────────────────────────────────┐   │
│  │              多信号关联引擎                          │   │
│  │  用户名 ↔ 邮箱 ↔ 手机号 ↔ 头像哈希 ↔ 平台账号       │   │
│  │  (依赖爬虫抓回的数据 + 泄露数据库查询结果)           │   │
│  └───────────────────────┬───────────────────────────┘   │
│                          ▼                                │
│  ┌───────────────────────────────────────────────────┐   │
│  │              全景报告引擎                            │   │
│  │  平台分布图 · 时间线 · 社交图谱 · Geist 渲染        │   │
│  └───────────────────────────────────────────────────┘   │
│                                                            │
│  ┌───────────────────────────────────────────────────┐   │
│  │              数据层                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐                │   │
│  │  │ 站点数据库     │  │ 泄露查询接口  │                │   │
│  │  │ sites/*.json  │  │ LeakSource   │                │   │
│  │  │ engines.json  │  │ (API聚合层)  │                │   │
│  │  └──────────────┘  └──────────────┘                │   │
│  └───────────────────────────────────────────────────┘   │
│                                                            │
│  ┌───────────────────────────────────────────────────┐   │
│  │              插件层（外部、分支维护）                 │   │
│  │  ┌─────────────────────────────────────────────┐  │   │
│  │  │ 中国站探测插件 (clawithme-cn)                  │  │   │
│  │  │ 含中国站 JSON + 专属抽取器 + 反爬策略          │  │   │
│  │  │ 主线仓库不含中国站爬取实现，用户自行加载        │  │   │
│  │  └─────────────────────────────────────────────┘  │   │
│  └───────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 三、核心模块

### 3.1 站点数据库

**定位**：中国站探测知识是护城河，数据库是存储形式。

#### 3.1.1 站点 Schema（v3 修正）

```json
{
  "id": "zhihu",
  "name": "知乎",
  "canonical_url": "https://www.zhihu.com/people/{username}",
  "engine_ref": "base_http_status",
  "classification": {
    "primary": "social",
    "identity_type": "virtual_social",
    "geo_region": "cn",
    "user_scale": 100000000,
    "tags": ["qa", "knowledge"]
  },
  "rankings": {
    "similarweb_global": 120
  },
  "check": {
    "method": "GET",
    "probe_url": "https://www.zhihu.com/api/v4/members/{username}",
    "expected": 200,
    "regex": "^[a-zA-Z0-9_-]{2,30}$",
    "presence_strs": [],
    "absence_strs": [],
    "error_flags": {},
    "known_accounts": ["zhangjiawei"],
    "known_unclaimed": ["thisuserdoesnotexist99999"],
    "headers": {}
  },
  "nsfw": false,
  "deprecated": false,
  "source": "manual",
  "last_updated": "2026-05-04T00:00:00Z"
}
```

**v3 修正点**：
- ❌ 删除 `check.type` — 检测类型由 Engine 的 `classifier` 唯一决定，避免冗余和矛盾
- ✅ 新增 `check.regex` — 用户名合法性校验（继承自 maigret）
- ✅ 新增 `check.error_flags` — 站点特有错误（地区限制、登录要求等）
- ✅ 新增 `classification.tags` — 保留 maigret 的标签过滤能力
- ✅ 新增 `check.presence_strs` / `check.absence_strs` — 明确命名，替代含糊的 e_string/m_string

#### 3.1.2 分类维度（v3 修正）

| 字段 | 含义 | 取值 |
|------|------|------|
| `identity_type` | 身份性质 | `real_social` — 真实身份社交（微信、QQ空间、LinkedIn） |
| | | `public_social` — **公开社交**（微博、小红书—半实名可搜索） |
| | | `virtual_social` — 虚拟身份社交（B站、知乎、豆瓣） |
| | | `anonymous` — 匿名社交（贴吧、Mojitianqi） |
| | | `professional` — 职业身份（GitHub、LinkedIn、掘金） |
| `geo_region` | 地理区域 | `cn` / `asia` / `europe` / `americas` / `global` |
| `user_scale` | 用户量（约） | 整数，用于优先级排序 |
| `primary` | 功能分类 | `social` / `devtools` / `forum` / `media` / `ecommerce` / `gaming` / `music` / `blog` / `academic` |

**v3 修正**：新增 `public_social` 分类，解决微博/小红书等半实名平台的分类模糊问题。

#### 3.1.3 中国站探测可行性

**可直接探测**（HTTP 公开，无需登录）：
知乎（API 端点）、豆瓣（RSS）、V2EX、掘金、CSDN、简书、网易云音乐（JSONP）、GitHub（全球）、B站（部分接口）

**需反爬对抗**（有反爬但可尝试）：
微博（mobile 版接口较宽松）、贴吧、B站（主站）

**实验性探测**（弱信号，低成功率但不放弃）：
微信（搜一搜/公众号名称/视频号—间接探测定性为"可能存在"）

**高难度/不可行**（需登录或强反爬）：
抖音、小红书、QQ空间（标记 skip，待反爬技术突破）

#### 3.1.4 架构隔离原则

中国站探测代码**不在主线仓库内**。主线仅包含：
- 全球站点 JSON（不含中国站—geo_region ≠ cn）
- 站点 schema 定义（分类枚举含 `cn`，但不含站点数据）
- LeakSource 抽象接口（数据源无关）

中国站相关代码放在独立仓库/分支 `clawithme-cn`：
- 中国站 JSON 文件
- 中国站专属抽取器（zhihu_crawler.py 等）
- 微信弱信号探测实验模块
- 用户自行安装插件后承担合规责任

#### 3.1.5 目录结构

```
data/
├── schema.json              # JSON Schema 校验（Phase 1 即编写，CI gate）
├── taxonomy.json            # 分类树定义（Phase 1 即编写）
├── engines.json             # Engine 规则定义
└── sites/                   # 一个站点一个 JSON（全球站，不含 cn）
    ├── social/              # 按 primary 分类
    ├── devtools/
    ├── forum/               # 统一单数
    ├── media/
    └── ...
```

---

### 3.2 Engine 系统（v3 修正）

**设计原则**：数据/逻辑分离。Engine 定义"怎么查"，站点只写"参数值"。
**关键规则**：检测类型由 Engine 的 `classifier` **唯一决定**，站点不声明类型。

#### 3.2.1 Engine 定义

```json
{
  "base_http_status": {
    "name": "HTTP Status Code Check",
    "version": "2.0",
    "classifier": "status_code",
    "params": {
      "expected": "{e_code}",
      "timeout_ms": 5000,
      "follow_redirects": true
    },
    "anti_bot": "scrapling_fetcher"
  },
  "xenforo": {
    "name": "XenForo CMS",
    "version": "1.0",
    "classifier": "message",
    "params": {
      "presence_strings": ["{e_string}"],
      "absence_strings": ["{m_string}"],
      "timeout_ms": 8000
    },
    "anti_bot": "scrapling_async",
    "shared_by_sites": 247
  }
}
```

#### 3.2.2 变量模板（v3 补充）

Engine 运行时变量替换：

```
{username}      → 用户输入的用户名
{e_code}        → 站点 check.expected（期望状态码）
{e_string}      → 站点 check.presence_strs（存在特征串）
{m_string}      → 站点 check.absence_strs（不存在特征串）
{e_headers}     → 站点 check.headers（自定义请求头）
{probe_url}     → 站点 check.probe_url
{url_subpath}   → 站点 subpath（论坛子路径等）
```

**安全约束**：模板引擎必须加沙箱保护。不使用 Jinja2 的 `|attr()`/`|import` 等危险过滤器，或改用手写字典替换（`str.replace`），防止外部数据触发模板注入。变量白名单制：只有上述 7 个变量可替换。

#### 3.2.3 反爬能力绑定

| 级别 | 工具 | 能力 | 适用 |
|------|------|------|------|
| `none` | 原生 httpx | 无伪装 | 友站/自有 API |
| `scrapling_fetcher` | Scrapling Fetcher | curl_cffi 指纹伪装 | 常规公众站点 |
| `scrapling_async` | Scrapling AsyncFetcher | 指纹 + 并发 | 批量扫描 |
| `scrapling_dynamic` | Scrapling DynamicFetcher | Playwright JS 渲染 | SPA/动态内容 |

---

### 3.3 反爬层 — Scrapling

已安装 Scrapling v0.4.7，三级能力。

**用途**：替代 maigret 原生的 requests/httpx，作为所有站点探测的 HTTP 底层。

**新增**：HTTP 代理配置（`config.toml`），国内访问海外 API 时使用。

---

### 3.3.1 可观测性 — 结构化日志

**工具**：`structlog` + Trace Context 传播。

```
每条日志携带: breach_id / trace_id / site_id
structlog.bind(trace_id=...) → 后续所有日志自动携带
grep 一个 trace_id → 看到完整请求链路
```

入口层（CLI/API）生成 `trace_id`，经过编排层、Engine、爬虫、LeakSource 时逐层传递。

---

### 3.4 深度爬虫

对命中站点抓取公开信息：
- 头像 URL → 计算 perceptual hash（pHash）
- 个人简介文字
- 公开帖子标题/摘要
- 关注数/粉丝数
- 最后活跃时间

**工具链**：Scrapling（反爬）+ CSS Selector / XPath（提取）
**策略**：Phase 2 每新增一个站点，同步编写其专属抽取器，不攒到后面补。

#### 统一 Profile 结构

```json
{
  "platform": "github",
  "username": "yes999zc",
  "display_name": "9哥",
  "avatar_url": "https://...",
  "avatar_hash": "a3f8c2d...",
  "bio": "...",
  "url": "https://github.com/yes999zc",
  "joined_date": "2018-03-15",
  "last_active": "2026-05-01",
  "follower_count": 42,
  "recent_posts": ["title1", "title2"]
}
```

---

### 3.5 泄露数据库集成（v3 修正）

统一抽象接口，三层数据源：

```python
from pydantic import BaseModel

class BreachRecord(BaseModel):
    """所有字段 Optional — 不同数据源返回字段不同。
    使用 Pydantic 替代 dataclass：构造时自动校验类型，model_dump() 一步序列化。"""
    email: str | None = None
    username: str | None = None
    phone: str | None = None
    password_sha256: str | None = None   # 只存 SHA256，绝不存明文
    domain: str | None = None
    source: str | None = None
    breach_date: str | None = None

class LeakSource(ABC):
    @abstractmethod
    async def search_by_username(self, username: str) -> list[BreachRecord]: ...
    @abstractmethod
    async def search_by_email(self, email: str) -> list[BreachRecord]: ...
    @abstractmethod
    async def search_by_phone(self, phone: str) -> list[BreachRecord]: ...
    async def is_available(self) -> bool: ...           # 健康检查
    async def rate_limit_remaining(self) -> int: ...    # 速率余量
```

具体实现：
```
├── CavalierSource      ← 免费 API，已验证可用
├── HIBPSource          ← HaveIBeenPwned API v3
├── DehashedSource      ← 付费 API（$5+/月）
└── SelfHostedSource    ← v2 scope: NAS PostgreSQL 自建
```

**v3 安全修正**：密码字段绝不存明文，只存 `password_sha256`。

---

### 3.6 多信号关联引擎

**输入依赖**：爬虫抓回的头像/简介数据 + 泄露数据库查询结果。
**因此 Phase 顺序**：先爬虫（Phase 3）→ 再关联（Phase 4）。

```
输入: 用户名 "zhangsan"
    │
    ├─→ 站点探测: 知乎 ✅  GitHub ✅  V2EX ❌
    │
    ├─→ 深度爬虫: GitHub头像 → hash a3f8...
    │             知乎头像 → hash b7e2...
    │
    ├─→ 泄露数据库: zhangsan → zhangsan@gmail.com / 138****1234
    │       │
    │       ├─→ 邮箱 → 更多平台账号
    │       └─→ 手机号 → 运营商归属
    │
    ├─→ 搜索引擎: site:v2ex.com "zhangsan"
    │
    └─→ 头像哈希匹配: a3f8 == b7e2? → 否 → 非同一人
```

**信号权重**：

| 信号 | 强度 | 说明 |
|------|------|------|
| 用户名精确匹配 | 中 | 同一用户名 ≠ 同一人（知乎昵称可重复） |
| 邮箱关联 | 高 | 邮箱几乎唯一 |
| 手机号关联 | 高 | 手机号唯一 |
| 头像哈希匹配 | 高 | 同一头像 → 同一人的概率极高 |
| 搜索引擎结果 | 低 | 辅助信号，需人工判断 |

**已知账号自动验证**（v3 新增）：CI 每日对 `known_accounts` 执行探测验证，检测规则失效。这是防止站点数据库腐烂的唯一手段，从 Phase 1 就开始跑。

---

### 3.7 全景报告

最终交付物，对标 nuwa.world 的 Deep Research。Geist 灰白风，无渐变无 emoji。

**v3 交付物明确化**：
- 可独立运行的 Web 应用（非仅 CLI 输出）
- 自包含 HTML 报告（CSS 内联，可分享/打印）
- 结构化 JSON 导出（供下游工具消费）

---

## 四、分阶段路线图（v3 重排）

### Phase 1：基础验证（当前阶段）🔴

**目标**：验证技术可行性 + 建立 schema 约束 + CI 门禁。

- [ ] 项目骨架 + `pyproject.toml` + pytest
- [ ] Scrapling HTTP 封装层
- [ ] **`data/schema.json`** — 站点 JSON 校验（schema-first，Phase 1 就写）
- [ ] **`data/taxonomy.json`** — 分类树定义
- [ ] HTTP 代理配置（`config.example.toml`）
- [ ] 手动验证 10 个中国核心站（含微信弱信号实验）
- [ ] 为可探测站点写 JSON（需通过 schema 校验）
- [ ] 实现 `base_http_status` + 1 个 CMS Engine
- [ ] `engines.json` 结构 + 引擎加载器
- [ ] **`LeakSource` 抽象接口**（3 个方法 + BreachRecord dataclass）
- [ ] `CavalierSource` 实现
- [ ] **known_accounts 自动验证 CI**（每日 cron，Phase 1 就跑）
- [ ] CLI 入口：`clawithme search <username>`

**交付物**：能探测 10 个中国站 + 查询 Cavalier 的 CLI 工具。schema + CI 已就位。

---

### Phase 2：站点数据库扩展

**目标**：建立护城河。

- [ ] 扩展至 50+ 中国站（含虎扑/NGA/少数派/什么值得买/AcFun/酷安/站酷/花瓣/LOFTER/百度知道/天涯社区）
- [ ] maigret 站点迁移脚本（maigret format → clawithme schema）
- [ ] 实现全部 CMS Engine（XenForo/phpBB/Discourse/vBulletin/Discuz!/WordPress）
- [ ] GitHub Actions CI：PR 自动运行 `validate.py`
- [ ] CONTRIBUTING.md
- [ ] **v2 scope**：2000 全球站迁移（非 Phase 2 必须）

**交付物**：50+ 中国站 JSON + Engine 系统 + CI 门禁。

---

### Phase 3：深度爬虫（原 Phase 4，提前）

**目标**：获取多信号关联所需的原始数据。**在 Phase 4 多信号关联之前完成。**

- [ ] 通用爬虫框架（`crawler/base.py`）
- [ ] 站点专属抽取器（zhihu/github 等，与 Phase 2 站点扩展同步编写）
- [ ] Scrapling DynamicFetcher 集成（SPA/JS 渲染）
- [ ] 频率控制 + User-Agent 轮换
- [ ] 统一 Profile 结构定义
- [ ] **已知账号验证 CI**（持续运行，监控规则腐烂）

**交付物**：至少 5 个站点能抓取简介 + 头像。爬虫模块可独立运行。

---

### Phase 4：多信号关联（原 Phase 3，后移）

**目标**：从「用户名枚举」升级为「多信号身份关联」。
**前置依赖**：Phase 3（爬虫数据）+ Phase 1（LeakSource）。

- [ ] 邮箱 → 平台关联
- [ ] 手机号 → 平台关联（含归属地查询）
- [ ] 头像哈希跨平台匹配（依赖 Phase 3 抓回的头像）
- [ ] 搜索引擎 site: 辅助
- [ ] 信号聚合器 + 置信度评分
- [ ] HIBP API 集成
- [ ] LeakSource 管理器（多源优先级 + 降级）

**交付物**：多信号关联引擎，输出 `{email, phone, platforms, confidence}`。

---

### Phase 5：全景报告（终局）

**目标**：对标 nuwa.world Deep Research。

- [ ] 报告数据聚合（站点探测 + 爬虫 + 泄露 + 关联信号）
- [ ] 完整度计算
- [ ] 平台分布图、活跃时间线、关联信号图
- [ ] Geist 灰白风 Web UI + 搜索交互
- [ ] 自包含 HTML 报告导出
- [ ] JSON 结构化导出

**交付物**：完整的独立 Web 应用 + 报告导出。

---

### v2 Scope（远期）

以下功能从主线 Phase 移入 v2 范围：

- **泄露数据库自建**（原 Phase 5）：NAS PostgreSQL + 泄露数据导入
  - 法律风险需独立评估（中国《刑法》第285条）
  - 当前阶段以 Cavalier + HIBP + Dehashed API 聚合替代
- **2000+ 全球站点迁移**（原 Phase 2 子任务）
  - 团队资源不足以维护 2000+ 站点的持续验证
  - v1 聚焦中国站，v2 扩展到全球

---

## 五、风险与应对（v3 补充）

| 风险 | 等级 | 应对 |
|------|------|------|
| 中国站探测大面积不可行 | 🔴 | Phase 1 优先验证，不可行的直接标记 skip |
| 站点数据库规则腐烂 | 🔴 | **Phase 1 即启动 known_accounts 每日自动验证 CI** |
| 法律合规（个人信息保护法） | 🔴 | 中国站代码架构隔离为外部插件，主线不含爬取实现 |
| IP 被封禁 | 🔴 | 代理配置 + 频率控制 + 不可逆操作前人工确认 |
| 反爬对抗持续升级 | 🟡 | Scrapling 多层兜底 + 频率控制 |
| 维护人力枯竭 | 🟡 | 聚焦 50+ 中国站，2000 全球站推至 v2 |
| **监控系统自身失效** | 🟡 | Phase 2 部署存活探针（healthchecks.io 或自建 cron 定时 ping 采集器），中国站隔离路径独立检查 |
| 自建泄露库刑事责任 | 🔴 | 推至 v2 scope 独立评估；v1 用 API 聚合 |
| 开源后数据库被抄 | 🟡 | 站点配置可抄，探测经验（anti_bot 策略、API 端点）是隐性知识 |

---

## 六、设计决策记录（v3 修订）

| 决策 | 结论 | 理由 |
|------|------|------|
| 站点存储格式 | 一个站点一个 JSON | Git PR 零冲突，diff 清晰 |
| Engine 存储 | 独立 engines.json | 数据/逻辑分离，Engine 升级所有站点受益 |
| **BreachRecord** | **Pydantic BaseModel（非 dataclass）** | 构造时自动校验，model_dump() 一步序列化 |
| **模板引擎** | **手写字典替换（非 Jinja2）** | 沙箱安全，变量白名单制 |
| **日志系统** | **structlog + trace_id 传播** | 全链路可追溯 |
| **检测类型归属** | **Engine 的 classifier 唯一决定，站点不声明 type** | 避免冗余和矛盾 |
| 分类体系 | identity_type + geo_region + user_scale + tags | 正交维度 + 灵活标签 |
| **identity_type 第五类** | **新增 public_social**（微博/小红书） | 解决半实名平台分类模糊 |
| HTTP 底层 | Scrapling 替代 requests/httpx | 绕过 Cloudflare，指纹伪装 |
| 泄露数据库集成 | 统一 LeakSource 抽象接口 + BreachRecord Pydantic Model | 多数据源可插拔 |
| **密码存储** | **只存 password_sha256，绝不存明文** | 合规底线 |
| 中国站代码位置 | 独立插件仓库（clawithme-cn），主线不含 | 法律风险隔离 |
| **Phase 3 & 4 顺序** | **深度爬虫（3）→ 多信号关联（4）** | 关联依赖爬虫数据 |
| 部署优先级 | 本地/NAS 优先，不追 Vercel | Serverless 限制不适合长扫描 |
| 设计风格 | Geist 灰白风 | 9 哥偏好，技术报告用极简结构感 |
| **CI 门禁时机** | **Phase 1 即部署 schema 校验 + known_accounts 每日验证** | 防止数据库早衰 |
