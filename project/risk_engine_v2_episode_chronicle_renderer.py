from __future__ import annotations

import html
import json
from typing import Any


def render_episode_chronicle_html(payload: dict[str, Any]) -> str:
    generation_id = str(payload.get("generation_id") or "unknown")
    escaped_generation_id = html.escape(generation_id, quote=True)
    embedded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    embedded = embedded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return _TEMPLATE.replace("__GENERATION_ID__", escaped_generation_id).replace("__CHRONICLE_DATA__", embedded)


_TEMPLATE = r"""<!doctype html>
<html lang="ja" data-generation-id="__GENERATION_ID__">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <link rel="icon" href="data:,">
  <title>市場警戒年代記</title>
  <style>
    :root {
      --navy:#082742; --navy-2:#123a5b; --paper:#f7f5ef; --paper-2:#fbfaf6;
      --ink:#102c46; --muted:#607083; --line:#d6d9d7; --line-dark:#aeb6bd;
      --amber:#c87f13; --amber-soft:#f4e7d3; --red:#d7342e; --red-soft:#f8ded8;
      --green:#287747; --green-soft:#e3eee2; --blue-soft:#e5eef5; --focus:#3b82b6;
      --header:58px; --index:320px; --inspector:340px;
      font-family:"Yu Gothic UI","Hiragino Kaku Gothic ProN",Meiryo,sans-serif;
    }
    * { box-sizing:border-box; }
    html,body { margin:0; min-height:100%; background:var(--paper); color:var(--ink); }
    body { overflow:hidden; }
    button,input,select { font:inherit; }
    button { color:inherit; }
    :focus-visible { outline:3px solid color-mix(in srgb,var(--focus) 75%,white); outline-offset:2px; }
    .topbar { height:var(--header); display:flex; align-items:center; gap:20px; padding:0 18px;
      background:var(--navy); color:white; box-shadow:0 1px 8px #00182b55; position:relative; z-index:20; }
    .brand { display:flex; align-items:center; gap:10px; min-width:max-content; }
    .brand-mark { font-size:25px; line-height:1; }
    .brand h1 { font-family:"Yu Mincho","Hiragino Mincho ProN",serif; font-size:25px; letter-spacing:.08em; margin:0; }
    .read-only { border:1px solid #ffffff2f; border-radius:4px; padding:7px 10px; color:#dce8f0; font-size:12px; }
    .top-actions { margin-left:auto; display:flex; align-items:center; gap:8px; }
    .top-actions button { min-height:44px; border:0; background:transparent; color:white; border-radius:4px; padding:0 12px; cursor:pointer; }
    .top-actions button:hover { background:#ffffff14; }
    .app { height:calc(100vh - var(--header)); height:calc(100svh - var(--header)); display:grid;
      grid-template-columns:var(--index) minmax(560px,1fr) var(--inspector); grid-template-areas:"index workspace inspector"; }
    .index-pane { grid-area:index; background:var(--paper-2); border-right:1px solid var(--line); display:flex; flex-direction:column; min-width:0; min-height:0; overflow:hidden; }
    .pane-heading { padding:20px 18px 12px; font-family:"Yu Mincho","Hiragino Mincho ProN",serif; font-size:18px; margin:0; }
    .index-controls { padding:0 14px 12px; display:grid; gap:9px; }
    .search-wrap { position:relative; }
    .search-wrap span { position:absolute; left:12px; top:12px; color:var(--muted); }
    .search-wrap input { width:100%; min-height:44px; padding:9px 12px 9px 36px; border:1px solid var(--line-dark); background:white; border-radius:5px; }
    .filter-row { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
    .filter-row select { min-height:44px; border:1px solid var(--line); background:white; border-radius:4px; padding:0 8px; }
    .index-count { color:var(--muted); font-size:12px; padding:0 2px; }
    .episode-list { flex:1 1 auto; min-height:0; overflow-x:hidden; overflow-y:scroll; overscroll-behavior:contain; scrollbar-gutter:stable;
      scrollbar-color:var(--line-dark) transparent; scrollbar-width:thin; padding:0 8px 18px; display:grid; align-content:start; gap:8px; }
    .episode-list::-webkit-scrollbar { width:10px; }
    .episode-list::-webkit-scrollbar-track { background:transparent; }
    .episode-list::-webkit-scrollbar-thumb { background:#aeb6bd; border:3px solid var(--paper-2); border-radius:10px; }
    .episode-list::-webkit-scrollbar-thumb:hover { background:#7f8d98; }
    .episode-item { width:100%; min-height:86px; border:1px solid var(--line); border-left:3px solid transparent; background:transparent;
      border-radius:4px; text-align:left; padding:12px 12px 10px; cursor:pointer; transition:background .14s ease,border-color .14s ease,transform .14s ease; }
    .episode-item:hover { background:white; transform:translateX(2px); }
    .episode-item.active { background:var(--blue-soft); border-color:#9eb6c9; border-left-color:var(--navy-2); }
    .episode-item .date-title { display:flex; gap:8px; align-items:flex-start; font-family:"Yu Mincho","Hiragino Mincho ProN",serif; font-weight:700; line-height:1.45; }
    .episode-item .dot { width:10px; height:10px; border:2px solid var(--navy); border-radius:50%; margin-top:5px; flex:none; }
    .episode-item.active .dot { background:var(--navy); }
    .item-meta { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:9px; font-size:11px; }
    .tag { display:inline-flex; align-items:center; min-height:24px; border:1px solid var(--line-dark); border-radius:4px; padding:2px 8px; background:#fff9; }
    .tag.mature { color:var(--navy); border-color:#7e9db7; background:#edf5fa; }
    .tag.pending { color:#8a5508; border-color:#d69b49; background:#fff4e2; }
    .tag.protective { color:var(--green); border-color:#8aae94; background:var(--green-soft); }
    .index-footer { margin-top:auto; padding:14px 16px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; }
    .workspace { grid-area:workspace; min-width:0; overflow:auto; scrollbar-width:none; -ms-overflow-style:none; background:var(--paper); }
    .workspace::-webkit-scrollbar { width:0; height:0; }
    .tabs { height:54px; display:flex; align-items:end; gap:0; border-bottom:1px solid var(--line); padding:0 14px; overflow-x:auto; overflow-y:hidden;
      overscroll-behavior-x:contain; scrollbar-width:thin; scrollbar-color:#8096a8 transparent; background:#f4f2ed; }
    .tabs::-webkit-scrollbar { height:10px; }
    .tabs::-webkit-scrollbar-track { background:transparent; }
    .tabs::-webkit-scrollbar-thumb { background:#8096a8; border:2px solid #f4f2ed; border-radius:10px; }
    .tab { min-width:146px; max-width:220px; height:42px; border:1px solid var(--line); border-bottom:0; background:#f7f5ef; padding:0 14px;
      border-radius:5px 5px 0 0; cursor:pointer; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .tab.active { background:var(--paper-2); font-weight:700; position:relative; top:1px; }
    .workspace-inner { padding:22px 24px 28px; animation:episode-enter .16s ease-out; }
    .episode-header { display:flex; align-items:flex-start; gap:18px; padding-bottom:16px; border-bottom:1px solid var(--line); }
    .episode-header h2 { font-family:"Yu Mincho","Hiragino Mincho ProN",serif; font-size:30px; letter-spacing:.02em; margin:0; line-height:1.25; }
    .badges { margin-left:auto; display:flex; flex-wrap:wrap; justify-content:flex-end; gap:8px; }
    .badge { min-height:32px; display:inline-flex; align-items:center; border:1px solid var(--line-dark); border-radius:4px; padding:4px 12px; background:white; font-size:13px; }
    .badge.protective { color:var(--green); border-color:#88a991; background:var(--green-soft); }
    .episode-subhead { display:flex; gap:30px; align-items:center; min-height:48px; font-size:13px; }
    .episode-subhead strong { font-size:15px; }
    .episode-subhead .range { color:var(--muted); }
    .chart-shell { min-height:395px; position:relative; }
    #episode-chart { display:block; width:100%; height:auto; min-height:360px; overflow:visible; }
    .series-controls { display:flex; align-items:center; flex-wrap:wrap; gap:8px 14px; margin:4px 0 8px; padding:10px 12px;
      border:1px solid var(--line); border-radius:5px; background:#fff8; }
    .series-controls legend { padding:0 5px; color:var(--muted); font-size:12px; }
    .series-toggle { display:inline-flex; align-items:center; gap:6px; min-height:32px; font-size:12px; cursor:pointer; }
    .series-toggle input { width:17px; height:17px; accent-color:var(--navy-2); }
    .series-toggle.benchmark { font-weight:700; cursor:default; }
    .series-chip { width:22px; height:3px; border-radius:2px; background:var(--series-color); }
    .series-readout { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:6px; margin:0 0 10px; }
    .readout-card { border-left:3px solid var(--series-color); padding:5px 8px; background:#fff8; font-size:11px; color:var(--muted); }
    .readout-card strong { display:block; color:var(--ink); font-size:12px; }
    .chart-empty { display:grid; place-items:center; min-height:360px; color:var(--muted); }
    .chart-legend { display:flex; justify-content:center; gap:28px; flex-wrap:wrap; color:var(--muted); font-size:12px; margin:2px 0 18px; }
    .legend-swatch { display:inline-block; width:22px; height:10px; margin-right:7px; vertical-align:middle; }
    .legend-swatch.drawdown { background:var(--red-soft); }
    .legend-swatch.recovery { background:var(--green-soft); }
    .narrative-heading { font-family:"Yu Mincho","Hiragino Mincho ProN",serif; font-size:17px; border-bottom:1px solid var(--line); margin:0; padding:0 0 8px; }
    .narrative { display:grid; grid-auto-flow:column; grid-auto-columns:minmax(150px,1fr); overflow-x:auto; padding:16px 0 6px; }
    .narrative-item { position:relative; min-height:150px; border:0; border-top:1px solid var(--line-dark); background:transparent; padding:18px 16px 8px 4px; text-align:left; cursor:pointer; }
    .narrative-item::before { content:""; position:absolute; width:11px; height:11px; border-radius:50%; background:var(--navy); top:-6px; left:4px; box-shadow:0 0 0 3px var(--paper); }
    .narrative-item.warning::before { background:var(--amber); }
    .narrative-item.danger::before,.narrative-item.outcome::before { background:var(--red); }
    .narrative-item.recovery::before { background:var(--green); }
    .narrative-item.selected { background:linear-gradient(180deg,#ffffffa0,transparent 85%); }
    .narrative-item time { color:var(--muted); font-size:11px; }
    .narrative-item strong { display:block; margin:7px 0; font-size:13px; }
    .narrative-item p { margin:0; color:#405264; font-size:11px; line-height:1.7; }
    .inspector { grid-area:inspector; min-width:0; overflow:auto; background:var(--paper-2); border-left:1px solid var(--line); padding:20px 16px; }
    .inspector h2 { font-family:"Yu Mincho","Hiragino Mincho ProN",serif; font-size:18px; margin:0 0 14px; padding-bottom:10px; border-bottom:1px solid var(--line); }
    .inspector h3 { font-size:13px; margin:18px 0 8px; }
    .metrics { border:1px solid var(--line); border-radius:5px; padding:4px 12px; background:#fff8; }
    .metric { display:grid; grid-template-columns:34px 1fr auto; align-items:center; gap:8px; min-height:70px; border-bottom:1px solid var(--line); }
    .metric:last-child { border-bottom:0; }
    .metric-icon { font-size:21px; color:var(--navy); }
    .metric-label { font-weight:700; font-size:13px; }
    .metric small { color:var(--muted); display:block; font-weight:400; margin-top:3px; }
    .metric-value { font-family:Georgia,serif; font-size:24px; white-space:nowrap; }
    .metric-value.danger { color:var(--red); }
    .metric-value.good { color:var(--green); font-family:inherit; font-size:16px; font-weight:700; }
    .inspector-block { border:1px solid var(--line); border-radius:5px; background:#fff8; padding:10px 11px; font-size:12px; line-height:1.7; }
    .inspector-list { margin:0; padding-left:18px; }
    .provenance { display:grid; grid-template-columns:1fr 1fr; gap:3px 12px; color:#405264; word-break:break-all; }
    .mobile-index-button { display:none; }
    .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
    .svg-grid { stroke:#cfd4d7; stroke-width:1; stroke-dasharray:3 4; }
    .svg-axis-label { fill:#657789; font-size:11px; }
    .svg-series { fill:none; stroke:var(--series-color); stroke-width:1.7; vector-effect:non-scaling-stroke; }
    .svg-series.benchmark { stroke-width:3; }
    .svg-marker line { stroke-width:1.2; vector-effect:non-scaling-stroke; }
    .svg-marker circle { stroke:white; stroke-width:2; cursor:pointer; }
    .svg-marker text { font-size:11px; font-weight:700; }
    .svg-marker.warning line,.svg-marker.warning circle { stroke:var(--amber); fill:var(--amber); }
    .svg-marker.warning text { fill:#9c5d00; }
    .svg-marker.danger line,.svg-marker.danger circle,.svg-marker.outcome line,.svg-marker.outcome circle { stroke:var(--red); fill:var(--red); }
    .svg-marker.danger text,.svg-marker.outcome text { fill:#b22520; }
    .svg-marker.recovery line,.svg-marker.recovery circle { stroke:var(--green); fill:var(--green); }
    .svg-marker.recovery text { fill:var(--green); }
    .svg-marker.selected circle { r:7; filter:drop-shadow(0 0 3px #0a2748aa); }
    @keyframes episode-enter { from { opacity:.35; transform:translateY(4px); } to { opacity:1; transform:none; } }
    @media (max-width:1199px) {
      :root { --inspector:310px; }
      .app { grid-template-columns:minmax(0,1fr) var(--inspector); grid-template-areas:"workspace inspector"; }
      .index-pane { position:fixed; left:0; top:var(--header); bottom:0; width:min(360px,88vw); z-index:30; transform:translateX(-105%); box-shadow:10px 0 24px #00182b33; transition:transform .18s ease; }
      body.index-open .index-pane { transform:none; }
      .mobile-index-button { display:inline-flex; align-items:center; }
    }
    @media (max-width:767px) {
      body { overflow:auto; }
      .topbar { padding:0 10px; gap:8px; }
      .brand h1 { font-size:19px; }
      .brand-mark,.read-only,.top-actions .desktop-label { display:none; }
      .app { height:auto; min-height:calc(100svh - var(--header)); display:block; }
      .workspace { overflow:visible; }
      .workspace-inner { padding:16px 14px 22px; }
      .episode-header { display:block; }
      .episode-header h2 { font-size:24px; }
      .badges { margin:12px 0 0; justify-content:flex-start; }
      .episode-subhead { align-items:flex-start; flex-direction:column; gap:3px; padding:10px 0; }
      .chart-shell { min-height:290px; overflow-x:auto; }
      #episode-chart { min-width:700px; min-height:290px; }
      .series-readout { grid-template-columns:1fr 1fr; }
      .narrative { grid-auto-columns:75vw; }
      .inspector { border-left:0; border-top:1px solid var(--line); padding:18px 14px 28px; }
    }
    @media (prefers-reduced-motion:reduce) {
      *,*::before,*::after { scroll-behavior:auto!important; animation-duration:.01ms!important; animation-iteration-count:1!important; transition-duration:.01ms!important; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand"><span class="brand-mark" aria-hidden="true">▤</span><h1>市場警戒年代記</h1></div>
    <span class="read-only">読み取り専用・本体判断への影響なし</span>
    <div class="top-actions">
      <button type="button" class="mobile-index-button" id="index-toggle" aria-controls="episode-index" aria-expanded="false">☰ <span>目次</span></button>
      <button type="button" id="focus-search">⌕ <span class="desktop-label">検索</span></button>
      <button type="button" id="focus-filter">▽ <span class="desktop-label">フィルター</span></button>
    </div>
  </header>
  <div class="app">
    <aside class="index-pane" id="episode-index" aria-label="エピソード目次">
      <h2 class="pane-heading">エピソード目次</h2>
      <div class="index-controls">
        <label class="search-wrap"><span aria-hidden="true">⌕</span><span class="sr-only">エピソード検索</span><input id="episode-search" type="search" placeholder="日付・分類・市場局面を検索"></label>
        <div class="filter-row">
          <label><span class="sr-only">種類</span><select id="type-filter"><option value="">すべての種類</option></select></label>
          <label><span class="sr-only">成熟度</span><select id="maturity-filter"><option value="">すべての状態</option></select></label>
        </div>
        <div class="index-count" id="episode-count"></div>
      </div>
      <div class="episode-list" id="episode-list" tabindex="0" aria-label="エピソード一覧（縦スクロール）"></div>
      <div class="index-footer" id="index-footer"></div>
    </aside>
    <main class="workspace" id="workspace">
      <nav class="tabs" id="recent-tabs" aria-label="最近開いたエピソード"></nav>
      <div class="workspace-inner" id="workspace-inner">
        <header class="episode-header"><h2 id="episode-title"></h2><div class="badges" id="episode-badges"></div></header>
        <div class="episode-subhead"><strong id="benchmark"></strong><span class="range" id="date-range"></span></div>
        <fieldset class="series-controls" id="series-controls"><legend>警戒判定に寄与した関連指標（最大5系列・開始値=100）</legend></fieldset>
        <div class="chart-shell"><svg id="episode-chart" viewBox="0 0 920 400" role="img" aria-labelledby="chart-title chart-description"><title id="chart-title">市場価格と警戒局面</title><desc id="chart-description">選択したエピソードの価格推移と証拠マーカーです。</desc></svg></div>
        <div class="series-readout" id="series-readout" aria-live="polite"></div>
        <div class="chart-legend"><span><i class="legend-swatch drawdown"></i>ドローダウン</span><span><i class="legend-swatch recovery"></i>回復局面</span></div>
        <h3 class="narrative-heading">この局面で何が起きたか</h3>
        <div class="narrative" id="narrative"></div>
      </div>
    </main>
    <aside class="inspector" aria-label="証拠と評価">
      <h2>証拠と評価</h2>
      <h3>定量サマリー</h3>
      <div class="metrics" id="metrics"></div>
      <h3>評価コメント</h3><div class="inspector-block" id="evaluation-comment"></div>
      <h3>主な根拠</h3><div class="inspector-block"><ul class="inspector-list" id="evidence-list"></ul></div>
      <h3>データ・出所</h3><div class="inspector-block provenance" id="provenance"></div>
    </aside>
  </div>
  <script type="application/json" id="chronicle-data">__CHRONICLE_DATA__</script>
  <script>
  (() => {
    'use strict';
    const data = JSON.parse(document.getElementById('chronicle-data').textContent);
    const episodes = Array.isArray(data.episodes) ? data.episodes : [];
    const state = { selectedId: data.summary?.latest_event_id || episodes[0]?.event_id, recent: [], markerId: null, focusDate: null, visibleSeries: new Set() };
    const byId = new Map(episodes.map(item => [item.event_id, item]));
    const list = document.getElementById('episode-list');
    const recentTabs = document.getElementById('recent-tabs');
    const search = document.getElementById('episode-search');
    const typeFilter = document.getElementById('type-filter');
    const maturityFilter = document.getElementById('maturity-filter');
    const svgNS = 'http' + '://' + 'www.w3.org/2000/svg';
    const svg = document.getElementById('episode-chart');

    function node(tag, className, text) {
      const element = document.createElement(tag);
      if (className) element.className = className;
      if (text !== undefined) element.textContent = text;
      return element;
    }
    function svgNode(tag, attrs = {}) {
      const element = document.createElementNS(svgNS, tag);
      Object.entries(attrs).forEach(([key,value]) => element.setAttribute(key, String(value)));
      return element;
    }
    function percent(value) { return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'; }
    function formatDate(value) { if (!value) return '—'; const [y,m,d] = String(value).slice(0,10).split('-'); return `${y}/${m}/${d}`; }
    const seriesColors=['#082742','#287f8e','#4d6fa9','#7b639f','#8b6d4f'];
    function comparisonSeries(item) {
      const supplied=Array.isArray(item.comparison_series)?item.comparison_series.slice(0,5):[];
      if(supplied.length && supplied[0]?.is_benchmark===true) return supplied;
      const chart=item.chart_points||[]; if(!chart.length) return [];
      const baseline=Number(chart[0].benchmark_price);
      return [{series_id:item.benchmark?.id||'ACWI',label:item.benchmark?.id||'ACWI',domain_label:'グローバル株式',is_benchmark:true,raw_unit:'price',points:chart.map(point=>({date:point.date,observation_date:point.date,raw_value:Number(point.benchmark_price),indexed_value:Number(point.benchmark_price)/baseline*100}))}];
    }
    function resetSeriesState(item) { const rows=comparisonSeries(item); state.visibleSeries=new Set(rows.map(row=>row.series_id)); state.focusDate=item.dates?.anchor||rows[0]?.points?.at(-1)?.date||null; }
    function addOptions(select, rows, key) {
      const values = new Map(); rows.forEach(row => values.set(row[key].status, row[key].label));
      [...values.entries()].sort().forEach(([value,label]) => { const option=node('option','',label); option.value=value; select.append(option); });
    }
    addOptions(typeFilter, episodes, 'event_type'); addOptions(maturityFilter, episodes, 'maturity');

    function filteredEpisodes() {
      const query = search.value.trim().toLowerCase();
      return episodes.filter(item => {
        const text = [item.title,item.event_type.label,item.classification.label,item.maturity.label,item.dates.anchor].join(' ').toLowerCase();
        return (!query || text.includes(query)) && (!typeFilter.value || item.event_type.status === typeFilter.value) && (!maturityFilter.value || item.maturity.status === maturityFilter.value);
      });
    }
    function renderList() {
      const rows = filteredEpisodes(); list.replaceChildren();
      rows.forEach(item => {
        const button=node('button',`episode-item${item.event_id===state.selectedId?' active':''}`); button.type='button';
        button.dataset.eventId=item.event_id; button.setAttribute('aria-pressed',String(item.event_id===state.selectedId));
        const heading=node('div','date-title'); heading.append(node('span','dot'),node('span','',item.title));
        const meta=node('div','item-meta'); meta.append(node('span','tag',item.event_type.label),node('span',`tag ${item.maturity.status}`,item.maturity.label));
        button.append(heading,meta); button.addEventListener('click',()=>selectEpisode(item.event_id)); list.append(button);
      });
      document.getElementById('episode-count').textContent=`新しい順・${rows.length}件`;
      document.getElementById('index-footer').textContent=`全${episodes.length}件 / 生成 ${String(DATA.generated_at || '-')}`;
      list.querySelector('.episode-item.active')?.scrollIntoView({block:'nearest'});
    }
    function selectEpisode(eventId) {
      if (!byId.has(eventId)) return;
      state.selectedId=eventId; state.markerId=null; resetSeriesState(byId.get(eventId));
      state.recent=[eventId,...state.recent.filter(id=>id!==eventId)].slice(0,5);
      renderList(); renderTabs(); renderEpisode();
      document.body.classList.remove('index-open'); document.getElementById('index-toggle').setAttribute('aria-expanded','false');
    }
    function renderTabs() {
      const tabs=document.getElementById('recent-tabs'); tabs.replaceChildren();
      state.recent.forEach(id => { const item=byId.get(id); const button=node('button',`tab${id===state.selectedId?' active':''}`,item.title); button.type='button'; button.setAttribute('aria-current',id===state.selectedId?'page':'false'); button.addEventListener('click',()=>selectEpisode(id)); tabs.append(button); });
    }
    function badge(text,className='') { return node('span',`badge ${className}`,text); }
    function renderEpisode() {
      const item=byId.get(state.selectedId); if (!item) return;
      const inner=document.getElementById('workspace-inner'); inner.style.animation='none'; requestAnimationFrame(()=>{inner.style.animation='';});
      document.getElementById('episode-title').textContent=item.title;
      const badges=document.getElementById('episode-badges'); badges.replaceChildren(badge(item.maturity.label,item.maturity.status),badge(item.split.excluded?`${item.split.name}・境界除外`:item.split.name),badge(item.classification.label,item.classification.status));
      document.getElementById('benchmark').textContent=`${item.benchmark.id}（${item.benchmark.source}）`;
      document.getElementById('date-range').textContent=`${formatDate(item.dates.display_start)} ～ ${formatDate(item.dates.display_end)}`;
      document.getElementById('chart-description').textContent=`${item.title}。${item.chart_points.length}観測点、${item.markers.length}証拠マーカー。`;
      renderSeriesControls(item); renderChart(item); renderNarrative(item); renderInspector(item);
    }
    function renderSeriesControls(item) {
      const controls=document.getElementById('series-controls'); controls.replaceChildren();
      const legend=node('legend','','警戒判定に寄与した関連指標（最大5系列・開始値=100）'); controls.append(legend);
      comparisonSeries(item).forEach((series,index)=>{
        const label=node('label',`series-toggle${series.is_benchmark?' benchmark':''}`); label.style.setProperty('--series-color',seriesColors[index]);
        const input=node('input'); input.type='checkbox'; input.checked=series.is_benchmark||state.visibleSeries.has(series.series_id); input.disabled=series.is_benchmark; input.setAttribute('aria-label',`${series.label}を表示`);
        const chip=node('span','series-chip'); chip.setAttribute('aria-hidden','true'); label.append(input,chip,node('span','',`${series.label}・${series.domain_label}`));
        if(!series.is_benchmark) input.addEventListener('change',()=>{ if(input.checked) state.visibleSeries.add(series.series_id); else state.visibleSeries.delete(series.series_id); renderChart(item); });
        controls.append(label);
      });
    }
    function renderChart(item) {
      [...svg.children].filter(child=>!['title','desc'].includes(child.tagName.toLowerCase())).forEach(child=>child.remove());
      const points=item.chart_points||[]; const allSeries=comparisonSeries(item); const visible=allSeries.filter(series=>series.is_benchmark||state.visibleSeries.has(series.series_id)); if (!points.length||!visible.length) return;
      const W=920,H=400,left=50,right=20,top=30,bottom=44,innerW=W-left-right,innerH=H-top-bottom;
      const values=visible.flatMap(series=>(series.points||[]).map(point=>Number(point.indexed_value)).filter(Number.isFinite)); const min=Math.min(...values),max=Math.max(...values); const pad=Math.max((max-min)*.12,2);
      const yMin=min-pad,yMax=max+pad; const x=i=>left+(points.length===1?innerW/2:i*innerW/(points.length-1)); const y=value=>top+(yMax-value)*innerH/(yMax-yMin);
      for(let i=0;i<5;i++){ const yy=top+i*innerH/4; svg.append(svgNode('line',{x1:left,y1:yy,x2:W-right,y2:yy,class:'svg-grid'})); const label=svgNode('text',{x:left-8,y:yy+4,'text-anchor':'end',class:'svg-axis-label'}); label.textContent=(yMax-i*(yMax-yMin)/4).toFixed(0); svg.append(label); }
      const tickIndexes=[0,Math.floor((points.length-1)/4),Math.floor((points.length-1)/2),Math.floor((points.length-1)*3/4),points.length-1];
      [...new Set(tickIndexes)].forEach(index=>{ const label=svgNode('text',{x:x(index),y:H-12,'text-anchor':'middle',class:'svg-axis-label'}); label.textContent=formatDate(points[index].date); svg.append(label); });
      let runStart=0; for(let i=1;i<=points.length;i++){ const previous=points[runStart].confirmed_stage; if(i===points.length || points[i].confirmed_stage!==previous){ if(['warning','danger','extreme'].includes(previous)){ const rect=svgNode('rect',{x:x(runStart),y:top,width:Math.max(2,x(Math.max(runStart,i-1))-x(runStart)),height:innerH,fill:previous==='warning'?'#f4e7d3':'#f8ded8',opacity:.55}); svg.append(rect); } runStart=i; } }
      const benchmark=allSeries[0]; const benchmarkValues=new Map((benchmark.points||[]).map(point=>[point.date,Number(point.indexed_value)]));
      const benchmarkPath=points.map((point,index)=>({index,value:benchmarkValues.get(point.date)})).filter(point=>Number.isFinite(point.value));
      if(benchmarkPath.length){ const area=benchmarkPath.map((point,i)=>`${i?'L':'M'}${x(point.index)},${y(point.value)}`).join(' ')+` L${x(benchmarkPath.at(-1).index)},${y(100)} L${x(benchmarkPath[0].index)},${y(100)} Z`; svg.append(svgNode('path',{d:area,fill:'#dbe5ec',opacity:.36})); }
      visible.forEach(series=>{ const seriesIndex=allSeries.indexOf(series); const byDate=new Map((series.points||[]).map(point=>[point.date,Number(point.indexed_value)])); let path='',drawing=false; points.forEach((point,index)=>{const value=byDate.get(point.date);if(Number.isFinite(value)){path+=`${drawing?' L':'M'}${x(index)},${y(value)}`;drawing=true;}else{drawing=false;}}); if(path) svg.append(svgNode('path',{d:path,class:`svg-series${series.is_benchmark?' benchmark':''}`,style:`--series-color:${seriesColors[seriesIndex]};${series.is_benchmark?'':'stroke-dasharray:7 4'}`})); });
      const indexByDate=new Map(points.map((point,index)=>[point.date,index]));
      (item.markers||[]).forEach((marker,markerIndex)=>{ const index=indexByDate.get(marker.date),benchmarkValue=benchmarkValues.get(marker.date); if(index===undefined||!Number.isFinite(benchmarkValue))return; const xx=x(index),yy=y(benchmarkValue); const kindClass=marker.kind.includes('warning')?'warning':marker.kind.includes('danger')?'danger':marker.kind==='recovery'?'recovery':'outcome'; const group=svgNode('g',{class:`svg-marker ${kindClass}${marker.marker_id===state.markerId?' selected':''}`,tabindex:'0',role:'button','aria-label':`${marker.label} ${formatDate(marker.date)}`}); group.dataset.markerId=marker.marker_id; group.append(svgNode('line',{x1:xx,y1:top,x2:xx,y2:H-bottom})); group.append(svgNode('circle',{cx:xx,cy:yy,r:5})); const text=svgNode('text',{x:xx+(markerIndex%2?5:-5),y:Math.max(18,top-7+(markerIndex%2)*15),'text-anchor':markerIndex%2?'start':'end'}); text.textContent=marker.label; group.append(text); group.addEventListener('click',()=>selectMarker(marker.marker_id)); group.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectMarker(marker.marker_id);}}); svg.append(group); });
      renderSeriesReadout(item,visible,allSeries);
    }
    function renderSeriesReadout(item,visible,allSeries) {
      const readout=document.getElementById('series-readout'); readout.replaceChildren(); const day=state.focusDate||item.dates?.anchor;
      visible.forEach(series=>{ const index=allSeries.indexOf(series); const point=(series.points||[]).find(entry=>entry.date===day)||(series.points||[]).filter(entry=>entry.date<=day&&entry.raw_value!==null).at(-1); const card=node('div','readout-card'); card.style.setProperty('--series-color',seriesColors[index]); const raw=point&&Number.isFinite(Number(point.raw_value))?`${Number(point.raw_value).toLocaleString('ja-JP',{maximumFractionDigits:3})} ${series.raw_unit||''}`:'データなし'; const indexed=point&&Number.isFinite(Number(point.indexed_value))?`指数 ${Number(point.indexed_value).toFixed(1)}`:'指数 —'; card.append(node('strong','',series.label),node('span','',`${formatDate(point?.observation_date||day)} / ${raw} / ${indexed}`)); readout.append(card); });
    }
    function renderNarrative(item) {
      const container=document.getElementById('narrative'); container.replaceChildren();
      (item.narrative||[]).forEach(entry=>{ const kind=entry.marker_id.split(':').at(-1); const className=kind==='recovery'?'recovery':kind.includes('warning')?'warning':kind.includes('danger')?'danger':'outcome'; const button=node('button',`narrative-item ${className}${entry.marker_id===state.markerId?' selected':''}`); button.type='button'; button.dataset.markerId=entry.marker_id; const time=node('time','',formatDate(entry.date)); time.dateTime=entry.date; button.append(time,node('strong','',entry.label),node('p','',entry.text)); button.addEventListener('click',()=>selectMarker(entry.marker_id)); container.append(button); });
    }
    function selectMarker(markerId) { state.markerId=markerId; const item=byId.get(state.selectedId); state.focusDate=(item.markers||[]).find(marker=>marker.marker_id===markerId)?.date||item.dates?.anchor; renderChart(item); renderNarrative(item); document.querySelector(`.narrative-item[data-marker-id="${CSS.escape(markerId)}"]`)?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'nearest',inline:'center'}); }
    function metric(icon,label,sub,value,valueClass='') { const row=node('div','metric'); const copy=node('div','metric-label',label); copy.append(node('small','',sub)); row.append(node('div','metric-icon',icon),copy,node('div',`metric-value ${valueClass}`,value)); return row; }
    function renderInspector(item) {
      const metrics=document.getElementById('metrics'); metrics.replaceChildren(metric('◫','警戒の先行','確認警戒から重大下落まで',item.evaluation.lead_time_days===null?'—':`${item.evaluation.lead_time_days}日`),metric('⌁','最大下落','記録されたピークから',percent(item.evaluation.maximum_drawdown),'danger'),metric('✓','公式系列','参照系列のカバー状態',item.evaluation.official_series_coverage==='complete'?'良好':'制約あり',item.evaluation.official_series_coverage==='complete'?'good':''),metric('◉','データ品質','欠損・遅延・改定の影響',item.evaluation.data_quality==='good'?'良好':'制約あり',item.evaluation.data_quality==='good'?'good':''));
      document.getElementById('evaluation-comment').textContent=item.evaluation.comment;
      const evidence=document.getElementById('evidence-list'); evidence.replaceChildren(); const evidenceRows=[item.classification.label,item.maturity.label,`${item.provenance.weekly_record_count}件の週次証拠`,item.split.excluded?`境界除外: ${item.split.exclusion_reason||'理由未記録'}`:`${item.split.name} split`,...comparisonSeries(item).filter(series=>!series.is_benchmark).map(series=>`${series.label}: ${series.domain_label} / ${series.source_status} / 当時の寄与証拠`)] ; evidenceRows.forEach(text=>evidence.append(node('li','',text)));
      const selection=item.context_series_selection||{}; const provenance=document.getElementById('provenance'); provenance.replaceChildren(); const rows=[['Benchmark',item.benchmark.id],['Source',item.benchmark.source],['Series selected',selection.selection_date||'—'],['Series count',String(selection.selected_context_count||0)],['Snapshot SHA',item.provenance.market_snapshot_sha256||'—'],['Policy',item.policy.version||'—'],['Records',String(item.provenance.weekly_record_count)],['Coverage',item.provenance.coverage_statuses.join(', ')||'—'],['Event ID',item.event_id]]; rows.forEach(([key,value])=>{provenance.append(node('strong','',key),node('span','',value));});
    }
    [search,typeFilter,maturityFilter].forEach(control=>control.addEventListener('input',renderList));
    recentTabs.addEventListener('wheel',event=>{
      if(recentTabs.scrollWidth<=recentTabs.clientWidth || Math.abs(event.deltaY)<=Math.abs(event.deltaX)) return;
      event.preventDefault(); recentTabs.scrollLeft+=event.deltaY;
    },{passive:false});
    document.getElementById('focus-search').addEventListener('click',()=>{document.body.classList.add('index-open');document.getElementById('index-toggle').setAttribute('aria-expanded','true');search.focus();});
    document.getElementById('focus-filter').addEventListener('click',()=>{document.body.classList.add('index-open');document.getElementById('index-toggle').setAttribute('aria-expanded','true');typeFilter.focus();});
    document.getElementById('index-toggle').addEventListener('click',event=>{const open=document.body.classList.toggle('index-open');event.currentTarget.setAttribute('aria-expanded',String(open));});
    if(state.selectedId){state.recent=[state.selectedId];resetSeriesState(byId.get(state.selectedId));renderList();renderTabs();renderEpisode();} else {document.getElementById('episode-title').textContent='表示できるエピソードがありません';}
  })();
  </script>
</body>
</html>"""
