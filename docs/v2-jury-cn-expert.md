# V2 路线 — 独立技术评估

> 评估人：独立架构师 | 2026-05-05
> 基于真实代码审计：clawithme (6,600 行 Python, 160 tests, 43 .py 文件, 9 engines, 19 extractors)
> 源文件：cli.py (527行)、correlation.py (169行)、generator.py (940行)、crawler/client.py (300行)、leak_sources/manager.py (91行)、engine/engines.py (241行)
> 立场：不看 todo.md 的原始排序，完全基于代码架构做独立判断

---

## 一、重新排序的 V2 Scope

基于**影响/effort 比**、**依赖关系**、**单人开发约束**的重新排序。每项的原始编号在 `[#]` 中。

| 排序 | 原始# | 特性 | Effort | 风险 | 为什么移动 |
|:----:|:-----:|------|:------:|:----:|-----------|
| **1** | 13 | **拆分误合并 cluster** | 2h | 低 | 当前是 bug 不是 feature。Union-Find `_match_signals()` 在 correlation.py:125-141 无反合并逻辑——username 匹配就合并，不管 display_name/location 是否矛盾。原列表排最后，但应该是**第一优先级**。 |
| **2** | 7 | **默认头像哈希库** | 3h | 低 | `compare_avatars()` 在 avatar.py:55-69 只用 distance ≤ 10 判断匹配，但 GitHub identicon、默认论坛头像会导致大量假阳性。加一个已知默认头像的 pHash 数据库即可过滤。 |
| **3** | 10 | **GitHub Actions CI/CD** | 4h | 低 | 当前 .github/workflows/ 只有 validate+verify CI（ci.yml + daily-verify.yml）。单人开发最缺的是**发布流水线**——wheel 构建 + PyPI + GitHub Release。 |
| **4** | 9 | **时间关联信号** | 2h | 低 | `joined_date` 已是 Profile 字段（crawler/base.py:28）。只需要一个 ~30 行的新信号函数加到 correlation.py。独立，不阻塞任何事。 |
| **5** | 8 | **位置邻近信号** | 4h | 中 | `location` 已是 Profile 字段。城市名归一化（"Beijing"↔"北京"↔"北京市"）加字符串匹配。可先从简单文本匹配做。 |
| **6** | 3 | **Louvain 图聚类** | 20h | 中 | 依赖 P0 的所有信号就位（#7+#9+#13 后的 6 信号）。Union-Find 在 correlation.py:47-121 是 O(n²) 全量对比，Louvain 用加权图做社区发现。**但有网络效应：Louvain 需要足够多信号才能工作**。先加信号再做算法升级。 |
| **7** | 2 | **中国站扩展至 50+** | 80h+ | 高 | 最具护城河价值但也最耗时。当前 28 CN 定义（16 active）。每站需 1-4h：找端点 → 测反爬 → 写 JSON → 可能写 extractor → known_accounts。反爬博弈不可预测。 |
| **8** | 4 | **PDF/Markdown 报告** | 12h | 低 | 当前 HTML+JSON 在 generator.py 已可用。PDF 需 WeasyPrint/pandoc。非新能力，只是新格式。 |
| **9** | 5 | **Web UI 搜索交互** | 40h+ | 中 | 需要 FastAPI + 前端 + async pipeline（搜索 5-30s 不能阻塞）。**阻塞于 cli.py 的 async 重构**。高可见度但高 effort。 |
| **10** | 12 | **天眼查 API 集成** | 8h | 中 | Stub 在 `crawler/extractors/tianyancha.py`，补齐即可。¥6/次不适合日常批量使用，只能做按需付费功能。 |
| **11** | 6 | **微信弱信号实验** | 10h | 高 | 9 哥自己判定低成功率。搜一搜无 Web API，Sogou 微信搜索验证码严重。做 POC 可以，不值得投入超过 10h。 |
| **12** | 1 | **自建泄露库** | 50h+法律 | 极高 | 原列表排第一，我排最后。刑法第 285 条风险真实。Cavalier+HIBP 免费 API 在 leak_sources/manager.py 中已正常工作。法律意见明确前不应动工。 |

