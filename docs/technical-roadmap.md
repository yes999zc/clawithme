# clawithme — 技术路线 v2

> 综合调研 + 陪审团头脑风暴 + 9 哥修正后的最终路线。
> 2026-05-04

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
│  护城河：中国站探测知识 + 泄露数据库                │
└─────────────────────────────────────────────────┘
```

**一句话**：中国互联网的 maigret，但不止于用户名枚举——多信号关联 + 泄露数据库 + 全景报告。

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────┐
│                     clawithme 架构                         │
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
│  │  │ 站点数据库     │  │ 泄露数据库    │                │   │
│  │  │ sites/*.json  │  │ PostgreSQL   │                │   │
│  │  │ engines.json  │  │ (自建/NAS)   │                │   │
│  │  └──────────────┘  └──────────────┘                │   │
│  └───────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 三、核心模块

### 3.1 站点数据库 — 核心护城河

**定位**：中国站探测知识是护城河，数据库是存储形式。

#### 3.1.1 站点 Schema

每个站点一个 JSON 文件，按 `primary` 分类存放在 `data/sites/<primary>/` 下。

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
    "user_scale": 100000000
  },
  "rankings": {
    "similarweb_global": 120,
    "alexa": 80
  },
  "check": {
    "type": "status_code",
    "probe_url": "https://www.zhihu.com/api/v4/members/{username}",
    "expected": 200,
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

#### 3.1.2 分类维度

| 字段 | 含义 | 取值 |
|------|------|------|
| `identity_type` | 身份性质 | `real_social` — 真实身份社交（微信、QQ空间、LinkedIn） |
| | | `virtual_social` — 虚拟身份社交（B站、知乎、豆瓣） |
| | | `anonymous` — 匿名社交（贴吧、Mojitianqi） |
| | | `professional` — 职业身份（GitHub、LinkedIn、掘金） |
| `geo_region` | 地理区域 | `cn` / `asia` / `europe` / `americas` / `global` |
| `user_scale` | 用户量（约） | 整数，用于优先级排序 |
| `primary` | 功能分类 | `social` / `devtools` / `forum` / `media` / `ecommerce` / `gaming` / `music` / `blog` / `academic` |

#### 3.1.3 中国站探测可行性（预分类）

**可直接探测**（HTTP 公开，无需登录）：
知乎（API）、豆瓣（RSS）、V2EX、掘金、CSDN、简书、网易云音乐（JSONP）、GitHub（全球）、B站（部分接口）

**需反爬对抗**（有反爬但可尝试）：
微博（mobile 版接口较宽松）、贴吧、B站（主站）

**高难度/不可行**（需登录或强反爬）：
抖音、小红书、QQ空间、微信

#### 3.1.4 目录结构

```
data/
├── schema.json              # JSON Schema 校验（CI gate）
├── taxonomy.json            # 分类树定义
├── engines.json             # Engine 规则定义
└── sites/
    ├── social/              # 按 primary 分类
    │   ├── zhihu.json
    │   ├── weibo.json
    │   └── douban.json
    ├── devtools/
    │   ├── github.json
    │   └── juejin.json
    ├── forum/
    │   └── v2ex.json
    ├── media/
    │   └── bilibili.json
    └── ...
