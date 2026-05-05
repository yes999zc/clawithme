# clawithme — 技术路线 v4

> V2 路线重写。四方评审（Brutal Pragmatist + China Internet Expert + Architect + Claude Code 独立评估）+ 9 哥方向确认。
> 2026-05-05

---

## 版本说明

| 版本 | 变更 |
|------|------|
| v1 | 初始路线（maigret 研究 + fork 对比） |
| v2 | 陪审团第一轮 + 9 哥修正（多信号关联、Scrapling、泄露数据库） |
| v3 | 陪审团第二轮修正（Phase 重排、schema 去冗余、安全加固） |
| **v4** | 四方评审 + 9 哥方向确认（LLM 身份推理、国际化聚焦、Web UI 提前） |

---

## 一、产品定位

```
               用户名 / 邮箱 / 手机号
                          │
                          ▼
┌─────────────────────────────────────────────────┐
│                  clawithme                        │
│                                                   │
│  开源 OSINT 工具 → 最终上线 SaaS                   │
│  输入 → 全网身份发现 → 全景报告                    │
│                                                   │
│  护城河：国际站 + 中国站探测知识                    │
│  差异化：LLM 身份推理引擎（规则 + AI 混合）         │
│  终局：人脸识别 → 跨实名平台关联（nuwa.world 方向） │
└─────────────────────────────────────────────────┘
```

**一句话**：maigret 的下一代——多信号关联 + LLM 身份推理 + 全景报告。国际客户为主，中国站探测作为补充优势。

**v2 核心命题**：从"能跑"到"能上线"——修引擎正确性 + 加 LLM 推理 + Web UI + 国际站点精华。

---

## 二、系统架构（v2 演进）

