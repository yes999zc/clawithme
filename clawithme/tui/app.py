"""clawithme TUI — main application."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding
from textual.screen import Screen


class TUIApp(App):
    """clawithme Terminal UI — username to identity panorama."""

    CSS = """
Screen {
    background: $surface;
}

Static.title {
    text-style: bold;
    color: $accent;
}

Button {
    margin: 1 0;
}

Button.primary {
    background: $accent;
    color: $text;
}

#banner {
    width: 100%;
    text-align: center;
    color: $text-muted;
    padding: 1 0;
}

#results-layout {
    height: 100%;
}

#overview-panel {
    height: 5;
    border: solid $primary;
    margin: 0 1;
}

#hits-panel {
    height: 1fr;
    border: solid $primary;
    margin: 0 1;
}

#profiles-panel {
    height: 1fr;
    border: solid $primary;
    margin: 0 1;
}

#clusters-panel {
    height: auto;
    border: solid $primary;
    margin: 0 1;
}

#action-bar {
    dock: bottom;
    height: 3;
    background: $panel;
    padding: 0 1;
}
"""

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        """Start on search screen."""
        self.push_screen("search")

    def action_go_home(self) -> None:
        """Return to search screen."""
        self.pop_screen()
        self.push_screen("search")


# Lazy screen registration — deferred import avoids circular deps
# ruff: noqa: PLC0415
def _get_screens() -> dict[str, type[Screen]]:
    from clawithme.tui.screens.results import ResultsScreen
    from clawithme.tui.screens.search import SearchScreen

    return {
        "search": SearchScreen,
        "results": ResultsScreen,
    }


TUIApp.SCREENS = _get_screens()