```

---

### 3.2 Engine 系统

**设计原则**：数据/逻辑分离。Engine 定义"怎么查"，站点只写"参数值"。

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

支持的 CMS Engine（优先级）：
- XenForo、phpBB、Discourse、vBulletin（全球论坛）
- Discuz!、WordPress（中国论坛/博客常见）

#### 3.2.2 反爬能力绑定

每个 Engine 必须指定 `anti_bot` 级别：

| 级别 | 工具 | 能力 | 适用 |
|------|------|------|------|
| `none` | 原生 httpx | 无伪装 | 友站/自有 API |
| `scrapling_fetcher` | Scrapling Fetcher | curl_cffi 指纹伪装 | 常规公众站点 |
| `scrapling_async` | Scrapling AsyncFetcher | 指纹 + 并发 | 批量扫描 |
| `scrapling_dynamic` | Scrapling DynamicFetcher | Playwright JS 渲染 | SPA/动态内容 |

---

### 3.3 反爬层 — Scrapling

已安装 Scrapling v0.4.7，三级能力：

```
Fetcher ──────────► curl_cffi 指纹伪装 → 绕过 Cloudflare
AsyncFetcher ─────► 同上 + 异步并发    → 批量站点探测
DynamicFetcher ───► Playwright Chromium → JS 渲染/SPA
```

**用途**：替代 maigret 原生的 requests/httpx，作为所有站点探测的 HTTP 底层。

---

### 3.4 深度爬虫

对命中站点抓取公开信息：
- 头像 URL / 头像哈希
- 个人简介文字
- 公开帖子标题/摘要
- 关注数/粉丝数
- 最后活跃时间

**工具链**：Scrapling（反爬）+ CSS Selector / XPath（提取）

---

### 3.5 泄露数据库集成

三层架构，统一抽象接口：

```
LeakSource (抽象基类)
├── search_by_username(username) → [{email, phone, source, date}]
├── search_by_email(email)       → [{username, source, date}]
└── search_by_phone(phone)       → [{username, email, source, date}]

具体实现：
├── CavalierSource      ← 免费 API，已验证可用
├── HIBPSource          ← HaveIBeenPwned API v3
├── DehashedSource      ← 付费 API（$5+/月）
├── SelfHostedSource    ← PostgreSQL 自建（NAS）
└── (更多数据源可扩展)
```

#### 自建数据库（远期）

| 数据集 | 规模 | 格式 |
|--------|------|------|
| BreachCompilation | 基础合集 | email:password |
| Collection #1 | 大合集 | email:password |
| Collection #2-5 + Antipublic | 最大合集 | email:password |
| COMB | 32 亿唯一条目 | email:password |

**技术栈**：PostgreSQL + GIN Trigram 索引
- BTree 索引 email/domain → 毫秒级精确搜索
- GIN Trigram 索引 username → 50ms 模糊搜索
- 存储估算：300-500GB（含索引）
- 部署位置：NAS（192.168.5.170）

**法律声明**：自建数据库仅用于授权的安全研究和自我账号审计。

---

### 3.6 多信号关联引擎

**核心思路**（来自陪审团建议 #1）：

不要执着于 "username 是否存在"，而是把多个信号串起来：

```
输入: 用户名 "zhangsan"
    │
    ├─→ 站点探测: 知乎 ✅  GitHub ✅  V2EX ❌
    │
    ├─→ 泄露数据库: zhangsan → zhangsan@gmail.com / 138****1234
    │       │
    │       ├─→ 邮箱 → 更多平台账号
    │       └─→ 手机号 → 运营商归属
    │
    ├─→ 搜索引擎: site:v2ex.com "zhangsan"
    │
    └─→ 头像哈希: GitHub头像 vs 知乎头像 → 匹配确认