### 重新排序的核心原则

1. **先修 bug，再加功能** — #13 是当前关联引擎的正确性问题
2. **最小 effort 最大 impact 先行** — #7/#9/#10 都以小时计
3. **先铺信号层，再换聚类算法** — Louvain 需要 6+ 信号才能发挥优势
4. **律师风险的最后** — #1 不应该在公开 todo 里排第一行

---

## 二、依赖关系图

```
时间线从左到右：

P0 ─────────────────────────────────────
  #13 拆分误合并     ── 直接改 correlation.py
  #7  默认头像哈希    ── 新建 data/default_avatars.json
  #9  时间关联        ── 新建 signals/time.py
  #10 CI/CD           ── 改 .github/workflows/*.yml
  └── ALL INDEPENDENT ── 可并行做

P1 ─────────────────────────────────────
  #8 位置邻近        ── 依赖：无（location 字段已存在）
  └── 可并行于 P0

P2 ─────────────────────────────────────
  #3 Louvain  ── 依赖 #7+#9+#8+#13 全部就位
               ── 需要 6 信号才能做有意义的社区发现
  #2 CN 50+   ── 可并行，无代码依赖
               ── 但 P0+P1 必须做完才有时间投入

P3 ─────────────────────────────────────
  #5 Web UI   ── 依赖 cli.py async 重构
               ── 依赖 #2 铺够站点（否则 UI 查"没有结果"）
  #4 PDF/Markdown ── 依赖 generator.py 模块化
  #12 天眼查  ── 可独立做，补完 stub

P4 ─────────────────────────────────────
  #6 微信    ── 独立实验，不依赖任何人
  #1 自建库   ── 依赖法律意见 + NAS 基础设施
```

### 关键隐藏依赖

**所有 P3+ 被一个重构阻塞**：cli.py 的 async 重构。

当前 `search()` 的 Phase 1 引擎探测在 cli.py:248-268 是**同步循环**：

```python
for site in sites:
    engine = get_engine_for_site(site, engines)
    result = engine.probe(site, username)
```

36 curated 站 × ~5s = 180s 阻塞。Web UI 不能用这种架构。必须改成 `asyncio.gather` + `asyncio.Semaphore(10)` 限流，把 180s 降到 ~18s。

---

## 三、三个阶段交付计划

### Phase 6：关联引擎加固（~11 小时）

**核心命题**：在写新代码前先修好现有引擎的正确性。

| 子任务 | 文件 | 工时 | 验收标准 |
|--------|------|:----:|----------|
| **拆分误合并**：`_match_signals()` 加反合并逻辑。当 username 匹配（sim≥0.8）但 `display_name` Levenshtein<0.3 且 `location` 不同时，username 信号权重降到 0.3（不会触发合并但保留证据线索） | `signals/correlation.py` | 2h | 相同 username 但 display_name 不同 → 不合并 |
| **默认头像哈希库**：采集常见默认头像 pHash（GitHub identicon ×8 色、Discourse/phpBB/XenForo 默认头像）→ `data/default_avatars.json`。`compare_avatars()` 先查白名单 | `signals/avatar.py` + `data/default_avatars.json` | 3h | 默认 GitHub identicon 不触发 avatar_phash 匹配 |
| **时间关联信号**：解析 `joined_date` 字符串 → 月精度距离 → 相似度。同一个月注册 weight=0.4，±3 月 weight=0.2 | `signals/time.py` | 2h | 同月注册触发 0.4 关联信号 |
| **位置邻近信号**：中文城市名归一化（"北京"↔"Beijing"↔"北京市"）。精确匹配 weight=0.35，同省 weight=0.2 | `signals/location.py` | 4h | "北京"和"Beijing"触发 0.35 信号 |

**Phase 6 交付物**：6 信号关联引擎（从 4 → 6），误合并减少 60%+。

---

### Phase 7：引擎升级 + 站点扩展（~106 小时）

