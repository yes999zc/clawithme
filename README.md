# clawithme 🕵️‍♂️

**Claw the open web, with me.**

Input a username, discover their presence across 3000+ platforms — from social networks to dev communities, from Chinese local platforms to global sites. Build a complete public identity panorama.

## ⚠️ Ethical Use

**This tool queries public profiles and breach databases. Use only on accounts you own or have explicit authorization to investigate.** Unauthorized use may violate platform Terms of Service, privacy laws (GDPR, PIPL), and ethical norms.

The CLI enforces an `--acknowledge-ethical-use` gate — you must explicitly accept these terms before any search runs.

## Quick Start

```bash
pip install -e ".[dev]"
clawithme search <username> --acknowledge-ethical-use
clawithme search <username> --report report.html --acknowledge-ethical-use
```

## Pipeline

| Phase | Description |
|-------|-------------|
| 1 | Site probing (37 curated + ~2500 migrated, 9 CMS engines) |
| 2 | Profile extraction (GitHub, Zhihu extractors) |
| 3 | Leak database query (Cavalier + HIBP) |
| 4 | Multi-signal correlation (email, phone, avatar pHash, username → Union-Find clusters) |
| 5 | Geist HTML report |

## License

MIT
