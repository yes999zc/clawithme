# clawithme — 中期审计报告

> 陪审团第四轮（中期审计）。2026-05-04

---

## 审计发现

### P0 — 4500 行 maigret 死代码

`clawithme/engine/` 下 18 个 vendored maigret 模块 + `resources/` 目录，CLI 路径完全不经过。新 Engine 系统（`engines.py` / `loader.py` / `http_client.py`）已完全替代。

**修复**：删除全部 18 个 .py 文件 + `resources/` 目录。仅保留 `http_client.py`、`engines.py`、`loader.py`。

### P0 — 7 个空壳站点标 active

以下站点 `probe_url` 为空字符串，`deprecated: false`，但实测不可探测：
- 虎扑、NGA、少数派、百度知道、开源中国、思否、站酷

**修复**：每个站点补 `probe_url` 并验证，或降级 `deprecated: true`。

### P0 — 迁移脚本 bug

`migrate_maigret.py` 第 122 行 `list(raw["sites"].values())` 丢弃了站点名（maigret 格式中站点名是 dict key），导致 110 个迁移结果全部输出 `unknown.json`。

**修复**：改为 `for name, site_data in raw["sites"].items()`，将 name 传入 migrate_site()。

### P1 — HTTP 层不统一

`CavalierSource` 直接 `import httpx`，绕过项目的 `HttpClient`（Scrapling 反指纹封装）。

**修复**：`CavalierSource` 改用 `HttpClient`。

### P1 — 0 测试

`tests/` 目录空。6885 行代码零测试。

**修复**：至少补 `test_engines.py`（Engine.probe mock 测试）和 `test_http_client.py`。

### P1 — 架构隔离未做

中国站代码应在独立插件中，当前混在主仓库。

**修复**：待 Phase 3 前完成。

---

## 自省：系统性缺陷

| 症状 | 根因 |
|------|------|
| 死代码堆积 | 只增不减，无 Phase 收尾清理 |
| 数据质量虚标 | 验收只看数字不看内容 |
| CI 门禁形同虚设 | validate.py 写了但未在 gate 强制执行 |
| 零测试 | 手动验证用完即弃 |
