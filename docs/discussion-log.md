# clawithme — 项目讨论记录

> 从 maigret-viz 到 clawithme 的完整演进过程。
> 最后更新：2026-05-04

---

## 一、起点：从 maigret 到 clawithme

### 1.1 原始调研

**maigret 原理分析**：
- maigret 是探测引擎，不是爬虫。对每个站点发一次 HTTP 请求（HEAD/GET）
- 通过 3 种方式判断账号存在性：`status_code`（200/404）、`body`（页面文本特征）、`headers`
- 无自建数据库，3156 个站点的检测规则以 JSON 形式存放在 `sites.md` 中
- 扫描速度：2495 站点 / 85 秒

**中国站覆盖率**：
- maigret 3156 站点中仅 9 个中国站（0.29%）：知乎、豆瓣、网易云、CSDN、SegmentFault、V2EX、贴吧、简书、掘金
- B站、小红书、抖音、微博等核心平台全部缺失

### 1.2 Vercel 部署尝试（已放弃）

尝试将 maigret-viz 部署到 Vercel，失败原因：
1. maigret 依赖 `pycairo`（系统库），Serverless 环境编译失败
2. Vercel Function 60s 超时限制与扫描耗时冲突
3. 结论：**短期内 Vercel 不可行，本地服务为主**

### 1.3 项目命名

候选名：maigret-cn / persona-panorama / social-eye / clawithme

**选定：clawithme**（claw = 抓取/爪 + with me = 陪伴）
- GitHub：`github.com/yes999zc/clawithme`
- 许可：MIT
- 定位：开源 OSINT 工具，用户名 → 全网账号发现 → 全景身份报告

---

## 二、fork 项目调研 & 最佳实践

研究四个同类项目后，提取的关键设计决策：

| 项目 | 站点数 | 中国站 | 亮点 |
|------|--------|--------|------|
| **maigret_china** | ~3156 | 少量新增 | **Engine 系统**：为 XenForo/phpBB/Discourse 等 CMS 定义一次检测规则，覆盖所有同构站点 |
| **social-analyzer** | 999 | 9 个 | **层级分类** type 字段（如 "Computers > Social Networks"）+ **global_rank** + **country** 字段 |
| **WhatsMyName** | 731 | 2 个（微博、知乎） | **formal JSON Schema** + **known** 字段（已知存在账号用于验证规则） |
| **blackbird** | 基于 WMN | — | 无新增亮点，基于 WhatsMyName 二次开发 |

**三大可借鉴设计**：

1. **Engine 系统**（maigret_china）
   ```
   Engine: XenForo     → 覆盖所有 XenForo 论坛
   Engine: phpBB       → 覆盖所有 phpBB 论坛
   Engine: Discourse   → 覆盖所有 Discourse 论坛
   Engine: WordPress   → 覆盖所有 WP 作者页
   ```
   意义：O(engines) 而非 O(sites)。对 Discuz!/phpBB 等中国常见论坛引擎尤其有用。

2. **层级分类 + 全球排名**（social-analyzer）
   ```json
   {
     "type": "Computers > Social Networks > ...",
     "global_rank": 9162,
     "country": "United States"
   }
   ```

3. **JSON Schema 验证 + known 账号**（WhatsMyName）
   - 正式 JSON Schema 适合社区贡献时的数据校验
   - `known` 字段预置已知存在的账号，用于自动化验证检测规则是否失效

---

## 三、nuwa.world 调研

**nuwa.world** 是商业 AI 身份情报平台，不是专门抓 LinkedIn 的。

| 功能 | 描述 |
|------|------|
| Face Search | 上传照片，AI 人脸识别搜索 |
| Semantic Search | 自然语言搜索（"在斯坦福的 ML 研究员"） |
| Deep Research | 整合 50+ 数据源 → 96% 完整度身份报告 |
| NUWA API | SDK（`@nuwa/sdk`），<100ms 响应 |

FAQ："Nuwa 仅索引互联网上公开可访问的信息"

**对 clawithme 的启发**：
- Deep Research 的全景报告 UI 就是我们要的目标形态
- 但它依赖人脸识别 + 语义搜索 + 付费 API
- clawithme 互补路径：**用用户名搜索做入口 → 爬虫抓取各平台信息 → 聚合为全景报告**

