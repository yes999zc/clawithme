"""Interactive LinkedIn login — one-command cookie capture.

Usage::

    clawithme linkedin-login

Opens a visible Chromium browser. You log in to LinkedIn manually.
Once logged in, cookies are captured and saved automatically.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from clawithme.logging import get_logger

logger = get_logger()

_COOKIE_DIR = Path.home() / ".config" / "clawithme"
_COOKIE_FILE = _COOKIE_DIR / "linkedin_cookies.json"

_LINKEDIN_FEED_URLS = (
    "https://www.linkedin.com/feed",
    "https://www.linkedin.com/feed/",
)


def _find_config_toml() -> Path | None:
    """Locate config.toml in the project directory."""
    candidates = [
        Path("config.toml"),                          # cwd
        Path(__file__).resolve().parent.parent / "config.toml",  # project root
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _update_config_toml(cookie_path: str) -> None:
    """Ensure config.toml has cookies.linkedin_file set."""
    config_path = _find_config_toml()
    if config_path is None:
        # config.toml doesn't exist yet — create a minimal one in project root
        config_path = Path(__file__).resolve().parent.parent / "config.toml"
        config_path.write_text(f'[cookies]\nlinkedin_file = "{cookie_path}"\n')
        print(f"   📁 已创建 {config_path}")
        return

    content = config_path.read_text()

    # Already set — skip
    if cookie_path in content:
        return

    # If [cookies] section exists, update linkedin_file
    if "[cookies]" in content:
        new_content = []
        in_cookies = False
        key_set = False
        for line in content.splitlines(True):
            if line.strip().startswith("[cookies]"):
                in_cookies = True
                new_content.append(line)
                continue
            if in_cookies and line.strip().startswith("["):
                in_cookies = False
            if in_cookies and line.strip().startswith("linkedin_file"):
                new_content.append(f'linkedin_file = "{cookie_path}"\n')
                key_set = True
                continue
            new_content.append(line)
        if not key_set and in_cookies:
            # Append before next section
            for i, line in enumerate(new_content):
                if line.strip().startswith("[") and i > 0:
                    new_content.insert(i, f'linkedin_file = "{cookie_path}"\n')
                    key_set = True
                    break
        if not key_set:
            new_content.append(f'linkedin_file = "{cookie_path}"\n')
    else:
        # No [cookies] section — append one
        content = content.rstrip()
        content += f'\n\n[cookies]\nlinkedin_file = "{cookie_path}"\n'
        new_content = [content]

    config_path.write_text("".join(new_content))
    logger.info("config_updated", key="cookies.linkedin_file", path=str(config_path))


def run_linkedin_login() -> int:
    """Interactive LinkedIn login. Returns 0 on success, 1 on failure."""
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  🔐 LinkedIn 登录                                    ║")
    print("║                                                      ║")
    print("║  即将打开浏览器窗口，请在浏览器中登录你的             ║")
    print("║  LinkedIn 账户。登录完成后 Cookie 会自动保存。       ║")
    print("║                                                      ║")
    print("║  ⚠️  仅限你自己的账户，请勿用于未授权访问。          ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    print("   正在启动浏览器...")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ 需要安装 Playwright: pip install playwright && playwright install chromium")
        return 1

    cookies_saved = False

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)

            print("   → 正在打开 LinkedIn...")
            page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            print()
            print("   ┌─────────────────────────────────────────┐")
            print("   │  👆 请在浏览器窗口中登录你的 LinkedIn     │")
            print("   │     登录完成后，Cookie 会自动捕获        │")
            print("   └─────────────────────────────────────────┘")
            print()

            # Wait for login to complete — detect feed page or profile page
            try:
                page.wait_for_url(
                    lambda url: any(
                        url.startswith(prefix)
                        for prefix in (
                            "https://www.linkedin.com/feed",
                        )
                    ),
                    timeout=300_000,  # 5 minutes for user to log in
                )
            except Exception:
                # Check if we're on any LinkedIn page with a session
                current_url = page.url
                if "linkedin.com" in current_url and "login" not in current_url:
                    print(f"   ℹ️  当前页面: {current_url}")
                else:
                    print("   ⚠️  未检测到登录完成，将尝试捕获当前 Cookie...")

            # Capture all cookies
            all_cookies = context.cookies()
            linkedin_cookies = [
                c for c in all_cookies
                if "linkedin.com" in (c.get("domain") or "")
            ]

            if not linkedin_cookies:
                print("   ❌ 未找到 LinkedIn Cookie，请确认已登录")
                browser.close()
                return 1

            # Save cookies
            _COOKIE_DIR.mkdir(parents=True, exist_ok=True)
            _COOKIE_FILE.write_text(
                json.dumps(linkedin_cookies, indent=2, ensure_ascii=False)
            )
            print(f"   ✅ 已保存 {len(linkedin_cookies)} 个 Cookie")
            print(f"   📁 {_COOKIE_FILE}")

            # Update config.toml
            _update_config_toml(str(_COOKIE_FILE))

            browser.close()
            cookies_saved = True

    except (OSError, RuntimeError) as e:
        print(f"   ❌ 浏览器启动失败: {e}")
        return 1

    if cookies_saved:
        print()
        print("   ✅ 完成！现在可以运行:")
        print(f"      clawithme search <username> --acknowledge-ethical-use")
        print()
        print("   ℹ️  Cookie 有效期约 2 周，过期后重新运行:")
        print("      clawithme linkedin-login")
        return 0

    return 1
