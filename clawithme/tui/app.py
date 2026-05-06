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

#banner {
    width: 100%;
    text-align: center;
    color: $text-muted;
    padding: 1 0;
}

#results-layout {
    height: 100%;
    layout: vertical;
}

#status-bar {
    height: 1;
    color: $text-muted;
    padding: 0 1;
}

#overview-panel {
    height: 3;
    layout: horizontal;
}

#loading {
    display: none;
}

#hits-log, #profiles-log, #clusters-log, #leaks-log {
    height: 1fr;
    border: solid $primary;
    margin: 0 1;
}

.panel-title {
    text-style: bold;
    color: $accent;
    padding: 0 1;
    margin-top: 1;
}

#action-bar {
    dock: bottom;
    height: 3;
    background: $panel;
    padding: 0 1;
    layout: horizontal;
}

Button {
    margin: 1 0;
}

Button.primary {
    background: $accent;
    color: $text;
}

Button.error {
    background: $error;
    color: $text;
}

.search-title {
    text-style: bold;
    color: $accent;
    padding: 0 1;
}

#options {
    layout: horizontal;
    height: 3;
}

#lang-row {
    layout: horizontal;
    height: 3;
}

.stats-line {
    color: $text-muted;
    padding: 1;
}
"""

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("escape", "go_home", "Home"),
        Binding("ctrl+n", "go_home", "New Search"),
    ]

    def on_mount(self) -> None:
        """Start on search screen."""
        self.push_screen("search")

    def action_go_home(self) -> None:
        """Return to search screen from results."""
        # Only pop if not already on search screen
        if len(self.screen_stack) > 1:
            screen = self.screen_stack[-1]
            if hasattr(screen, "_searching"):
                screen._searching = False
            self.pop_screen()


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