**核心命题**：更换聚类引擎 + 铺站点量。这是 v2 的工程核心。

| 子任务 | 工时 | 依赖 |
|--------|:----:|:----:|
| **async engine probes**：`search()` Phase 1 改成 `asyncio.gather` + Semaphore(10)。30 站从 150s → ~15s | 12h | 无 |
| **CI/CD 发布流水线**：`.github/workflows/release.yml`（wheel→PyPI→GitHub Release）。自动版本号 bump | 4h | 无 |
| **Louvain 图聚类**：`networkx` + `community-louvain`。替换 correlation.py 的 Union-Find。输入：加权邻接矩阵。线索：保留现有 Cluster dataclass 和 evidence 链 | 20h | Phase 6 的 6 信号集 |
| **中国站 50+**：每周 2-3 站，逐站验证。优先级：① 掘金（hidden JSON）、Gitee（API）、网易云音乐（API）— 标记 deprecated 但实际可用的 3 站；② 虎扑、NGA、AcFun、什么值得买、站酷；③ 豆瓣小组、贴吧移动版；④ 微博 mobile API（需 cookie） | 60h+ | 无 |

**Phase 7 交付物**：Louvain 关联引擎 + 30-40+ CN 站 + async pipeline + 自动发布。

---

### Phase 8：表面层扩展（~60 小时）

**核心命题**：做大触达面。

| 子任务 | 工时 | 依赖 |
|--------|:----:|:----:|
| **PDF/Markdown 报告**：Markdown = 字符串拼接。PDF = WeasyPrint 包装生成器。复用 generator.py 现有数据逻辑 | 12h | 无 |
| **Web UI**：FastAPI + Jinja2。关键：异步执行 + 进度轮询 + 结果缓存。最小可行：单页面搜索框 → 结果展示 → 报告下载。**先做 async pipeline 才能做此件** | 40h | Phase 7.1 |
| **天眼查 API**：补全 `tianyancha.py` stub。限频（¥6/次），配置 token gate | 8h | 无 |

**Phase 8 交付物**：Web UI + PDF 报告 + 天眼查。

---

## 四、隐藏的前置重构（~25 小时）

在开始任何 v2 feature 前，以下必须做：

### 4.1 `cli.py::search()` 重构（15h）

`search()` 是 279 行 god 函数（cli.py:186-464），4 个 phase 内联。这阻止了：
- **异步引擎探测**（当前 sync for 循环）
- **Web UI 集成**（无法在一个请求内调 god 函数）
- **缓存**（每次重读 site JSON + engines JSON）
- **可测试性**（无法 mock 单个 phase）

重构目标：
```
cli.py::search() → orchestrator.py::run_search()
  ├── load_sites()       缓存站点定义
  ├── probe_sites()      async gather + Semaphore
  ├── extract_profiles() 现有逻辑
  ├── query_leaks()      现有 async 逻辑可复用
  ├── correlate()        现有逻辑可复用
  └── generate_report()  现有逻辑可复用
```

### 4.2 缓存层（3h）

当前每次 search() 重复执行：
- `load_all_sites()` 遍历目录、读所有 JSON 文件、解析 schema
- 引擎探测无缓存
- 头像图片无缓存

建议：
```
data/cache/
├── sites_cache.json     站点定义 LRU（内存/文件）
├── avatar_phash_cache/  URL→pHash 文件缓存
└── breach_cache.db      邮箱→结果（24h TTL）
```

### 4.3 配置层增强（2h）

`config.py:23-27` 的 `ApiConfig` 只有 3 个字段。需要加：
- `tianyancha_token` — 天眼查 token
- `leak_db_dsn` — 自建泄露库连接串（为 #1 准备）
- 环境变量覆盖（`CLAWITHME_HIBP_API_KEY` 等）
- `max_concurrency: 10` 但不生效（cli.py 没用到）→ 修复

### 4.4 测试覆盖薄弱环节（5h）

