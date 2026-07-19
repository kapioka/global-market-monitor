from __future__ import annotations

from project.risk_engine_v2_episode_chronicle_renderer import render_episode_chronicle_html
from project.tests.test_risk_engine_v2_episode_chronicle import _build


def test_renderer_embeds_offline_accessible_workspace() -> None:
    payload = _build()
    html = render_episode_chronicle_html(payload)

    assert 'data-generation-id="aaaaaaaaaaaaaaaa"' in html
    assert "市場警戒年代記" in html
    assert 'id="episode-index"' in html
    assert 'id="episode-chart"' in html
    assert 'id="series-controls"' in html
    assert 'id="series-readout"' in html
    assert "comparisonSeries(item)" in html
    assert "slice(0,5)" in html
    assert "state.visibleSeries" in html
    assert "開始値=100" in html
    assert 'aria-label="証拠と評価"' in html
    assert "prefers-reduced-motion" in html
    assert "overflow-y:scroll" in html
    assert "scrollbar-gutter:stable" in html
    assert ".workspace::-webkit-scrollbar { width:0; height:0; }" in html
    assert "scrollbar-width:none" in html
    assert "overflow-x:auto; overflow-y:hidden" in html
    assert ".tabs::-webkit-scrollbar { height:10px; }" in html
    assert "recentTabs.scrollLeft+=event.deltaY" in html
    assert "{passive:false}" in html
    assert 'aria-label="エピソード一覧（縦スクロール）"' in html
    assert "list.querySelector('.episode-item.active')?.scrollIntoView({block:'nearest'});" in html
    assert 'target="_blank"' not in html
    assert "http://" not in html.lower()
    assert "https://" not in html.lower()
    assert "cdn" not in html.lower()


def test_renderer_escapes_embedded_script_termination() -> None:
    payload = _build()
    payload["episodes"][0]["title"] = "</script><script>bad()</script>"
    html = render_episode_chronicle_html(payload)

    assert "</script><script>bad()" not in html
    assert "\\u003c/script\\u003e" in html