```

**信号权重**：
| 信号 | 强度 | 说明 |
|------|------|------|
| 用户名精确匹配 | 中 | 同一用户名 ≠ 同一人（知乎昵称可重复） |
| 邮箱关联 | 高 | 邮箱几乎唯一 |
| 手机号关联 | 高 | 手机号唯一 |
| 头像哈希匹配 | 高 | 同一头像 → 同一人的概率极高 |
| 搜索引擎结果 | 低 | 辅助信号，需人工判断 |

---

### 3.7 全景报告

最终交付物，对标 nuwa.world 的 Deep Research：

```
┌─────────────────────────────────────────┐
│          Identity Panorama               │
│          "zhangsan"                       │
├─────────────────────────────────────────┤
│  ┌──────────────────────────────────┐   │
│  │  📊 平台分布                      │   │
│  │  GitHub ✅  知乎 ✅  CSDN ✅       │   │
│  │  豆瓣 ✅  V2EX ❌  微博 ❌          │   │
│  │  命中率: 4/6                       │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │  🔗 关联信号                      │   │
│  │  邮箱: z***@gmail.com            │   │
│  │  手机: 138**** (中国移动)         │   │
│  │  头像哈希: a3f8c2d...            │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │  🕐 活跃时间线                    │   │
│  │  GitHub: 2018-至今               │   │
│  │  知乎: 2020-2024                 │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │  🗂️ 泄露记录                     │   │
│  │  数据源: BreachCompilation       │   │
│  │  ⚠️ 2021年 LinkedIn 泄露         │   │
│  └──────────────────────────────────┘   │
├─────────────────────────────────────────┤
│  完整度: 72%   数据源: 6   信号: 4      │
└─────────────────────────────────────────┘
```

**设计风格**：Geist 灰白风，无渐变无 emoji（内部使用图标由字符替换），纯结构感。

---

## 四、分阶段路线图

### Phase 1：基础验证（当前阶段）

**目标**：验证技术可行性，不求完整。

- [ ] 用 Scrapling 手动探测 10 个中国核心平台
- [ ] 为每个可探测站点写一个 JSON（按上述 schema）
- [ ] 实现基础 Engine 系统（base_http_status + 1 个 CMS engine）
- [ ] 实现 Cavalier LeakSource（免费 API 先行验证）

**交付物**：一个能探测 10 个中国站 + 查询 Cavalier 的 CLI 工具。

---

### Phase 2：站点数据库扩展

**目标**：建站护城河。

- [ ] 扩展至 50+ 中国站
- [ ] 引入 maigret 的 3156 站点（删减后保留活跃站点）
- [ ] 实现所有 Engine（XenForo/phpBB/Discourse/Discuz!/WordPress）
- [ ] JSON Schema CI 校验

**交付物**：完整的站点数据库 + Engine 系统。

---

### Phase 3：多信号关联

**目标**：从 "用户名枚举" 升级到 "多信号关联"。

- [ ] 实现邮箱/手机号 → 平台关联
- [ ] 实现头像哈希跨平台匹配
- [ ] 集成搜索引擎 site: 辅助
- [ ] 集成 HIBP API

**交付物**：多信号关联引擎。

---

### Phase 4：深度爬虫

**目标**：获取详细信息。

- [ ] 对命中站点抓取公开信息
- [ ] Scrapling DynamicFetcher 处理 SPA
- [ ] 反爬策略捆绑到 Engine

**交付物**：深度爬虫模块。

---

### Phase 5：泄露数据库自建（远期）

**目标**：真正的护城河。

- [ ] NAS 部署 PostgreSQL
- [ ] 下载至少一个泄露数据集
- [ ] 建立 GIN Trigram 索引
- [ ] 实现 SelfHostedSource

**交付物**：本地泄露数据库查询服务。

---

### Phase 6：全景报告

**目标**：对标的终局。

- [ ] 身份全景报告引擎
- [ ] Geist 灰白风 Web UI
- [ ] 导出 PDF / JSON / HTML

**交付物**：完整产品。

---

## 五、风险与应对

| 风险 | 等级 | 应对 |
|------|------|------|
| 中国站探测大面积不可行 | 🔴 | Phase 1 优先验证，不可行的直接标记 skip |
| 反爬对抗持续升级 | 🟡 | Scrapling 多层兜底 + 频率控制 |
| 法律合规（个人信息保护法） | 🔴 | 文档声明仅限授权使用；默认关闭批量中国站扫描 |
| 泄露数据库存储成本 | 🟡 | NAS 已有基础设施；按需下载子集 |
| 开源后数据库被抄 | 🟡 | 站点配置可抄，但中国站探测经验（anti_bot 策略、API 端点发现）是隐性知识 |
| 站点规则失效（URL 变更） | 🟡 | known_accounts 自动验证 + CI 死链检测 |

---

## 六、设计决策记录

| 决策 | 结论 | 理由 |
|------|------|------|
| 站点存储格式 | 一个站点一个 JSON | Git PR 零冲突，diff 清晰 |
| Engine 存储 | 独立 engines.json | 数据/逻辑分离，Engine 升级所有站点受益 |
| 分类体系 | identity_type + geo_region + user_scale | 三个正交维度，互不重叠 |
| HTTP 底层 | Scrapling 替代 requests/httpx | 绕过 Cloudflare，指纹伪装 |
| 泄露数据库集成 | 统一 LeakSource 抽象接口 | 多数据源可插拔，不锁死单一供应商 |
| 部署优先级 | 本地/NAS 优先，不追 Vercel | Vercel 的 Serverless 限制不适合长扫描任务 |
| 设计风格 | Geist 灰白风 | 9 哥偏好，技术报告用极简结构感 |
