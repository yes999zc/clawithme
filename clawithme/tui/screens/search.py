"""Search screen — username input with banner and options."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Select, Static

_BANNER_PATH = Path(__file__).resolve().parent.parent.parent / "web" / "app.py"


def _load_banner() -> str:
    """Extract the Unicode banner from web/app.py, cached."""
    if getattr(_load_banner, "_cache", None):
        return _load_banner._cache
    try:
        text = _BANNER_PATH.read_text()
        for prefix in ('_BANNER = r"""', '_BANNER = """'):
            start = text.find(prefix)
            if start != -1:
                start += len(prefix)
                end = text.find('"""', start)
                if end != -1:
                    _load_banner._cache = text[start:end]
                    return _load_banner._cache
        return ""
    except Exception:
        return ""


_BANNER = _load_banner() or (
    "╭───────────────────── clawithme ─────────────────────╮"
    "\n│              OSINT Identity Panorama               │"
    "\n╰────────────────────────────────────────────────────╯"
)


class SearchScreen(Screen):
    """Search input screen with banner and options."""

    def compose(self) -> ComposeResult:
        yield Static(_BANNER, id="banner")
        yield Static("", classes="spacer")
        yield Static("🔍 Username Search", classes="title")
        yield Input(
            placeholder="Enter a username, email, or phone number...",
            id="username-input",
        )
        with Horizontal(id="options"):
            yield Checkbox("Include migrated (3119 sites)", id="opt-migrated")
            yield Checkbox("Disable cache", id="opt-nocache")
            yield Checkbox("Sync mode", id="opt-sync")
            yield Checkbox("Incremental (skip cached)", id="opt-incremental")
        with Horizontal(id="lang-row"):
            yield Static("Language:")
            yield Select(
                [(x, x) for x in ("zh", "en")],
                prompt="Language",
                value="zh",
                id="lang-select",
            )
        yield Button("Search", id="search-btn", variant="primary")
        yield Static(
            "3000+ sites · 49 extractors · 9 engines · 4 report formats",
            classes="stats-line",
        )
        yield Static(
            "Ctrl+C Quit · Enter Search",
            classes="stats-line",
        )

    def on_mount(self) -> None:
        """Focus the input field on start."""
        self.query_one("#username-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Start search on Enter."""
        if event.input.id == "username-input":
            self._start_search()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Start search on button click."""
        if event.button.id == "search-btn":
            self._start_search()

    def _start_search(self) -> None:
        """Validate input and push results screen."""
        username = self.query_one("#username-input", Input).value.strip()
        if not username:
            return

        migrated = self.query_one("#opt-migrated", Checkbox).value
        no_cache = self.query_one("#opt-nocache", Checkbox).value
        sync_mode = self.query_one("#opt-sync", Checkbox).value
        incremental = self.query_one("#opt-incremental", Checkbox).value
        lang_val = self.query_one("#lang-select", Select).value
        lang = lang_val if lang_val else "zh"

        self.app.push_screen("results")
        results_screen = self.app.get_screen("results")
        results_screen.run_search(
            username=username,
            include_migrated=migrated,
            no_cache=no_cache,
            sync_mode=sync_mode,
            incremental=incremental,
            lang=lang,
        )
