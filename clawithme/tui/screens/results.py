"""Results screen — live search results display."""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Header, RichLog, Static

from clawithme.cache import ResultCache
from clawithme.cli import load_all_sites
from clawithme.config import load_config
from clawithme.crawler.registry import discover_extractors
from clawithme.engine.loader import load_engines
from clawithme.pipeline import AsyncPipeline
from clawithme.signals.llm_verifier import LLMVerifier


def _color_for_confidence(conf: float) -> str:
    if conf >= 0.75:
        return "green"
    if conf >= 0.30:
        return "yellow"
    return "red"


class ResultsScreen(Screen):
    """Display search results with overview, hits, profiles, clusters."""

    username = reactive("")
    hits_total = reactive(0)
    profiles_total = reactive(0)
    clusters_total = reactive(0)
    leaks_total = reactive(0)
    elapsed = reactive(0.0)
    status_text = reactive("idle")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="results-layout"):
            yield Static(id="status-bar")
            with Horizontal(id="overview-panel"):
                yield Static("", id="stat-hits")
                yield Static("", id="stat-profiles")
                yield Static("", id="stat-clusters")
                yield Static("", id="stat-leaks")
            yield Static("🌐 Hits", classes="panel-title")
            yield RichLog(id="hits-log", highlight=True, markup=True, wrap=True)
            yield Static("👤 Profiles", classes="panel-title")
            yield RichLog(
                id="profiles-log", highlight=True, markup=True, wrap=True
            )
            yield Static("🔗 Identity Clusters", classes="panel-title")
            yield RichLog(
                id="clusters-log", highlight=True, markup=True, wrap=True
            )
            with Horizontal(id="action-bar"):
                yield Button("📄 HTML", id="btn-html", variant="primary")
                yield Button("📋 JSON", id="btn-json")
                yield Button("📕 PDF", id="btn-pdf")
                yield Button("📝 MD", id="btn-md")
                yield Button("🔍 New Search", id="btn-new", variant="default")

    def watch_status_text(self, value: str) -> None:
        bar = self.query_one("#status-bar", Static)
        bar.update(f"  {value}")

    def watch_hits_total(self, value: int) -> None:
        self.query_one("#stat-hits", Static).update(f"[bold]{value}[/] hits")

    def watch_profiles_total(self, value: int) -> None:
        self.query_one("#stat-profiles", Static).update(
            f"[bold]{value}[/] profiles"
        )

    def watch_clusters_total(self, value: int) -> None:
        self.query_one("#stat-clusters", Static).update(
            f"[bold]{value}[/] clusters"
        )

    def watch_leaks_total(self, value: int) -> None:
        self.query_one("#stat-leaks", Static).update(
            f"[bold]{value}[/] leaks"
        )

    def run_search(
        self,
        username: str,
        include_migrated: bool = False,
        no_cache: bool = False,
        sync_mode: bool = False,
        lang: str = "zh",
    ) -> None:
        """Start a search in a background task."""
        self.username = username
        self.status_text = f"🔍 Searching {username}..."
        self.set_timer(0.1, lambda: self._do_search(
            username, include_migrated, no_cache, lang
        ))

    async def _do_search(
        self,
        username: str,
        include_migrated: bool,
        no_cache: bool,
        lang: str,
    ) -> None:
        """Run the pipeline and display results."""
        t0 = time.time()
        try:
            config = load_config()
            sites = load_all_sites(include_migrated=include_migrated)
            engines = load_engines()
            extractors = discover_extractors()

            cache = None if no_cache else ResultCache()

            llm = None
            try:
                from clawithme.signals.llm_verifier import (  # noqa: PLC0415
                    auto_discover_providers,
                )

                providers = auto_discover_providers()
                if providers:
                    llm = LLMVerifier(providers=providers)
            except Exception:
                pass

            pipeline = AsyncPipeline(
                sites=sites,
                engines=engines,
                extractors=extractors,
                config=config,
                cache=cache,
                llm_verifier=llm,
            )

            self.status_text = f"🔍 Probes running on {len(sites)} sites..."
            result = await pipeline.run(username)

            elapsed = time.time() - t0
            self.elapsed = elapsed
            self._display_results(result, username, elapsed)
            self.status_text = (
                f"✅ Done in {elapsed:.1f}s — "
                f"{len(result.hits)} hits · "
                f"{len(result.profiles)} profiles · "
                f"{len(result.clusters)} clusters"
            )
        except Exception as e:
            self.status_text = f"❌ Error: {e}"
            log = self.query_one("#hits-log", RichLog)
            log.write(f"[red]Search failed: {e}[/red]")

    def _display_results(self, result, username: str, elapsed: float) -> None:
        """Render search results into the panels."""
        self.hits_total = len(result.hits)
        self.profiles_total = len(result.profiles)
        self.clusters_total = len(result.clusters)
        self.leaks_total = len(result.leak_records)

        hits_log = self.query_one("#hits-log", RichLog)
        for hit in result.hits:
            site_id = hit.get("site_id", hit.get("id", "?"))
            status = hit.get("status", "?")
            url = hit.get("url", "")
            conf = hit.get("confidence", 0.5)
            color = _color_for_confidence(conf)
            hits_log.write(
                f"[{color}]●[/{color}] [bold]{site_id}[/bold] "
                f"({status}) [dim]{url}[/dim]"
            )

        profiles_log = self.query_one("#profiles-log", RichLog)
        for p in result.profiles:
            name = p.get("display_name") or p.get("username", "?")
            site = p.get("site_id", "?")
            loc = p.get("location", "")
            loc_str = f" 📍 {loc}" if loc else ""
            profiles_log.write(
                f"  [bold]{name}[/bold] [dim]@{site}{loc_str}[/dim]"
            )

        clusters_log = self.query_one("#clusters-log", RichLog)
        for i, c in enumerate(result.clusters):
            sites_in = getattr(c, "site_ids", [])
            conf_val = getattr(c, "confidence", 0.0)
            clusters_log.write(
                f"\n  Cluster {i+1}: "
                f"[bold]{', '.join(sites_in[:5])}[/bold]"
                f"{'…' if len(sites_in) > 5 else ''}"
                f" [dim]confidence={conf_val}[/dim]"
            )
            evidence = getattr(c, "evidence", [])
            for ev in evidence[:3]:
                clusters_log.write(f"    └ {ev}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle action bar buttons."""
        btn = event.button.id
        if btn == "btn-new":
            self.app.pop_screen()
        elif btn in ("btn-html", "btn-json", "btn-pdf", "btn-md"):
            fmt = {"btn-html": "html", "btn-json": "json",
                   "btn-pdf": "pdf", "btn-md": "md"}[btn]
            self.status_text = (
                f"📄 Export: use `--report report.{fmt} --format {fmt}`"
            )