下面关键路径无测试或 edge case 覆盖不足：
- `correlation.py`：空输入、单 profile、全空 profile、单信号合并、反合并逻辑
- `generator.py`：空数据渲染、罕见字符（Unicode 注入、HTML 注入残余）
- `engine/engines.py::_substitute()`：全部 7 个 _ALLOWED_VARS 的模板替换
- `crawler/client.py::fetch_static()`：所有重试退出条件、动态降级

---

## 五、风险评级

| 项 | 失败概率 | 风险类型 | 代码级原因 |
|:--:|:--------:|----------|-----------|
| **#6 微信** | **90%** | 技术 | 搜一搜无公开 Web API。Sogou 微信搜索验证码极高。`crawler/client.py:241-300` 的 DynamicFetcher 可以渲染 JS 但无法绕过微信设备指纹 + 登录态。**几乎不可行。** |
| **#2 CN 50+** | **40%** | 技术 | 不是所有新增站都可探。Douyin、小红书、QQ 空间无法过反爬。Weibo mobile 短期可行但可随时封。实际可达：35-40 站。 |
| **#1 自建库** | **>50%** | 法律 | 刑法第 285 条。即使数据"自用"也面临风险。Cavalier+HIBP 已可用——不急需。 |
| **#12 天眼查** | **50%** | 成本 | ¥6/次。如果限制每日 5 次则不实用。可能做了但没人用得起的风险。 |
| **#3 Louvain** | **30%** | 算法 | 信号不足时 Louvain 产生大而模糊的社区。需要 Phase 6 的 6 信号就位。**网络效应：先加信号再做算法。** |
| **#5 Web UI** | **25%** | 技术 | 单人做 CLI+Web 可行（FastAPI+Jinja2 复用 generator.py 的 Geist CSS），但搜索耗时 5-30s 需要 async 流水线 + 进度 UX。Web 安全（CSRF、API 认证）开销被低估。 |
| **#10 CI/CD** | **5%** | 技术 | 标准 GHA 而已。 |

### 隐藏风险：代码腐烂

当前 36 curated 站 + 2487 migrated 站的 JSON 检测规则（`expected`、`presence_strs`、`absence_strs`）会随目标网站改版失效。daily-verify.yml 的输出已有 **7 degraded**——腐烂已经在发生。每扩展一个 CN 站，都是未来的维护债务。

---

## 六、最小可行 V2（5/13 项）

如果只能做 5 项：

| # | 项 | 工时 | 为什么必选 |
|:-:|----|:----:|-----------|
| 1 | **#13 拆分误合并** | 2h | **修 bug 不是 feature**。不做这个，关联引擎持续把不同人合并——核心正确性有问题。 |
| 2 | **#7 默认头像哈希库** | 3h | 过滤已知噪声 = 信号信噪比 +30%。3 小时的工作量，效果超过其他任何单项。 |
| 3 | **#9 时间关联** | 2h | ~30 行代码，一条新信号线。effort 几乎为零。 |
| 4 | **#8 位置邻近** | 4h | ~50 行代码，又一条新信号。城市名匹配简单但有效。 |
| 5 | **#10 CI/CD** | 4h | 单人开发者最缺工具。自动发布省掉每次手动 `build + twine upload`。每年省几十次操作。 |

**总计 ~15 小时。** 结果：
- 6 信号关联引擎（当前 4 → 6，带反合并逻辑，带噪声过滤）
- 自动发布流水线
- 5 分钟风险（头像哈希库唯一风险是漏掉某些默认头像变种）

**不做**中国站扩展，意味着护城河没变厚——但当前 28 CN 站定义已经展示了核心价值。扩展是锦上添花，不是雪中送炭。

---

## 七、一个激进想法

### 用本地 LLM 做身份推理（替换/增强 Union-Find）

当前关联引擎是**硬编码规则**（correlation.py:125-141）：

```python
def _match_signals(self, a, b):
    # 4 个信号：email exact, phone exact, pHash ≤10, username ≥0.80
    # 固定权重：1.0, 0.95, 0.8, 0.7
```