---

## 四、陪审团头脑风暴

### 4.1 评审员配置

| 角色 | 职责 |
|------|------|
| 残酷实用主义者 | 审查漏洞、风险、不可行之处 |
| 中国互联网生态专家 | 评估中国站覆盖的可行性 |
| 架构师 | 设计站点数据库 schema 和 Engine 系统 |
| 产品战略家（主持人） | 产品定位、竞争策略、优先级 |

### 4.2 共识结论

**共识 #1：username 枚举范式在中国站失效**

maigret "发 HTTP → 看 status_code" 的方法论在中国平台跑不通：
- 抖音/小红书：不暴露用户名是否注册的语义
- 知乎：昵称可重复，无法唯一标识
- 微博：昵称→UID 映射无公开 API

**可直接探测的**：知乎（API 端点）、豆瓣（RSS）、V2EX、掘金、网易云音乐（JSONP）、CSDN、简书
**需登录/强反爬的**：小红书、抖音、微博、贴吧、QQ空间

**共识 #2：Engine 系统需捆绑反爬层**

Engine 规则正确，但同 CMS 下不同站点有不同反爬策略。不捆绑代理池+cookie管理+重试退避的 Engine 是纸老虎。

**共识 #3：法律风险需重视**

《个人信息保护法》《网络安全法》框架下的风险：
- 工具文档必须声明仅限个人授权账号使用
- 默认关闭中国站高频扫描功能

### 4.3 分歧点

**站点数据库是护城河吗？**

| 立场 | 观点 |
|------|------|
| 残酷实用主义者 | 不是。站点规则每月在变，护城河 = 人力消耗战 |
| 产品战略家 | 是，但重新定义为：**中国站探测知识是护城河，数据库只是存储形式** |

### 4.4 修正后的技术路线

```
Phase 1: 先探路，再建库
  ├─ 手动验证每个中国站的探测可行性
  ├─ 分三类：直接探测 / 需对抗 / 不可行
  └─ 只收录前两类

Phase 2: 多信号关联（非纯 username 枚举）
  ├─ 手机号/邮箱 → 平台关联
  ├─ 搜索引擎 site: 语法辅助发现
  ├─ 头像哈希跨平台匹配
  └─ 用户名枚举仅作为信号之一

Phase 3: Engine 系统 + 反爬层
  ├─ 独立 engines.json（数据/逻辑分离）
  ├─ 每个 Engine 捆绑反爬策略
  └─ 一个站点一个 JSON 文件

Phase 4: 全景报告
  └─ 对标 nuwa.world 的 Deep Research
```

---

## 五、9 哥的修正 & 新增方向

> "要解决问题，而不是回避问题。反爬是重要技术手段，要重点调研。"

### 5.1 Scrapling 反爬方案

**Scrapling** 已在本地安装（v0.4.7），提供三级反爬能力：

| 级别 | 类 | 能力 | 适用场景 |
|------|-----|------|----------|
| 基础 | `Fetcher` | curl_cffi 指纹伪装，绕过 Cloudflare | 常规站点探测 |
| 并发 | `AsyncFetcher` | 同 Fetcher + 异步并发 | 批量扫描 |
| 动态 | `DynamicFetcher` | Playwright Chromium，JS 渲染 | SPA/登录墙/验证码 |

可直接用于 clawithme 的站点探测，替代 maigret 原生的 requests/httpx。

### 5.2 泄露数据库集成

调研发现的可用数据源：

| 服务 | 类型 | 接口 | 成本 |
|------|------|------|------|
| **Hudson Rock Cavalier** | Infostealer 泄露 | 免费 API，按用户名搜索 | 免费 |
| HaveIBeenPwned | 数据泄露 | API v3，按域名/邮箱 | 免费（限速率） |
| DeHashed | 泄露数据库 | 付费 API | $5+/月 |
| Snusbase | 泄露数据库 | 付费 | 订阅制 |
| LeakCheck | 泄露数据库 | 付费 API | 按量计费 |

**Cavalier API 验证通过**：
```json
GET https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-username?username=xxx
→ {"stealers": [...], "total_corporate_services": N, "total_user_services": N}
```