```
┌──────────────────────────────────────────────────────────┐
│                     clawithme 架构 v2                      │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────┐   ┌──────────────────┐   ┌──────────────┐  │
│  │ CLI 入口  │   │ Web UI (Phase 8) │   │ Python API   │  │
│  │ (现有)    │   │ Geist + SSE      │   │ (供外部集成)   │  │
│  └────┬─────┘   └────────┬─────────┘   └──────┬───────┘  │
│       └──────────────────┼───────────────────┘           │
│                          ▼                                 │
│  ┌───────────────────────────────────────────────────┐   │
│  │           编排层 (Orchestrator) — async             │   │
│  │  ┌─────────┐  ┌─────────┐  ┌───────────────────┐  │   │
│  │  │ 探测引擎 │  │ 深度爬虫 │  │ 泄露数据库查询      │  │   │
│  │  │ Engine  │  │ Crawler │  │ LeakSources       │  │   │
│  │  │ async   │  │         │  │ Cavalier + HIBP   │  │   │
│  │  └────┬────┘  └────┬────┘  └────────┬──────────┘  │   │
│  └───────┼────────────┼───────────────┼──────────────┘   │
│          ▼            ▼               ▼                   │
│  ┌───────────────────────────────────────────────────┐   │
│  │         多信号关联引擎（规则 + LLM 混合）             │   │
│  │  ┌──────────────────┐  ┌───────────────────────┐  │   │
│  │  │ 规则信号 (6+)     │  │ LLM 仲裁 (DeepSeek)    │  │   │
│  │  │ email/phone/avatar│  │ 高冲突 cluster 判断    │  │   │
│  │  │ username/location │  │ bio 语义理解           │  │   │
│  │  │ time/city-match   │  │ identity summary       │  │   │
│  │  └────────┬─────────┘  └───────────┬───────────┘  │   │
│  └───────────┼────────────────────────┼──────────────┘   │
│              ▼                        ▼                   │
│  ┌───────────────────────────────────────────────────┐   │
│  │              全景报告引擎                            │   │
│  │  Geist 渲染 · HTML/PDF/Markdown · 脱敏 · 图表       │   │
│  └───────────────────────────────────────────────────┘   │
│                                                            │
│  ┌───────────────────────────────────────────────────┐   │
│  │          v3 方向：实名关联层                          │   │
│  │  人脸识别 API / LinkedIn 实名 → 天眼查工商           │   │
│  │  → nuwa.world 式「Find the Big Picture」             │   │
│  └───────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 三、V2 产品方向（9 哥确认）

| 决策 | 结论 | 理由 |
|------|------|------|
| **客户定位** | 国际客户为主 | 中国爬虫法律灰色地带，但中国站探测知识仍是竞争优势 |
| **CN 站规模** | 30 精华站（非 50+） | 聚焦高质量国际站 + 中国金矿站，不含低质量凑数站 |
| **Louvain** | 推迟到 v3 | 最终方向是人脸识别 / nuwa.world API 做大图关联，规则聚类是中间态 |
| **天眼查** | 推迟 | 当前搜不到真实姓名，需要先通过 LinkedIn 等实名平台拿到真实身份后才能用 |
| **LLM 推理** | **v2 核心差异化** | DeepSeek Flash API 先跑通，后续可能换更便宜的 API；上线后做付费功能 |
| **Web UI** | 提前做（Phase 8） | 上线需要，不等站点量铺够 |
| **自建泄露库** | **KILL** | 刑法 285 条风险 + 无合法数据源 |
| **微信弱信号** | **KILL** | 失败率 90%+，无公开 API |

---

## 四、V2 三阶段

### Phase 6：关联引擎加固 + 基础建设（~33h）

**核心命题**：修正确性 + 加信号 + 治腐烂 + 上 LLM POC。不写新架构。

| # | 任务 | 工时 | 说明 |
|:--:|------|:----:|------|
| 6.1 | **拆分误合并** (#13) | 2h | `_match_signals()` 加反合并：username 匹配但 display_name/location 矛盾 → 降权重 |
| 6.2 | **默认头像哈希库** (#7) | 3h | 采集 GitHub identicon / Discourse / phpBB 等默认头像 pHash → 白名单过滤 |
| 6.3 | **时间关联信号** (#9) | 2h | `signals/time.py`：joined_date 解析 + 同月 weight=0.4，±3 月 weight=0.2 |
| 6.4 | **Extractor 健康监控** | 5h | 每周 smoke test：对 known_accounts 跑 extractor，检测返回值退化，告警 |
| 6.5 | **修复误判 deprecated CN 站** | 3h | Gitee（API 含 email/weibo/QQ）、掘金（`__NEXT_DATA__` JSON）、网易云音乐（JSONP）、AcFun |
| 6.6 | **CI/CD 自动发布** (#10) | 4h | wheel 构建 → PyPI publish → GitHub Release，版本号自动 bump |
| 6.7 | **LLM 身份推理 POC** | 8h | DeepSeek Flash API：高冲突 cluster 二分类、bio 语义理解、identity summary |
| 6.8 | **结果缓存层** | 3h | SQLite cache，TTL 可配，key=(username,site_id)，减少无效重探测 |
| 6.9 | **位置邻近信号** (#8) | 3h | `signals/location.py`：城市名归一化（"北京"↔"Beijing"），精确匹配 weight=0.35 |

**交付物**：6 信号规则引擎 + 反合并 + 噪声过滤 + LLM 仲裁 POC + 4 个 CN 站复活 + 自动发布 + extractor 监控

---

### Phase 7：引擎升级 + 站点扩展（~88h）

**核心命题**：async pipeline + 铺国际精华站 + LLM 推理正式化。

| # | 任务 | 工时 | 说明 |
|:--:|------|:----:|------|
| 7.1 | **CLI async 重构** | 15h | `search()` god function → `Orchestrator.run()` + `asyncio.gather` + Semaphore。36 站 180s → ~18s |
| 7.2 | **LLM 推理正式化** | 12h | POC → 生产：prompt 模板化、批量推理、缓存、fallback 到规则引擎、成本控制 |
| 7.3 | **国际站扩展 Tier 1**（10 站） | 20h | LinkedIn（实名桥梁）、Instagram（profile）、Reddit、Pinterest、Medium、YouTube、Twitch（API 替代）、TikTok、Spotify、Telegram |
| 7.4 | **CN 站扩展 Tier 1**（6 站） | 12h | 虎扑、NGA、站酷、LOFTER、什么值得买、贴吧移动版 — extractor |
| 7.5 | **CN 站扩展 Tier 2**（8 站） | 16h | 微博 mobile API、CSDN 增强（`__NEXT_DATA__`）、简书增强、酷安增强、豆瓣小组、Bilibili 增强（space/acc/info）、小红书 POC、抖音 POC |
| 7.6 | **报告 LLM 增强** | 5h | LLM 生成自然语言 identity summary 替代 `_compose_summary()`；bio 语义 clustering |
| 7.7 | **配置层增强** | 3h | DeepSeek API key、concurrency 生效、cache TTL、Web UI 配置 |
| 7.8 | **测试补齐** | 5h | correlation 边界、generator 安全、engines 模板全量、extractor mock |

**交付物**：async 流水线（180s→18s）+ 16-24 新站 + LLM 推理正式版 + 7 信号引擎 + 缓存 + 配置完善

---

### Phase 8：表面层扩展（~60h）

**核心命题**：Web UI + 多格式报告 + 天眼查（条件触发）。

| # | 任务 | 工时 | 说明 |
|:--:|------|:----:|------|
| 8.1 | **Web UI** | 40h | FastAPI + Jinja2 + SSE 进度。单页面：搜索框 → 实时进度 → 结果卡片 → cluster 可视化 → 报告下载。Geist 灰白风 |
| 8.2 | **PDF/Markdown 报告** | 12h | Markdown = 字符串拼接。PDF = WeasyPrint 包装。复用 generator.py 数据层 |
| 8.3 | **天眼查 API** (#12) | 8h | stub 补齐，token gate，条件触发（需先通过 LinkedIn 等拿到真实姓名） |

**交付物**：可上线的最小 Web 应用 + PDF/Markdown 导出 + 天眼查 token gate

---

## 五、V3 方向（远期愿景）

```
Phase 6-8 (v2)              V3 (远期)
═══════════════              ════════
规则信号引擎 (6-7路)    →    人脸识别 API 接入
LLM 仲裁 (DeepSeek)     →    多模态 LLM 推理
Union-Find 聚类         →    Louvain / 图神经网络
用户名 → 虚拟身份        →    人脸 → 实名身份 → 工商关联
国际 30+ 站              →    全球 100+ 站
Web UI                  →    SaaS 上线 + 付费功能
```

**V3 关键路径**：
1. **LinkedIn 实名桥梁** — 拿到真实姓名、公司、职位
2. **人脸识别 API** — nuwa.world / PimEyes / FaceCheck.id 等，实现跨平台人脸搜索
3. **天眼查对接** — 拿到真实姓名 → 查工商（法人/股东/高管/失信）
4. **Louvain 图聚类** — 信号就位后再升级算法
5. **SaaS 上线** — 购买服务器，付费 API 选型，用户体系

---

## 六、风险与应对

| 风险 | 等级 | 应对 |
|------|:---:|------|
| LLM 推理幻觉（错误合并/拆分） | 🔴 | 规则引擎兜底，LLM 仅仲裁高冲突 case；confidence score 分层 |
| DeepSeek API 不可用/涨价 | 🟡 | 设计 provider-agnostic 接口，可切换 Kimi/百炼/OpenRouter |
| 国际站反爬升级 | 🟡 | Scrapling + DynamicFetcher 多层兜底；优先 API-first 站点 |
| 中国爬虫法律风险 | 🟡 | 主线不含 CN 爬取代码（clawithme-cn 插件隔离）；国际客户为主 |
| Extractor 腐烂 | 🟡 | Phase 6 健康监控 + 每日 CI；CSS-based extractor 优先迁移到 API |
| 单人维护瓶颈 | 🟡 | 上线后开源社区贡献；优先自动化（CI/CD/监控） |
| 个人信息保护法 | 🔴 | `--acknowledge-ethical-use` 门禁；不上传数据到服务器；报告加水印 |

---

## 七、设计决策记录（v4 新增）

| 决策 | 结论 | 理由 |
|------|------|------|
| **LLM 接入方式** | DeepSeek Flash API 先跑通，provider-agnostic 接口 | 初期不建本地推理；上线后可能换便宜 API 做付费功能 |
| **CN 站规模** | 30 精华站 | 中国爬虫法律灰色地带，国际客户为主，不追求数量 |
| **Louvain 时机** | v3 | 最终方向是人脸识别做大图关联，规则聚类是中间态 |
| **天眼查时机** | v3（条件触发） | 需要 LinkedIn 等实名平台先拿到真实姓名 |
| **Web UI 优先级** | 提前到 Phase 8 | 上线需要，不等站点量铺够 |
| **KILL：微信弱信号** | 永久移除 | 失败率 90%+，无公开 API |
| **KILL：自建泄露库** | 永久移除 | 刑法 285 条风险 + 无合法数据源 |
| **客户定位** | 国际为主 | 中国法律风险 + 国际市场更大 |