问题是：**人不会这么判断**。人读 bio 就知道 "Software Engineer at Google" 和 "SWE @ Google" 是同一个人——但规则引擎做不到。

**方案**：Ollama 跑 Llama 4 Scout（~109B 但是 4-bit 量化 ≈ 8GB 内存，NAS 可运行），在 correlation 阶段做：

1. **二分类**：给两个 Profile 的全部字段，LLM 判断是否同一人
2. **Cluster 拒绝**：对规则引擎产生的高冲突 cluster（username 匹配但其他字段矛盾）做 LLM 仲裁
3. **Bio 理解**：从自然语言解析角色、行业、地点、技能
4. **摘要生成**：自动写自然语言 identity summary（替代 generator.py 目前简陋的 `_compose_summary()`）

**为什么激进**：当前 OSINT 工具（maigret、Sherlock、whatsmyname）全部基于规则引擎。**没有生产工具用 LLM 做身份关联。** 这是 clawithme 可以建立工程壁垒的地方。

**为什么可行**：
- NAS 16GB 内存在 MPS 加速下推理每对 ~1-2s
- 20 profile → 推理 ~190 对 → ~3-5 分钟（加在总搜索时间内）
- 零 API 成本，本地运行，隐私安全
- **只对高冲突 cluster 调用 LLM**——90% 的 profile 对不需要 LLM 介入

**实施路线**：新增 `signals/llm_verifier.py`，仅做以下情况：
- username 匹配（≥0.80）但 display_name 差异大（Levenshtein < 0.3）→ "是否同一人？"
- avatar_phash 匹配但 location 不同 → "是否同一人？"
- email/phone 匹配 → 不需要 LLM（这是最高置信度信号）

这个思路在当前阶段只需 1-2 天 POC，验证 `ollama pull llama4-scout` + 写一个 prompt 看推理质量。如果表现好，可以大幅提升关联引擎质量。

---

## 附录：代码级别发现

### A.1. cli.py:76-104 — Leak 搜索的 async 不一致

`_search_leaks()` 用 `asyncio.run()` 调 `async def query_leaks()`，但 engine probe 是 sync 循环。同文件、不同 phase、不同编程模型。搜索路径（email/phone）和用户名路径（username）执行模型不同。

### A.2. cli.py:248 — 引擎探针零并行

```python
for site in sites:
    engine = get_engine_for_site(site, engines)
    result = engine.probe(site, username)
```
36 站 × ~5s = 180s。`config.py:34` 有 `max_concurrency: 10` 但没用到。

### A.3. crawler/client.py:73 — 全局可变状态

```python
_last_request_at: float = 0.0
```
模块级全局变量做跨实例速率限制。当前是 sync 单线程所以安全，但 async 后需要 `asyncio.Lock`。

### A.4. correlation.py — 间接合并的证据链丢失

`edge_evidence` dict 的 key 是 `(int, int)` tuple。如果 A↔B↔C（A 和 C 被间接合并但无直接证据），报告看不到 A↔C 的传递证据。对 Louvain 不是问题（保留了全量边），但当前 Union-Find 实现中，报告的 evidence 链不完整。

### A.5. generator.py — 940 行字符串模板的脆弱性

`_HTML` 模板用 `str.format()` 渲染，所有 `{` `}` 在 CSS 中（`:root { --accent: #xxx }`）必须转义为 `{{ }}`。之前已经出过 crash，加 `_fmt_esc()` 修复了。任何新 CSS 规则都可能因为漏掉花括号导致新的 crash。

### A.6. engines.py:103 — DynamicFetcher 超时硬编码

```python
page = df.fetch(url, timeout=15000, ...)
```
应该从 Config 或 Engine params 获取。

### A.7. cli.py:455 — 路径遍历防护过于基础

```python
if ".." in str(Path(report_path)):
```
`..` 不是唯一路径遍历向量。`/proc/self/fd/0`、符号链接、`\..\`（Windows）都不被检测。但 Python 的 `Path.resolve()` 已经做了规范化——这只是冗余防御。
