# Lessons Learned — clawithme

> 记录开发中踩过的坑、犯过的错，以及从中汲取的教训。
> 每个条目按：**问题 → 根因 → 教训 → 防范** 的结构。
> 最后更新：2026-05-05

---

## 1. 虚标：文件存在 ≠ 功能完成

**问题**：审计时发现 7 个 ✅ 标记是虚的——schema.json、taxonomy.json 文件存在，但管线中零引用；BreachRecord 是 Pydantic 模型但不校验格式。

**根因**：todo 用"文件已创建"作为完成标准，而非"管线可执行"。schema.json 是脚手架阶段的文档产物，写完后没有接入 `load_all_sites()`。

**教训**：
- 验收标准必须可执行：不是"文件存在"，而是"`clawithme validate` 拒绝非法 JSON"
- 每个跨越模块边界的功能，必须有一个集成测试证明管线真的调用了它

**防范**：新增任何功能模块后，从 CLI 入口跑一次端到端，确认数据流经过该模块。

---

## 2. Scrapling Fetcher.text 返回空字符串

**问题**：10 个站点切到 message 引擎后仍然误报。排查发现 Scrapling `Fetcher.get().text` 是 `TextHandler` 懒加载对象，`str()` 返回 `""`，实际内容在 `.body` 中。

**根因**：HttpClient 封装层直接 `str(page.text)`，没有检查空字符串回退。Scrapling 的 `TextHandler` 设计是惰性解码，但 `__str__` 实现有 bug（或未按预期工作）。

**教训**：
- 第三方库的"方便方法"不可信——至少验证一次返回值
- 封装层应该做防御：`text = str(page.text) or page.body.decode(encoding)`

**防范**：引入新的外部依赖后，对其核心返回值写一个 smoke test。

**修复**：`http_client.py` `_to_response()` — text 为空时从 body 解码回退。

---

## 3. HTTP 200 不表示用户存在

**问题**：37 个站点中 16 个对不存在用户返回 200，纯 status_code 引擎全部误报。

**根因**：很多站点（尤其中国站）用前端 SPA + 统一 HTTP 200 + JS 渲染错误信息。maigret 原版也是 status_code 为主，在中国站水土不服。

**教训**：
- status_code 引擎只适用于返回明确 404 的站点
- 中国站需要 message 引擎 + `absence_strs` 检测 body 中的"用户不存在"文本
- JS 渲染站点（Twitter、Twitch、少数派）需要 browser 引擎

**防范**：新增站点时，先用已知不存在用户名实测，确认 HTTP body 中可提取区分信号。

---

## 4. username 相似度阈值过低导致误合并

**问题**：`CorrelationEngine` 把 `test@gmail.com` 和 `test2@yahoo.com` 两个无关 profile 合并成一个集群。

**根因**：
1. `compare_usernames()` 对 "test" vs "test2" 的处理：剥离尾部数字后核心名相同 → 返回 0.8
2. 旧阈值 0.7 允许这个匹配通过
3. username 作为**独立**合并信号（不需要 email/phone 佐证）

**教训**：
- username 相似度应该是**辅助信号**，不应独立触发合并
- 阈值设置需要构造具体的 false-positive case 验证
- `compare_usernames()` 内部的 0.7 缩放系数使得 Levenshtein 匹配几乎永远不触发（0.99 × 0.7 = 0.69），真正起作用的是 exact/affix/digit 三条捷径

**防范**：信号系统上线前，用已知反例（不同人的相似用户名）做回归测试。

**修复**：阈值 0.7 → 0.85，同时 `n==0` 返回 `[]` 而非空 cluster。

---

## 5. disposable email 域名列表不完整

**问题**：`temporary.email`、`disposablemail.com` 等真实一次性邮箱域名不在过滤列表中。

**根因**：初始列表是手工挑选的常见域名，没有引用权威 disposable domain 列表（如 github.com/disposable-email-domains）。

**教训**：
- 手工维护的阻止列表必然有遗漏
- 应引用社区维护的权威列表作为 baseline，再叠加项目特定规则

**防范**：定期从 disposable-email-domains 仓库同步；或提供 `--allow-disposable` 开关供调试。