**集成策略**：（留接口，当前阶段不强依赖）
- 定义统一的 `LeakSource` 抽象接口
- Cavalier 作为第一个免费数据源实现
- 预留付费数据源的扩展点

### 5.3 站点分类维度

| 维度 | 取值 | 用途 |
|------|------|------|
| 身份性质 | `real_social` / `virtual_social` / `anonymous` / `professional` | 区分真实身份社交 vs 虚拟身份社交 |
| 地理区域 | `cn` / `asia` / `europe` / `americas` / `global` | 区域优先搜索 |
| 用户量级 | 通过 similarweb 排名 / alexaRank | 重点维护头部站点 |

---

## 六、架构师设计的站点 Schema

### 6.1 站点 JSON（单文件）

```json
{
  "id": "github",
  "name": "GitHub",
  "canonical_url": "https://github.com/{username}",
  "engine_ref": "base_http_status",
  "classification": {
    "primary": "devtools",
    "identity_type": "professional",
    "geo_region": "global",
    "user_scale": 100000000
  },
  "rankings": {
    "similarweb_global": 58,
    "alexa": 10
  },
  "check": {
    "type": "status_code",
    "expected": 200,
    "method": "GET",
    "probe_url": "https://api.github.com/users/{username}",
    "headers": {},
    "known_accounts": ["torvalds"],
    "known_unclaimed": ["thisuserdoesnotexist999999"]
  },
  "nsfw": false,
  "deprecated": false,
  "source": "maigret",
  "last_updated": "2025-05-01T00:00:00Z"
}
```

### 6.2 Engine 定义（engines.json）

```json
{
  "base_http_status": {
    "name": "HTTP Status Code Check",
    "version": "2.0",
    "classifier": "status_code",
    "params": {
      "expected": "{e_code}",
      "timeout_ms": 5000,
      "follow_redirects": true,
      "anti_bot": "scrapling_fetcher"
    }
  },
  "xenforo": {
    "name": "XenForo CMS",
    "classifier": "message",
    "params": {
      "presence_strings": ["{e_string}"],
      "absence_strings": ["{m_string}"],
      "anti_bot": "scrapling_async"
    },
    "shared_by_sites": 247
  }
}
```

### 6.3 目录结构

```
clawithme/
├── data/
│   ├── sites/              # 一个站点一个 JSON
│   │   ├── social/         # 按 primary 分类
│   │   ├── devtools/
│   │   └── forums/
│   ├── engines.json        # Engine 定义
│   ├── taxonomy.json       # 分类树
│   └── schema.json         # JSON Schema 校验
├── clawithme/
│   ├── engine/             # 探测引擎核心
│   │   ├── maigret.py      # HTTP 检测 + 3 种 check type
│   │   ├── checking.py
│   │   └── sites.py        # 站点数据库加载
│   ├── crawler/            # 深度爬虫
│   │   └── anti_bot.py     # Scrapling 反爬封装
│   ├── report/             # 全景报告
│   └── leak_sources/       # 泄露数据库集成
│       ├── __init__.py     # LeakSource 抽象接口
│       └── cavalier.py     # Hudson Rock Cavalier 实现
└── docs/
    └── discussion-log.md   # 本文件
```

---

## 七、当前状态 & 下一步

### 已完成
- [x] maigret 原理分析 & 本地扫描验证
- [x] 4 个 fork 项目的站点 schema 对比研究
- [x] nuwa.world 产品调研
- [x] 4 视角陪审团头脑风暴
- [x] Scrapling 反爬方案评估
- [x] 泄露数据库调研（Cavalier API 验证通过）
- [x] 站点 schema 设计（架构师方案）

### 待决定
- [ ] 是否先手动验证 10 个中国核心平台的探测可行性？
- [ ] 站点数据库采用「一个站点一个 JSON」还是「单文件大 JSON」？
- [ ] 第一个 milestone 的定义（最小可验证的产品形态）

### 待执行（需 9 哥确认后）
- [ ] 实现 Scrapling Fetcher 替代 maigret 原生 HTTP 客户端
- [ ] 创建 `LeakSource` 抽象接口 + Cavalier 实现
- [ ] 逐个验证中国站探测可行性并编写站点 JSON