---

## 6. 单元测试覆盖不到管线级逻辑错误

**问题**：116 个单元测试全绿，但功能审计发现 3 个 bug：
- 空输入返回假 cluster
- username 误合并
- disposable 域名漏网

**根因**：
- `test_signals_correlation.py` 只测了显式的 email/phone/avatar 匹配
- 没有测"两个不同邮箱 + 相似 username = 不应合并"
- 没有测"空 profiles 列表 = 空 clusters"
- `test_signals_extraction.py` 没有用真实 disposable 域名测试

**教训**：
- 单元测试测的是"代码怎么写"，功能审计测的是"用户怎么用"
- 每个模块至少 3 个端到端 case：正常路径、边界路径、异常路径
- 不要假设测试覆盖了所有逻辑——主动构造反例

**防范**：每个 Phase 交付前跑一次功能审计，用真实数据（不是 mock）验证管线。

---

## 7. CavalierSource ≠ 通用泄露库

**问题**：用户搜 `364939526@qq.com` 期望看到泄露记录，但 Cavalier 返回 0 条。实际上这个邮箱可能在其他泄露库中有记录。

**根因**：Cavalier（Hudson Rock）只覆盖 infostealer 日志，不是通用 breach database。HIBP 覆盖通用泄露库，但 clawithme 未接入。

**教训**：
- 数据源的能力边界必须在文档中明确说明
- "查泄露"这个需求需要多个互补数据源，单一 API 不够

**防范**：接入 HIBP 作为第二数据源；在 CLI 输出中注明查询了哪些源。

---

## 8. 开源中国 — 存在/不存在页面完全相同

**问题**：oschina 对所有用户返回相同的 2810 字节 HTML 页面，无法通过 HTTP 区分。

**根因**：站点使用 JS 渲染 + 统一壳页面，用户信息完全由 API 动态加载。

**教训**：
- 不是所有站点都能通过单次 HTTP GET 区分
- 新增站点时必须实测不存在用户名，确认可区分后再标记 active
- 无法区分的站点应立即 `deprecated: true`，而不是带着误报跑

**防范**：站点入库 checklist 增加"已知不存在用户名实测"步骤。

---

## 9. Pydantic 模型需要显式 field validator

**问题**：`BreachRecord` 声明为"自动校验类型"，但只校验了 str vs int，不校验 email 格式、phone 长度、sha256 格式。

**根因**：Pydantic 的"类型校验"只到类型层面，格式校验需要 `@field_validator`。初期没加是因为"字段都是 Optional，数据源返回什么就存什么"的想法。

**教训**：
- Pydantic model 的校验粒度必须在定义时明确：类型、格式、业务规则
- "Optional 所以不用校验"是错的——Optional 只表示可以不传，传了就应该合法
- 校验逻辑写进 model 比散落在调用方好——出问题时在一处修

**防范**：所有 Pydantic model 至少检查：必填字段有格式约束、Optional 字段传了就要合法。

**修复**：添加 `_validate_email`、`_validate_phone`、`_validate_sha256` 三个 field_validator。

---

## 10. CLI help 不够友好

**问题**：`clawithme --help` 输出 `Unknown command: --help`，`clawithme` 无参数只显示 `search` 和 `verify`，不提示 `validate` 和 `--format json`。

**根因**：CLI 是手写 `if/elif` 解析，没有用 argparse/click，help 是事后补的。

**教训**：
- 手写参数解析适合 <5 个命令的 CLI，但要刻意维护 usage 输出
- 每加一个新命令/参数，必须同步更新 help 文本

**防范**：新增 CLI 功能时 checklist：usage 字符串、无参数时的提示、错误命令时的提示。

---

## 检查清单（新增功能前）

- [ ] 端到端 CLI 验证（不是单元测试）
- [ ] 不存在用户名实测（站点入库）
- [ ] 已知反例测试（信号/关联模块）
- [ ] CLI help 更新
- [ ] 第三方返回值 smoke test（新依赖）
- [ ] Pydantic model 格式校验（新 model）
- [ ] 数据源能力边界文档化（新数据源）
