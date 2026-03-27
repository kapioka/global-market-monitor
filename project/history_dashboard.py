from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGIME_LABELS = {
    "risk_on": "リスクオン",
    "transition": "移行局面",
    "risk_off": "リスクオフ",
    "credit_stress": "信用ストレス",
    "early_recovery": "初期回復",
    "inflation_shock": "インフレショック",
    "stagflation_warning": "スタグフレーション警戒",
    "data_unavailable": "判定保留",
}

ACTION_LABELS = {
    "buy_window": "買い検討ゾーン",
    "watch": "監視継続",
    "wait": "待機",
}

CYCLE_LABELS = {
    "upswing": "上昇局面",
    "late_cycle": "終盤局面",
    "recovery": "回復局面",
    "downswing": "下降局面",
    "insufficient_data": "データ不足",
}


DASHBOARD_TEMPLATE = """<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Market History Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #eef3f8;
      --panel: rgba(255,255,255,0.94);
      --ink: #102033;
      --muted: #5d6b7c;
      --line: rgba(125,145,166,0.22);
      --accent: #5f7c92;
      --accent-strong: #476477;
      --accent-soft: rgba(95,124,146,0.12);
      --state-risk-on: #3f7d5e;
      --state-transition: #b38a3a;
      --state-risk-off: #a24f4b;
      --state-credit: #7d5d49;
      --state-inflation: #c56d3d;
      --state-recovery: #5f8792;
      --state-neutral: #52606d;
      --shadow: 0 18px 42px rgba(16,32,51,0.08);
      --shadow-soft: 0 10px 24px rgba(16,32,51,0.05);
      --radius-xl: 28px;
      --radius-lg: 22px;
      --radius-md: 18px;
      --radius-sm: 14px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: 'Yu Gothic UI', 'Hiragino Sans', sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(255,255,255,0.98) 0%, rgba(238,243,248,0.98) 46%, rgba(227,235,244,1) 100%),
        linear-gradient(180deg, #f7faff 0%, #eaf0f7 100%);
    }
    .dashboard-shell {
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px 18px 56px;
      container-type: inline-size;
    }
    .hero,
    .panel,
    .timeline-toolbar,
    .metric,
    .map-node,
    .detail-box,
    details.disclosure,
    .focus-card,
    .focus-note {
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.9) 0%, rgba(250,246,240,0.95) 100%);
      box-shadow: var(--shadow-soft);
    }
    .hero {
      padding: 22px 24px;
      border-radius: var(--radius-xl);
      box-shadow: none;
      backdrop-filter: blur(10px);
    }
    .eyebrow {
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .04em;
    }
    h1 {
      margin: 0;
      font-size: clamp(26px, 4.4vw, 38px);
      line-height: 1.1;
    }
    .hero-copy,
    .hero-subcopy,
    .section-copy,
    .detail-copy,
    .focus-note,
    .footer-note,
    .guide-body,
    .microcopy,
    .detail-subtitle,
    .detail-box .k,
    .metric h2,
    .list-table th {
      color: var(--muted);
    }
    .hero-copy,
    .hero-subcopy,
    .section-copy,
    .detail-copy,
    .focus-note,
    .footer-note,
    .guide-body { line-height: 1.75; }
    .hero-subcopy {
      margin: 4px 0 0;
      max-width: 1220px;
      font-size: 14px;
    }
    .focus-card,
    .panel { border-radius: var(--radius-xl); }
    .focus-card {
      width: min(250px, 100%);
      padding: 10px 12px;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(248,243,236,0.98) 100%);
    }
    .focus-card .label { font-size: 11px; font-weight: 700; color: var(--muted); }
    .focus-card .value { margin-top: 4px; font-size: clamp(14px, 1.5vw, 18px); font-weight: 800; line-height: 1.35; word-break: break-word; }
    .stack { display: grid; gap: 18px; margin-top: 18px; }
    .panel { padding: 22px; }
    .panel h2 { margin: 0; font-size: 22px; }
    .section-copy { margin: 10px 0 0; font-size: 14px; }
    .workspace-title-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: start;
      margin-top: 12px;
    }
    .workspace-title-block {
      display: grid;
      gap: 8px;
      align-content: start;
    }
    .workspace-copy {
      margin: 0;
      max-width: none;
      font-size: 14px;
      color: var(--muted);
      line-height: 1.7;
    }
    .workspace-status-strip {
      margin-top: 18px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .status-chip {
      min-width: 180px;
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
      display: grid;
      gap: 4px;
      align-content: start;
    }
    .status-chip .k {
      font-size: 11px;
      font-weight: 700;
      color: var(--muted);
      letter-spacing: .03em;
      text-transform: uppercase;
    }
    .status-chip .v {
      font-size: 15px;
      font-weight: 800;
      line-height: 1.35;
      color: var(--ink);
    }
    .timeline-side {
      display: grid;
      gap: 12px;
      width: min(780px, 100%);
      justify-items: end;
    }
    .timeline-calibration {
      width: 100%;
      max-width: 780px;
    }
    .timeline-calibration {
      display: grid;
      gap: 8px;
      justify-items: stretch;
    }
    .compare-strip {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      width: 100%;
    }
    .compare-strip.compact .compare-card {
      min-height: 88px;
      padding: 10px 12px;
    }
    .compare-strip.compact.triple {
      grid-template-columns: 1.08fr 1fr 1fr;
      align-items: stretch;
    }
    .compare-strip.compact .focus-card-inline {
      min-height: 88px;
      padding: 10px 12px;
    }
    .focus-card-inline {
      width: 100%;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(248,243,236,0.98) 100%);
      box-shadow: var(--shadow-soft);
      display: grid;
      align-content: start;
    }
    .focus-card-inline .label {
      font-size: 11px;
      font-weight: 700;
      color: var(--muted);
      line-height: 1.35;
    }
    .focus-card-inline .value {
      margin-top: 4px;
      font-size: clamp(16px, 1.9vw, 20px);
      font-weight: 800;
      line-height: 1.35;
      word-break: break-word;
      color: #243b53;
    }
    .compare-card {
      padding: 12px;
      min-height: 108px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
      display: grid;
      align-content: start;
    }
    .compare-card .label {
      font-size: 13px;
      font-weight: 400;
      line-height: 1.35;
      color: var(--ink);
    }
    .compare-card strong {
      display: block;
      margin-top: 4px;
      font-size: 22px;
      font-weight: 800;
      line-height: 1.15;
      color: #243b53;
    }
    .compare-card small {
      display: block;
      margin-top: 4px;
      font-size: 13px;
      color: var(--muted);
      line-height: 1.5;
    }
    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 10px;
    }
    .badge-row.is-empty { display: none; }
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .01em;
    }
    .badge-neutral { background: rgba(122,92,77,0.12); color: #6b4d3f; }
    .badge-credit { background: color-mix(in srgb, var(--state-credit) 12%, white); color: var(--state-credit); }
    .badge-inflation { background: color-mix(in srgb, var(--state-inflation) 12%, white); color: var(--state-inflation); }
    .badge-relief { background: color-mix(in srgb, var(--state-recovery) 12%, white); color: var(--state-recovery); }
    .risk-stage-inline { font-weight: 800; }
    .risk-stage-inline.caution { color: #b7791f; }
    .risk-stage-inline.danger { color: #c05621; }
    .risk-stage-inline.extreme { color: #c53030; }
    .severity-inline { font-weight: 800; }
    .severity-inline.caution { color: #b7791f; }
    .severity-inline.danger { color: #c05621; }
    .severity-inline.extreme { color: #c53030; }
    .alert-stack { display: grid; gap: 10px; margin-top: 12px; }
    .alert-card {
      padding: 12px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.78);
    }
    .alert-card h4 { margin: 0; font-size: 14px; }
    .alert-card p { margin: 8px 0 0; font-size: 13px; color: var(--muted); line-height: 1.6; }
    .alert-card.high { border-color: rgba(156,66,33,0.32); }
    .alert-card.moderate { border-color: rgba(183,121,31,0.28); }
    .alert-card.low { border-color: rgba(82,96,109,0.2); }
    .timeline-panel { display: grid; gap: 18px; }
    .timeline-header {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: start;
    }
    .timeline-lead {
      display: grid;
      gap: 8px;
      align-content: start;
    }
    .timeline-lead h2 {
      margin: 0;
      font-size: 14px;
      font-weight: 700;
      color: var(--muted);
      line-height: 1.4;
    }
    .timeline-lead .section-copy {
      margin-top: 0;
    }
    .chart-card {
      position: relative;
      padding: 18px;
      border-radius: var(--radius-lg);
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(247,250,253,0.98) 100%);
      overflow: hidden;
    }
    .legend { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; font-size: 13px; }
    .legend span::before {
      content: '';
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      margin-right: 6px;
      vertical-align: middle;
    }
    .legend .on::before { background: var(--state-risk-on); }
    .legend .transition::before { background: var(--state-transition); }
    .legend .off::before { background: var(--state-risk-off); }
    .legend .credit::before { background: var(--state-credit); }
    .legend .inflation::before { background: var(--state-inflation); }
    .legend .recovery::before { background: var(--state-recovery); }
    svg { width: 100%; height: auto; display: block; }
    .chart-shell { transition: transform 220ms ease, opacity 220ms ease; }
    .chart-shell.is-refreshing { opacity: .8; transform: translateY(2px); }
    .timeline-toolbar {
      display: grid;
      grid-template-columns: auto minmax(0,1fr) auto auto;
      gap: 12px;
      align-items: center;
      padding: 14px 16px;
      border-radius: var(--radius-lg);
    }
    .controls { display: inline-flex; gap: 10px; flex-wrap: wrap; }
    button,
    .timeline-toolbar input[type=\"range\"] { accent-color: var(--accent); }
    button {
      border: 0;
      padding: 10px 16px;
      border-radius: 999px;
      background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 82%, white) 0%, var(--accent-strong) 100%);
      color: #fff;
      font-weight: 700;
      cursor: pointer;
      transition: transform 180ms ease, box-shadow 180ms ease;
      box-shadow: 0 10px 20px rgba(71,100,119,0.18);
    }
    button.secondary { background: linear-gradient(180deg, #e9ecef 0%, #dce4eb 100%); color: #243b53; box-shadow: none; }
    button:hover,
    button:focus-visible,
    .map-node:hover,
    .map-node:focus-visible { transform: translateY(-1px) scale(1.01); }
    button:focus-visible,
    .map-node:focus-visible,
    summary:focus-visible,
    input:focus-visible { outline: 2px solid rgba(122,92,77,0.45); outline-offset: 2px; }
    .summary-grid { display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 12px; }
    .summary-layout {
      display: grid;
      grid-template-columns: minmax(0, 2fr) minmax(240px, 0.92fr);
      gap: 14px;
      align-items: stretch;
    }
    .primary-metric {
      padding: 16px;
      border-radius: var(--radius-lg);
      border: 1px solid rgba(125,145,166,0.14);
      background: rgba(255,255,255,0.78);
      box-shadow: none;
      display: grid;
      gap: 8px;
      position: relative;
      overflow: hidden;
    }
    .primary-metric::after {
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(37,99,235,0.05), transparent 48%);
      pointer-events: none;
    }
    .primary-head {
      display: grid;
      gap: 2px;
      position: relative;
      z-index: 1;
    }
    .primary-head h3 { margin: 0; font-size: 14px; color: var(--muted); }
    .primary-signal {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: minmax(0, 1.32fr) minmax(200px, 0.78fr);
      gap: 12px;
      align-items: start;
      margin-top: 0;
    }
    .primary-meaning {
      display: grid;
      gap: 6px;
      align-content: start;
    }
    .primary-meaning .badge-row {
      margin-top: -6px;
      margin-bottom: -2px;
      justify-content: flex-start;
      min-height: 18px;
    }
    .primary-regime {
      font-size: clamp(28px, 4.4vw, 42px);
      font-weight: 800;
      line-height: 1.08;
      color: #243b53;
      word-break: break-word;
    }
    .primary-regime-copy {
      font-size: 13px;
      color: var(--muted);
      line-height: 1.55;
      max-width: none;
      opacity: .88;
    }
    .primary-score-side {
      display: grid;
      gap: 0;
      align-content: start;
      justify-items: stretch;
    }
    .primary-score-block {
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid rgba(125,145,166,0.14);
      background: rgba(255,255,255,0.66);
      align-self: start;
      display: grid;
      align-content: center;
      min-height: 108px;
    }
    .primary-score-block .k { font-size: 12px; color: var(--muted); font-weight: 700; }
    .primary-score-block .v { margin-top: 4px; font-size: clamp(28px, 4vw, 38px); font-weight: 800; line-height: 1.08; color: #102a43; }
    .primary-meta {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: -2px;
    }
    .support-column {
      display: grid;
      grid-template-rows: repeat(3, auto);
      gap: 10px;
      align-content: start;
    }
    .mini-stat {
      display: grid;
      align-content: center;
      gap: 3px;
      padding: 10px 0 0;
      min-height: 0;
      border-radius: 0;
      border: 0;
      border-top: 1px solid rgba(125,145,166,0.18);
      background: transparent;
    }
    .mini-stat .k { font-size: 12px; color: var(--muted); font-weight: 700; }
    .mini-stat .v { margin-top: 0; font-size: 24px; font-weight: 800; line-height: 1.12; color: #243b53; }
    .support-metric {
      min-height: 0;
      display: grid;
      align-content: start;
      padding: 10px 14px;
    }
    .support-metric .sub strong { color: #243b53; }
    .delta-positive { color: #2f855a; }
    .delta-negative { color: #c53030; }
    .delta-neutral { color: #7a5c4d; }
    .metric {
      position: relative;
      padding: 16px;
      border-radius: var(--radius-md);
      transition: transform 220ms ease, box-shadow 220ms ease, border-color 220ms ease;
      overflow: hidden;
      background: rgba(255,255,255,0.72);
    }
    .metric::after {
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, var(--accent-soft), transparent 42%);
      opacity: 0;
      transition: opacity 220ms ease;
      pointer-events: none;
    }
    .metric[data-flash=\"true\"] { border-color: rgba(95,124,146,0.28); box-shadow: 0 16px 30px rgba(95,124,146,0.12); transform: translateY(-2px); }
    .metric[data-flash=\"true\"]::after { opacity: 1; }
    .metric h2 { margin: 0 0 8px; font-size: 13px; }
    .metric .value { font-size: clamp(22px, 3vw, 28px); font-weight: 800; line-height: 1.18; }
    .metric .sub { margin-top: 8px; font-size: 12px; color: var(--muted); line-height: 1.5; }
    .map-grid { display: grid; grid-template-columns: minmax(500px,0.9fr) minmax(480px,1.1fr); gap: 16px; align-items: start; }
    .relation-shell { display: grid; gap: 14px; }
    .relation-canvas {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      border-radius: var(--radius-lg);
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.88) 0%, rgba(244,248,253,0.98) 100%);
      padding: 16px;
    }
    .relation-row {
      display: contents;
    }
    .relation-group {
      display: grid;
      grid-template-rows: auto auto 1fr;
      gap: 6px;
      padding-block: 12px;
      padding-inline: 0;
      border-radius: 18px;
      border: 1px solid rgba(125,145,166,0.18);
      background: rgba(255,255,255,0.58);
      align-content: start;
    }
    .relation-group.full-span {
      grid-column: 1 / -1;
    }
    .relation-group.candidates-span {
      padding-inline: 0;
      display: grid;
      grid-template-columns: subgrid;
    }
    .relation-group.core-span {
      padding-inline: 0;
    }
    .relation-group.col-1,
    .relation-group.col-2,
    .relation-group.col-3 {
      padding-inline: 0;
    }
    .relation-group.core-span .relation-group-title,
    .relation-group.core-span .relation-group-copy,
    .relation-group.col-1 .relation-group-title,
    .relation-group.col-1 .relation-group-copy,
    .relation-group.col-2 .relation-group-title,
    .relation-group.col-2 .relation-group-copy,
    .relation-group.col-3 .relation-group-title,
    .relation-group.col-3 .relation-group-copy,
    .relation-group.candidates-span .relation-group-title,
    .relation-group.candidates-span .relation-group-copy {
      padding-inline: 12px;
      grid-column: 1 / -1;
    }
    .relation-group.core-span {
      grid-column: 1 / span 2;
    }
    .relation-group.col-1 {
      grid-column: 1;
    }
    .relation-group.col-2 {
      grid-column: 2;
    }
    .relation-group.col-3 {
      grid-column: 3;
    }
    .relation-group-title {
      font-size: 11px;
      font-weight: 700;
      color: var(--muted);
      letter-spacing: .03em;
      text-transform: uppercase;
      min-height: 14px;
    }
    .relation-group-copy {
      margin: -2px 0 0;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.5;
      min-height: 24px;
    }
    .node-grid {
      display: grid;
      gap: 10px;
      align-items: stretch;
    }
    .node-grid.core {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .node-grid.single {
      grid-template-columns: 1fr;
    }
    .node-grid.single.two-rows {
      grid-template-columns: 1fr;
      grid-template-rows: repeat(2, minmax(116px, 1fr));
    }
    .node-grid.triple {
      grid-template-columns: repeat(3, minmax(180px, 1fr));
      align-items: stretch;
      gap: 14px;
      grid-auto-rows: 1fr;
    }
    .node-grid.candidate-band {
      display: contents;
    }
    .map-node {
      position: static;
      width: calc(100% - 14px);
      min-height: 92px;
      padding: 12px 14px;
      border-radius: var(--radius-md);
      text-align: left;
      cursor: pointer;
      color: var(--ink);
      border: 1px solid rgba(125,145,166,0.18);
      background: rgba(255,255,255,0.78);
      display: grid;
      align-content: start;
      justify-self: center;
      transition: transform 220ms ease, box-shadow 220ms ease, border-color 220ms ease, background 220ms ease, opacity 220ms ease;
    }
    .map-node .label { font-size: 12px; color: var(--muted); }
    .map-node .strong { margin-top: 6px; font-size: 19px; font-weight: 800; line-height: 1.24; color: #243b53; }
    .map-node .mini { margin-top: 6px; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .map-node.placeholder {
      visibility: hidden;
      pointer-events: none;
      min-height: 110px;
    }
    .map-node[aria-pressed=\"true\"] { border-color: rgba(95,124,146,0.30); background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(243,247,249,0.98) 100%); box-shadow: 0 16px 30px rgba(95,124,146,0.12); }
    .map-node.is-dim { opacity: .55; filter: saturate(.82); box-shadow: 0 8px 16px rgba(29,41,53,0.04); }
    .map-node.is-active { border-color: rgba(95,124,146,0.34); box-shadow: 0 18px 32px rgba(95,124,146,0.14); }
    .map-node.candidates,
    .map-node.recovery-candidates,
    .map-node.regime-leading-candidates {
      min-height: 0;
      height: 100%;
      align-self: stretch;
      grid-template-rows: auto auto 1fr;
      gap: 6px;
      padding: 14px 16px;
    }
    .map-node.candidates .label,
    .map-node.recovery-candidates .label,
    .map-node.regime-leading-candidates .label {
      font-size: 12px;
      line-height: 1.35;
    }
    .map-node.candidates .strong,
    .map-node.recovery-candidates .strong,
    .map-node.regime-leading-candidates .strong {
      margin-top: 0;
      font-size: 19px;
      line-height: 1.24;
    }
    .map-node.candidates .mini,
    .map-node.recovery-candidates .mini,
    .map-node.regime-leading-candidates .mini {
      font-size: 11px;
      line-height: 1.45;
      writing-mode: horizontal-tb;
      word-break: normal;
      overflow-wrap: anywhere;
      overflow: visible;
      text-overflow: clip;
      margin-top: 0;
    }
    .detail-panel { display: grid; gap: 0; align-content: start; align-self: stretch; background: rgba(255,255,255,0.84); }
    .detail-head { display: block; }
    .detail-title {
      font-size: 22px;
      font-weight: 800;
      line-height: 1.1;
      margin: 0;
    }
    .detail-subtitle {
      font-size: 14px;
      line-height: 1.75;
      min-height: 0;
      margin-top: 10px;
    }
    .detail-copy {
      min-height: calc(1.75em * 2);
      align-content: start;
      margin-top: 10px;
      margin-bottom: calc(1.75em * 0.5);
    }
    .detail-boxes {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      align-items: stretch;
    }
    .detail-box {
      padding: 12px;
      border-radius: var(--radius-sm);
      min-height: 104px;
      height: 100%;
      display: grid;
      align-content: start;
      grid-template-rows: auto 1fr;
    }
    .detail-box .v { margin-top: 6px; font-size: 18px; font-weight: 700; line-height: 1.3; }
    .detail-panel .disclosure { margin-top: 12px; }
    details.disclosure { border-radius: var(--radius-md); overflow: clip; }
    details.disclosure summary { list-style: none; cursor: pointer; padding: 12px 14px; font-weight: 700; user-select: none; }
    details.disclosure summary::-webkit-details-marker { display: none; }
    .table-inner { padding: 0 14px 14px; }
    .list-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .list-table th,
    .list-table td { padding: 10px 6px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; line-height: 1.55; }
    .list-table th { font-size: 12px; font-weight: 700; }
    .list-table td small { display: block; color: var(--muted); margin-top: 4px; }
    .detail-empty { padding: 0 14px 14px; color: var(--muted); font-size: 13px; }
    .sector-visual { display: grid; grid-template-columns: minmax(220px, 280px) 1fr; gap: 14px; align-items: start; }
    .sector-visual-card { border: 1px solid var(--line); border-radius: 16px; padding: 12px; background: linear-gradient(180deg, rgba(255,255,255,0.9) 0%, rgba(250,246,240,0.95) 100%); }
    .sector-visual-card h4 { margin: 0 0 8px; font-size: 14px; }
    .sector-visual-card p { margin: 10px 0 0; font-size: 12px; color: var(--muted); line-height: 1.6; }
    .sector-visual svg { width: 100%; height: auto; display: block; }
    .guide-body { padding: 0 14px 14px; font-size: 13px; }
    .footer-note { font-size: 13px; }
    .run-alert {
      margin-top: 14px;
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid rgba(197, 48, 48, 0.22);
      background: linear-gradient(180deg, rgba(254,226,226,0.96) 0%, rgba(254,242,242,0.98) 100%);
      color: #9b2c2c;
      font-weight: 800;
      line-height: 1.6;
    }
    .current-run-layout {
      display: grid;
      grid-template-columns: minmax(320px, 1.05fr) minmax(0, 1.95fr);
      gap: 14px;
      align-items: start;
    }
    .current-run-hero {
      padding: 16px 18px;
      border-radius: var(--radius-lg);
      border: 1px solid rgba(37,99,235,0.12);
      background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(244,248,253,0.98) 100%);
      box-shadow: none;
      display: grid;
      gap: 8px;
    }
    .current-run-hero .eyebrow-note { font-size: 12px; color: var(--muted); font-weight: 700; }
    .current-run-hero .hero-value { font-size: clamp(24px, 4vw, 34px); font-weight: 800; line-height: 1.12; color: #102a43; }
    .current-run-status {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      align-content: start;
    }
    .current-run-status .metric {
      min-height: 0;
      padding: 14px 16px;
      border-radius: 16px;
      box-shadow: none;
    }
    .current-run-status .metric h2 {
      margin-bottom: 6px;
    }
    .run-alert.is-hidden { display: none; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
    @container (max-width: 1180px) {
      .workspace-title-row { grid-template-columns: 1fr; }
      .summary-grid { grid-template-columns: repeat(3, minmax(0,1fr)); }
      .summary-layout { grid-template-columns: minmax(0, 1.45fr) minmax(220px, 1fr); }
      .primary-signal { grid-template-columns: 1fr; }
      .primary-meta { grid-template-columns: repeat(3, minmax(0,1fr)); }
      .map-grid { grid-template-columns: 1fr; }
      .timeline-header { grid-template-columns: 1fr; }
      .timeline-toolbar { grid-template-columns: 1fr; }
      .timeline-side { width: 100%; justify-items: stretch; }
      .sector-visual { grid-template-columns: 1fr; }
      .current-run-layout { grid-template-columns: 1fr; }
      .current-run-status { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .detail-boxes { grid-template-columns: repeat(2, minmax(0,1fr)); }
    }
    @container (max-width: 760px) {
      .dashboard-shell { padding-inline: 12px; }
      .hero, .panel { padding: 18px; }
      .summary-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .summary-layout { grid-template-columns: 1fr; }
      .primary-meta { grid-template-columns: 1fr; }
      .relation-canvas { grid-template-columns: 1fr; }
      .relation-group.core-span,
      .relation-group.col-1,
      .relation-group.col-2,
      .relation-group.col-3,
      .relation-group.full-span { grid-column: 1; }
      .node-grid.core,
      .node-grid.triple { grid-template-columns: 1fr; }
      .current-run-status { grid-template-columns: 1fr; }
      .compare-strip.compact.triple { grid-template-columns: 1fr; }
      .detail-boxes { grid-template-columns: 1fr; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
    }
  </style>
</head>
<body>
  <main class=\"dashboard-shell\">
    <section class=\"hero\">
      <div class=\"workspace-title-row\">
        <div class=\"workspace-title-block\">
          <h1>市場状態と投資判断を確認するダッシュボード</h1>
          <p class=\"workspace-copy\">履歴ブラウズと今回の実行結果を分離し、時間差による見え方の違いを混同せずに判断できるようにした運用画面です。</p>
        </div>
        <div class=\"focus-card\">
          <div class=\"label\">画面リンク</div>
          <div class=\"value\"><a href=\"report.html\">最新レポートを見る</a></div>
        </div>
      </div>
    </section>

    <div class=\"stack\">
      <section class=\"panel timeline-panel\" aria-labelledby=\"timelineHeading\">
        <div class=\"timeline-header\">
          <div class=\"timeline-lead\">
            <h2 id=\"timelineHeading\">過去履歴ブラウズ</h2>
            <p class=\"section-copy\">ここから下は、過去に保存された履歴だけを使うビューです。最新の実行結果とは別枠なので、上段と値が違う場合は過去時点との差です。</p>
          </div>
          <div class=\"timeline-side\">
            <div class=\"timeline-calibration\">
              <div class=\"label\" style=\"font-size:14px;font-weight:700;color:#5c6976;\">校正基準の見方</div>
              <p id=\"calibrationNote\" class=\"section-copy\" style=\"margin-top:0;\">日次圧縮を主基準にし、全履歴は参考として残します。</p>
              <div class=\"compare-strip compact triple\" style=\"margin-top:10px;\">
                <div class=\"focus-card-inline\">
                  <div class=\"label\">履歴で現在選択中の時点</div>
                  <output id=\"focusTimestamp\" class=\"value\">履歴なし</output>
                </div>
                <div class=\"compare-card\">
                  <div class=\"label\">主基準: daily_latest</div>
                  <strong id=\"calibrationPrimaryCount\">0件</strong>
                  <small>同日の再生成は最新1件へ圧縮</small>
                </div>
                <div class=\"compare-card\">
                  <div class=\"label\">参考: all_history</div>
                  <strong id=\"calibrationSecondaryCount\">0件</strong>
                  <small>重複を含む全履歴の母数</small>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class=\"chart-card\">
          <div class=\"legend\"><span class=\"on\">リスクオン</span><span class=\"transition\">移行局面</span><span class=\"off\">リスクオフ</span><span class=\"credit\">信用ストレス</span><span class=\"inflation\">インフレ系</span><span class=\"recovery\">初期回復</span></div>
          <div id=\"chartShell\" class=\"chart-shell\"><svg id=\"scoreChart\" viewBox=\"0 0 900 300\" role=\"img\" aria-label=\"合成スコア推移チャート\"></svg></div>
        </div>
        <div class=\"timeline-toolbar\" aria-label=\"履歴操作\">
          <div class=\"controls\"><button id=\"playButton\" type=\"button\">再生</button><button id=\"latestButton\" class=\"secondary\" type=\"button\">最新へ</button></div>
          <label class=\"sr-only\" for=\"timeline\">履歴シークバー</label>
          <input id=\"timeline\" type=\"range\" min=\"0\" max=\"0\" value=\"0\" />
          <output id=\"timelineCount\" class=\"microcopy\">0件</output>
          <output id=\"timestampLabel\" class=\"microcopy\">履歴なし</output>
        </div>
        <div class=\"summary-layout\">
          <article class=\"primary-metric\" data-metric=\"primary\">
            <div class=\"primary-head\">
              <div>
                <h3>最重要シグナル</h3>
                <div id=\"metricRegimeSub\" class=\"sub\">地合いの大枠</div>
              </div>
            </div>
            <div class=\"primary-signal\">
              <div class=\"primary-meaning\">
                <div id=\"metricRegimeBadges\" class=\"badge-row is-empty\"></div>
                <div id=\"metricRegime\" class=\"primary-regime\">-</div>
                <div id=\"metricRegimeCopy\" class=\"primary-regime-copy\">現在の地合いを最優先で読む領域です。</div>
              </div>
              <div class=\"primary-score-side\">
                <div class=\"primary-score-block\">
                  <div class=\"k\">合成スコア</div>
                  <div id=\"metricScore\" class=\"v\">-</div>
                  <div id=\"metricScoreSub\" class=\"sub\">0 から 1 の範囲で高いほど条件が良好</div>
                </div>
              </div>
            </div>
            <div class=\"primary-meta\">
              <div class=\"mini-stat\"><div class=\"k\">前回比</div><div id=\"metricScoreDelta\" class=\"v\">-</div></div>
              <div class=\"mini-stat\"><div class=\"k\">判定用スコア</div><div id=\"metricAdjusted\" class=\"v\">-</div></div>
              <div class=\"mini-stat\"><div class=\"k\">減点</div><div id=\"metricPenalty\" class=\"v\">-</div></div>
            </div>
          </article>
          <div class=\"support-column\">
            <article class=\"metric support-metric\" data-metric=\"cycle\"><h2>サイクル判定</h2><div id=\"metricCycle\" class=\"value\">-</div><div id=\"metricCycleSub\" class=\"sub\">位相角 - 度</div></article>
            <article class=\"metric support-metric\" data-metric=\"spot\"><h2>スポット判断</h2><div id=\"metricSpot\" class=\"value\">-</div><div id=\"metricSpotSub\" class=\"sub\">二段下げリスク -</div></article>
            <article class=\"metric support-metric\" data-metric=\"availability\"><h2>データ健全性</h2><div id=\"metricAvailability\" class=\"value\">-</div><div id=\"metricAvailabilitySub\" class=\"sub\">代替取得や未取得の件数</div></article>
          </div>
        </div>
        <p class=\"footer-note\">グラフとシークを同じ枠にまとめているので、時間を動かす操作と結果の変化を同じ視野内で追えます。</p>
      </section>

      <div class=\"map-grid\">
        <section class=\"panel relation-shell\" aria-labelledby=\"relationHeading\">
          <div>
            <h2 id=\"relationHeading\">関係マップ</h2>
            <p class=\"section-copy\">全体判断、補助ドライバー、候補層を分けた操作パネルです。気になる項目を押すと、右側の解釈と明細が固定で切り替わります。</p>
          </div>
          <div class=\"relation-canvas\">
            <div class="relation-row core">
              <div class="relation-group core-span">
                <div class="relation-group-title">Core Signal</div>
                <p class="relation-group-copy">まず全体判断の軸になる 2 項目から確認します。</p>
                <div class="node-grid core">
                  <button class="map-node regime" data-node="regime" type="button" aria-pressed="true"><div class="label">市場レジーム</div><div id="nodeRegime" class="strong">-</div><div id="nodeRegimeSub" class="mini">地合いの大枠</div></button>
                  <button class="map-node score" data-node="score" type="button" aria-pressed="false"><div class="label">合成スコア</div><div id="nodeScore" class="strong">-</div><div id="nodeScoreSub" class="mini">押し目条件のまとまり</div></button>
                </div>
              </div>
            </div>
            <div class="relation-row drivers">
              <div class="relation-group col-1">
                <div class="relation-group-title">Timing</div>
                <p class="relation-group-copy">入るか待つかの判断に効く時間軸の補助です。</p>
                <div class="node-grid single two-rows">
                  <button class="map-node cycle" data-node="cycle" type="button" aria-pressed="false"><div class="label">サイクル判定</div><div id="nodeCycle" class="strong">-</div><div id="nodeCycleSub" class="mini">位相角 -</div></button>
                  <button class="map-node spot" data-node="spot" type="button" aria-pressed="false"><div class="label">スポット判断</div><div id="nodeSpot" class="strong">-</div><div id="nodeSpotSub" class="mini">二段下げリスク -</div></button>
                </div>
              </div>
              <div class="relation-group col-2">
                <div class="relation-group-title">Flow</div>
                <p class="relation-group-copy">資金が向かっている先と比較上位を確認します。</p>
                <div class="node-grid single two-rows">
                  <button class="map-node sector" data-node="sector" type="button" aria-pressed="false"><div class="label">先導セクター</div><div id="nodeSector" class="strong">-</div><div id="nodeSectorSub" class="mini">資金の向かい先</div></button>
                  <button class="map-node asset" data-node="asset" type="button" aria-pressed="false"><div class="label">上位資産クラス</div><div id="nodeAsset" class="strong">-</div><div id="nodeAssetSub" class="mini">資産比較の先頭</div></button>
                </div>
              </div>
              <div class="relation-group col-3">
                <div class="relation-group-title">Risk</div>
                <p class="relation-group-copy">警告の発火状況を市場判断と切り分けて確認します。</p>
                <div class="node-grid single two-rows">
                  <button class="map-node alerts" data-node="alerts" type="button" aria-pressed="false"><div class="label">警告レイヤー</div><div id="nodeAlerts" class="strong">-</div><div id="nodeAlertsSub" class="mini">市場と生活の警戒灯</div></button>
                  <div class="map-node placeholder" aria-hidden="true"></div>
                </div>
              </div>
            </div>
            <div class="relation-row candidates">
              <div class="relation-group full-span candidates-span">
                <div class="relation-group-title">Candidates</div>
                <p class="relation-group-copy">今の強さ、反転初期、次レジーム適性の 3 系統で候補を分けています。</p>
                <div class="node-grid candidate-band">
                  <button class="map-node candidates" data-node="candidates" type="button" aria-pressed="false"><div class="label">追随候補</div><div id="nodeCandidates" class="strong">-</div><div id="nodeCandidatesSub" class="mini">今強い流れを追う候補</div></button>
                  <button class="map-node recovery-candidates" data-node="recovery_candidates" type="button" aria-pressed="false"><div class="label">先回り候補</div><div id="nodeRecoveryCandidates" class="strong">-</div><div id="nodeRecoveryCandidatesSub" class="mini">底打ち初期を狙う候補</div></button>
                  <button class="map-node regime-leading-candidates" data-node="regime_leading_candidates" type="button" aria-pressed="false"><div class="label">レジーム先回り</div><div id="nodeRegimeLeadingCandidates" class="strong">-</div><div id="nodeRegimeLeadingCandidatesSub" class="mini">次の地合いで効きやすい候補</div></button>
                </div>
              </div>
            </div>
          </div>
          <details class=\"disclosure\"><summary>このパネルの読み方</summary><div class=\"guide-body\">まず Core Signal で全体判断を確認し、次に Timing / Flow / Risk の補助要素へ進みます。候補群は最後に見る前提なので、候補の強さだけで全体判断を上書きしないように分けています。</div></details>
        </section>

        <aside class=\"panel detail-panel\" aria-live=\"polite\">
          <div class=\"detail-head\"><div><div id=\"detailTitle\" class=\"detail-title\">詳細</div><div id=\"detailSubtitle\" class=\"detail-subtitle\">ノードを選択すると解説が切り替わります。</div></div></div>
          <div id=\"detailCopy\" class=\"detail-copy\">履歴がある場合、関係マップのノードごとに解釈を確認できます。</div>
          <div id=\"detailBoxes\" class=\"detail-boxes\"></div>
          <details id=\"detailTableDisclosure\" class=\"disclosure\" open><summary id=\"detailTableSummary\">明細を表示</summary><div id=\"detailTableWrap\" class=\"table-inner\"></div></details>
        </aside>
      </div>
    </div>

    <section class=\"panel timeline-panel\" aria-labelledby=\"currentRunHeading\" style=\"margin-top:18px;\">
      <div class=\"timeline-header\">
        <div>
          <h2 id=\"currentRunHeading\">今回の実行結果</h2>
          <p class=\"section-copy\">ここは最新の実行結果だけを表示します。履歴再生や過去成功データは混ざりません。</p>
        </div>
        <div class=\"focus-card\"><div class=\"label\">参照元</div><output id=\"currentRunSourceFile\" class=\"value\">最新の実行結果</output></div>
      </div>
      <div id=\"currentRunAlert\" class=\"run-alert is-hidden\">今回の実行は live 取得ではありません。過去履歴に live 成功が残っていても、それは今回分ではありません。</div>
      <div class=\"current-run-layout\">
        <article class=\"current-run-hero\">
          <div class=\"eyebrow-note\">今回の実行サマリー</div>
          <div id=\"currentRunTimestamp\" class=\"hero-value\">-</div>
          <div id=\"currentRunDataSource\" class=\"value\">-</div>
          <div id=\"currentRunDataSourceSub\" class=\"sub\">今回の取得方式</div>
          <p class=\"section-copy\" style=\"margin:2px 0 0;\">判断に使うときはこの枠を優先し、上の履歴ビューは比較用として扱います。</p>
        </article>
        <div class=\"current-run-status\">
          <article class=\"metric\"><h2>取得成功</h2><div id=\"currentRunOkCount\" class=\"value\">-</div><div class=\"sub\">今回の実行だけの成功数</div></article>
          <article class=\"metric\"><h2>代替取得</h2><div id=\"currentRunFallbackCount\" class=\"value\">-</div><div class=\"sub\">代替ティッカーやサンプル代替</div></article>
          <article class=\"metric\"><h2>未取得</h2><div id=\"currentRunUnavailableCount\" class=\"value\">-</div><div class=\"sub\">今回の実行だけの未取得数</div></article>
          <article class=\"metric\"><h2>警告件数</h2><div id=\"currentRunWarningCount\" class=\"value\">-</div><div class=\"sub\">今回の実行だけの警告数</div></article>
        </div>
      </div>
      <details class=\"disclosure\"><summary>今回の実行の取得状況を開く</summary><div id=\"currentRunTableWrap\" class=\"table-inner\"></div></details>
    </section>
  </main>

  <script>
    const dashboardPayload = __PAYLOAD__;
    const dashboardData = dashboardPayload.history || [];
    const currentRun = dashboardPayload.current_run;
    const dashboardMeta = dashboardPayload.meta || {
      history_count: dashboardData.length,
      daily_latest_count: dashboardData.length,
      primary_basis: 'daily_latest',
      primary_label: '主基準: daily_latest',
      secondary_label: '参考: all_history'
    };
    const regimeColors = {
      risk_on: '#3f7d5e',
      transition: '#b38a3a',
      risk_off: '#a24f4b',
      credit_stress: '#7d5d49',
      inflation_shock: '#c56d3d',
      stagflation_warning: '#b15b42',
      data_unavailable: '#52606d',
      early_recovery: '#5f8792',
      default: '#7a5c4d'
    };
    const detailState = { currentIndex: Math.max(dashboardData.length - 1, 0), selectedNode: 'regime', timer: null };
    const chartState = { points: [], marker: null };

    function updateRelationLines() {
      const canvas = document.querySelector('.relation-canvas');
      const scoreNode = document.querySelector('.map-node.score');
      const svg = document.querySelector('.relation-svg');
      if (!canvas || !scoreNode || !svg) return;

      const canvasRect = canvas.getBoundingClientRect();
      const scoreRect = scoreNode.getBoundingClientRect();
      const centerOf = (rect) => ({
        x: rect.left - canvasRect.left + (rect.width / 2),
        y: rect.top - canvasRect.top + (rect.height / 2),
      });

      const scoreCenter = centerOf(scoreRect);
      const pairs = [
        ['lineRegime', '.map-node.regime'],
        ['lineCycle', '.map-node.cycle'],
        ['lineSpot', '.map-node.spot'],
        ['lineSector', '.map-node.sector'],
        ['lineAlert', '.map-node.alerts'],
        ['lineAsset', '.map-node.asset'],
      ];

      svg.setAttribute('viewBox', `0 0 ${canvasRect.width} ${canvasRect.height}`);
      pairs.forEach(([lineId, selector]) => {
        const target = document.querySelector(selector);
        const line = document.getElementById(lineId);
        if (!target || !line) return;
        const targetCenter = centerOf(target.getBoundingClientRect());
        line.setAttribute('x1', String(scoreCenter.x));
        line.setAttribute('y1', String(scoreCenter.y));
        line.setAttribute('x2', String(targetCenter.x));
        line.setAttribute('y2', String(targetCenter.y));
      });
    }
    const el = (id) => document.getElementById(id);
    const timeline = el('timeline');
    const playButton = el('playButton');
    const latestButton = el('latestButton');
    const nodeButtons = Array.from(document.querySelectorAll('.map-node'));

    function formatScore(value) {
      return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(4) : '-';
    }

    function formatSigned(value, digits = 4) {
      return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '-';
    }

    function formatRisk(value) {
      if (value === 'low') return '低い';
      if (value === 'moderate') return '中程度';
      if (value === 'high') return '高い';
      if (value === 'extreme') return '非常に高い';
      return value || '-';
    }

    function escapeHtml(value) {
      return String(value ?? '-')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function severityTone(value) {
      if (value === 'extreme') return 'extreme';
      if (value === 'high') return 'danger';
      if (value === 'moderate') return 'caution';
      return 'normal';
    }

    function formatSeverityInline(label, tone) {
      if (!label) return '-';
      if (tone === 'normal') return label;
      return `<span class="severity-inline ${tone}">${label}</span>`;
    }

    function actionTone(value) {
      if (value === 'wait') return 'danger';
      if (value === 'watch') return 'caution';
      return 'normal';
    }

    function formatActionInline(value, label) {
      return formatSeverityInline(label || value || '-', actionTone(value));
    }

    function formatRiskInline(value) {
      const label = formatRisk(value);
      return formatSeverityInline(label, severityTone(value));
    }

    function alertSeverityTone(value) {
      if (value === 'high') return 'danger';
      if (value === 'moderate') return 'caution';
      return 'normal';
    }

    function formatAlertSeverityInline(alert) {
      return formatSeverityInline(alert?.severity_label || '-', alertSeverityTone(alert?.severity || 'low'));
    }

    function emphasizeRiskText(value) {
      const escaped = escapeHtml(value);
      const protectedTerms = [
        { pattern: /危険ライン/g, token: '__KEEP_RISK_LINE__' },
        { pattern: /警戒ライン/g, token: '__KEEP_CAUTION_LINE__' },
      ];
      const protectedText = protectedTerms.reduce(
        (current, { pattern, token }) => current.replace(pattern, token),
        escaped,
      );
      const replacements = [
        { pattern: /非常に危険/g, tone: 'extreme' },
        { pattern: /危険/g, tone: 'danger' },
        { pattern: /警戒/g, tone: 'caution' },
        { pattern: /注意/g, tone: 'caution' },
        { pattern: /重要/g, tone: 'danger' },
        { pattern: /中程度/g, tone: 'caution' },
        { pattern: /過熱/g, tone: 'danger' },
      ];
      const emphasized = replacements.reduce(
        (current, { pattern, tone }) => current.replace(pattern, (match) => `<span class="severity-inline ${tone}">${match}</span>`),
        protectedText,
      );
      return emphasized
        .replace(/__KEEP_RISK_LINE__/g, '危険ライン')
        .replace(/__KEEP_CAUTION_LINE__/g, '警戒ライン');
    }

    function setDetailCopy(value, emphasize = true) {
      el('detailCopy').innerHTML = emphasize ? emphasizeRiskText(value || '-') : escapeHtml(value || '-');
    }

    function decorateAttentionValue(value, emphasize = true) {
      const raw = value ?? '-';
      const text = typeof raw === 'string' ? raw : String(raw);
      if (!emphasize) return escapeHtml(text);
      if (text.includes('<')) return text;
      return emphasizeRiskText(text);
    }

    function riskStageTone(stageKey) {
      if (stageKey === 'extreme_danger_line_reached') return 'extreme';
      if (stageKey === 'danger_line_reached') return 'danger';
      if (stageKey === 'credit_spillover_initial' || stageKey === 'caution') return 'caution';
      return 'normal';
    }

    function formatRiskStageInline(riskLines) {
      const label = riskLines?.stage_label || '-';
      const tone = riskStageTone(riskLines?.stage_key || 'normal');
      if (tone === 'normal') return label;
      return `<span class="risk-stage-inline ${tone}">${label}</span>`;
    }

    function internalWarningLabel(entry) {
      return `${(entry.warnings || []).length}件 (内部警告)`;
    }

    function formatTimestampInline(value) {
      return (value || '-').replace('T', ' ');
    }

    function formatTimestampStacked(value) {
      if (!value) return 'なし';
      const parts = String(value).split('T');
      if (parts.length !== 2) return String(value);
      return `${parts[0]}<br>${parts[1]}`;
    }

    function formatStatusCounts(summary) {
      if (!summary || !summary.status_counts) return [];
      const labels = { ok: '取得成功', proxy_fallback: '代替ティッカーで取得', sample_fallback: 'サンプル代替', unavailable: '未取得' };
      return Object.entries(summary.status_counts).map(([key, count]) => ({ key, label: labels[key] || key, count }));
    }

    function formatDelta(value) {
      if (typeof value !== 'number' || !Number.isFinite(value)) return '-';
      const sign = value > 0 ? '+' : '';
      return `${sign}${value.toFixed(4)}`;
    }

    function deltaClass(value) {
      if (typeof value !== 'number' || !Number.isFinite(value)) return 'delta-neutral';
      if (value > 0.00005) return 'delta-positive';
      if (value < -0.00005) return 'delta-negative';
      return 'delta-neutral';
    }

    function stageBadges(entry) {
      if (!entry) return [];
      const badges = [];
      const creditFlag = entry.regime?.credit_flag || 'neutral';
      const inflationFlag = entry.regime?.inflation_flag || 'neutral';
      if (creditFlag === 'credit_stress_severe') {
        badges.push({ label: '強め信用', tone: 'credit' });
      } else if (creditFlag === 'credit_stress_moderate') {
        badges.push({ label: '中程度信用', tone: 'credit' });
      } else if (creditFlag === 'credit_improving') {
        badges.push({ label: '信用改善', tone: 'neutral' });
      }
      if (inflationFlag === 'stagflation_warning') {
        badges.push({ label: 'スタグフレ警戒', tone: 'inflation' });
      } else if (inflationFlag === 'inflation_shock_broad') {
        badges.push({ label: '広域インフレ', tone: 'inflation' });
      } else if (inflationFlag === 'inflation_shock_oil_only') {
        badges.push({ label: '原油主導', tone: 'inflation' });
      }
      if (entry.spot_signal?.risk_off_relief_applied) {
        badges.push({ label: '救済あり', tone: 'relief' });
      }
      return badges;
    }

    function renderBadgeRow(targetId, badges) {
      const target = el(targetId);
      if (!target) return;
      if (!badges.length) {
        target.className = 'badge-row is-empty';
        target.innerHTML = '';
        return;
      }
      target.className = 'badge-row';
      target.innerHTML = badges.map((badge) => `<span class="badge badge-${badge.tone || 'neutral'}">${badge.label}</span>`).join('');
    }

    function renderCalibrationSummary() {
      el('calibrationPrimaryCount').textContent = `${dashboardMeta.daily_latest_count || 0}件`;
      el('calibrationSecondaryCount').textContent = `${dashboardMeta.history_count || 0}件`;
      el('calibrationNote').textContent = `主基準は ${dashboardMeta.primary_basis || 'daily_latest'} です。同日の再生成は圧縮し、全履歴は参考として残します。`;
    }

    function renderCurrentRun(entry) {
      const wrap = el('currentRunTableWrap');
      const alert = el('currentRunAlert');
      if (!entry) {
        alert.classList.add('is-hidden');
        el('currentRunTimestamp').textContent = 'なし';
        el('currentRunDataSource').textContent = '未実行';
        el('currentRunDataSourceSub').textContent = '今回の実行結果がまだ保存されていません';
        el('currentRunOkCount').textContent = '-';
        el('currentRunFallbackCount').textContent = '-';
        el('currentRunUnavailableCount').textContent = '-';
        el('currentRunWarningCount').textContent = '-';
        wrap.innerHTML = '<div class="detail-empty">最新の実行結果がまだ保存されていないため、ここには表示できません。</div>';
        return;
      }

      const counts = entry.availability_summary?.status_counts || {};
      const fallbackCount = (counts.proxy_fallback || 0) + (counts.sample_fallback || 0);
      const unavailableCount = counts.unavailable || 0;
      if (entry.data_source === 'sample') {
        alert.classList.remove('is-hidden');
      } else {
        alert.classList.add('is-hidden');
      }
      el('currentRunTimestamp').innerHTML = formatTimestampStacked(entry.generated_at);
      el('currentRunDataSource').textContent = entry.data_source || '-';
      el('currentRunDataSourceSub').textContent =
        entry.data_source === 'sample'
          ? '今回の実行はサンプル代替です。下段の過去 live 成功履歴とは別です。'
          : entry.data_source === 'mixed'
            ? '今回の実行は live と代替が混在しています。'
            : entry.data_source === 'yfinance'
              ? '今回の実行は live 取得です。'
              : '今回の実行結果だけを表示しています。';
      el('currentRunOkCount').textContent = String(counts.ok || 0);
      el('currentRunFallbackCount').textContent = String(fallbackCount);
      el('currentRunUnavailableCount').textContent = String(unavailableCount);
      el('currentRunWarningCount').textContent = String((entry.warnings || []).length);

      const head = ['要求系列', '状態', '実使用系列', '説明'].map((header) => `<th>${header}</th>`).join('');
      const rows = (entry.availability || []).map((row) => (
        `<tr><td>${cellWithSub(row.requested_ticker || '-', row.requested_ticker_name_ja)}</td>` +
        `<td>${row.status === 'ok' ? '取得成功' : row.status === 'proxy_fallback' ? '代替ティッカーで取得' : row.status === 'sample_fallback' ? 'サンプル代替' : '未取得'}</td>` +
        `<td>${cellWithSub(row.used_ticker || '-', row.used_ticker_name_ja)}</td>` +
        `<td>${row.message || '-'}</td></tr>`
      )).join('');
      wrap.innerHTML = rows
        ? `<table class="list-table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`
        : '<div class="detail-empty">今回の取得状況データはありません。</div>';
    }

    function cellWithSub(value, sub) {
      return `${value || '-'}${sub ? `<small>${sub}</small>` : ''}`;
    }

    function plainInline(value) {
      return `<span class="plain-inline">${escapeHtml(value || '-')}</span>`;
    }

    function pulseMetric(name) {
      const target = document.querySelector(`[data-metric=\"${name}\"]`);
      if (!target) return;
      target.dataset.flash = 'false';
      requestAnimationFrame(() => {
        target.dataset.flash = 'true';
        window.setTimeout(() => { target.dataset.flash = 'false'; }, 260);
      });
    }

    function renderBoxes(boxes) {
      el('detailBoxes').innerHTML = boxes.map((box) => `<div class=\"detail-box\"><div class=\"k\">${escapeHtml(box.key)}</div><div class=\"v\">${decorateAttentionValue(box.value, box.emphasize !== false)}</div></div>`).join('');
    }

    function renderTable(title, headers, rows) {
      const disclosure = el('detailTableDisclosure');
      el('detailTableSummary').textContent = title;
      const wrap = el('detailTableWrap');
      if (!rows.length) {
        disclosure.open = true;
        wrap.innerHTML = '<div class=\"detail-empty\">追加の明細はありません。</div>';
        return;
      }
      const head = headers.map((header) => `<th>${header}</th>`).join('');
      const body = rows.map((row) => `<tr>${row.map((cell) => `<td>${decorateAttentionValue(cell)}</td>`).join('')}</tr>`).join('');
      wrap.innerHTML = `<table class=\"list-table\"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    }

    function renderAlerts(alerts) {
      if (!alerts.length) {
        return '<div class="detail-empty">この時点では追加の警告はありません。</div>';
      }
      return `<div class="alert-stack">${alerts.map((alert) => `
        <article class="alert-card ${alert.severity || 'low'}">
          <h4>${alert.title || '-'}</h4>
          <div class="badge-row">
            <span class="badge badge-neutral">${alert.category_label || '-'}</span>
            <span class="badge badge-${alert.severity === 'high' ? 'inflation' : alert.severity === 'moderate' ? 'credit' : 'neutral'}">${formatAlertSeverityInline(alert)}</span>
          </div>
          <p>${alert.message || '-'}</p>
        </article>
      `).join('')}</div>`;
    }

    function buildSectorRotationSvgLegacy(rows) {
      if (!rows.length) {
        return '<div class="detail-empty">有効なセクターデータがありません。</div>';
      }
      const width = 320;
      const height = 340;
      const cx = 160;
      const cy = 170;
      const maxRadius = 126;
      const returns = rows.map((row) => typeof row.return_12w === 'number' ? row.return_12w : 0);
      const minReturn = Math.min(...returns);
      const maxReturn = Math.max(...returns);
      const span = Math.max(maxReturn - minReturn, 0.0001);
      const colors = { leading: '#2f855a', improving: '#3182ce', weakening: '#d69e2e', lagging: '#c53030' };
      const parts = [
        `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="セクターローテーション図">`,
        `<circle cx="${cx}" cy="${cy}" r="${maxRadius}" fill="none" stroke="#d9e2ec" stroke-width="1" />`,
        `<circle cx="${cx}" cy="${cy}" r="${maxRadius * 0.66}" fill="none" stroke="#e9eef2" stroke-width="1" />`,
        `<circle cx="${cx}" cy="${cy}" r="${maxRadius * 0.33}" fill="none" stroke="#f1f5f8" stroke-width="1" />`,
        `<line x1="${cx}" y1="${cy - maxRadius - 12}" x2="${cx}" y2="${cy + maxRadius + 12}" stroke="#d9e2ec" />`,
        `<line x1="${cx - maxRadius - 12}" y1="${cy}" x2="${cx + maxRadius + 12}" y2="${cy}" stroke="#d9e2ec" />`,
        `<text x="${cx}" y="24" text-anchor="middle" font-size="12" fill="#52606d">先導</text>`,
        `<text x="${width - 28}" y="${cy + 4}" text-anchor="middle" font-size="12" fill="#52606d">改善</text>`,
        `<text x="${cx}" y="${height - 16}" text-anchor="middle" font-size="12" fill="#52606d">鈍化</text>`,
        `<text x="28" y="${cy + 4}" text-anchor="middle" font-size="12" fill="#52606d">出遅れ</text>`
      ];
      rows.forEach((row, idx) => {
        const angleDeg = -90 + (360 / rows.length) * idx;
        const angle = angleDeg * Math.PI / 180;
        const radius = 44 + (((typeof row.return_12w === 'number' ? row.return_12w : 0) - minReturn) / span) * (maxRadius - 44);
        const x = cx + radius * Math.cos(angle);
        const y = cy + radius * Math.sin(angle);
        const labelRadius = radius + 18;
        const labelX = cx + labelRadius * Math.cos(angle);
        const labelY = cy + labelRadius * Math.sin(angle) + 4;
        const anchor = labelX >= cx + 14 ? 'start' : labelX <= cx - 14 ? 'end' : 'middle';
        const color = colors[row.rotation_phase] || '#7a5c4d';
        parts.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="6" fill="${color}"><title>${row.ticker} ${row.sector_name_ja || row.ticker} / ${formatSigned(row.return_12w, 4)}</title></circle>`);
        parts.push(`<text x="${labelX.toFixed(1)}" y="${labelY.toFixed(1)}" text-anchor="${anchor}" font-size="11.5" fill="#243b53">${row.ticker}</text>`);
      });
      parts.push('</svg>');
      return parts.join('');
    }

    function sectorBaseColor(ticker) {
      const colors = { XLK: '#2563eb', XLF: '#0f766e', XLE: '#b45309', XLV: '#0ea5a4', XLY: '#db2777', XLP: '#2f855a', XLI: '#475569', XLB: '#ca8a04', XLU: '#7c3aed', XLRE: '#5b6c7d' };
      return colors[ticker] || '#52606d';
    }

    function sectorOutlineColor(baseColor) {
      return blendHexColor(baseColor, '#102a43', 0.35);
    }

    function blendHexColor(baseColor, mixColor, ratio) {
      const normalize = (value) => {
        const hex = String(value || '').replace('#', '');
        return hex.length === 3 ? hex.split('').map((char) => char + char).join('') : hex;
      };
      const base = normalize(baseColor);
      const mix = normalize(mixColor);
      if (base.length !== 6 || mix.length !== 6) return baseColor || '#52606d';
      const blendChannel = (index) => {
        const baseValue = parseInt(base.slice(index, index + 2), 16);
        const mixValue = parseInt(mix.slice(index, index + 2), 16);
        const blended = Math.round(baseValue * (1 - ratio) + mixValue * ratio);
        return blended.toString(16).padStart(2, '0');
      };
      return `#${blendChannel(0)}${blendChannel(2)}${blendChannel(4)}`;
    }

    function buildArrowPolygon(x1, y1, x2, y2, color) {
      const angle = Math.atan2(y2 - y1, x2 - x1);
      const arrowLength = 9;
      const arrowHalfWidth = 4;
      const leftX = x2 - arrowLength * Math.cos(angle) + arrowHalfWidth * Math.sin(angle);
      const leftY = y2 - arrowLength * Math.sin(angle) - arrowHalfWidth * Math.cos(angle);
      const rightX = x2 - arrowLength * Math.cos(angle) - arrowHalfWidth * Math.sin(angle);
      const rightY = y2 - arrowLength * Math.sin(angle) + arrowHalfWidth * Math.cos(angle);
      return `<polygon points="${x2.toFixed(1)},${y2.toFixed(1)} ${leftX.toFixed(1)},${leftY.toFixed(1)} ${rightX.toFixed(1)},${rightY.toFixed(1)}" fill="${color}"></polygon>`;
    }

    function classifyVectorDirection(dx, dy) {
      const absDx = Math.abs(dx || 0);
      const absDy = Math.abs(dy || 0);
      if (absDx < 1e-6 && absDy < 1e-6) return 'flat';
      if (absDy >= absDx) return (dy || 0) < 0 ? 'improving' : 'weakening';
      return (dx || 0) >= 0 ? 'cyclical' : 'defensive';
    }

    function inferQuadrant(point) {
      const x = Number(point?.x || 0);
      const y = Number(point?.y || 0);
      if (Math.abs(x) < 0.1 && Math.abs(y) < 0.1) return 'center';
      if (x >= 0 && y >= 0) return 'leading';
      if (x >= 0 && y < 0) return 'improving';
      if (x < 0 && y < 0) return 'weakening';
      return 'lagging';
    }

    function sectorCandidateReason(analysis, candidateLabel) {
      const normalizedLength = Number(analysis?.normalized_length || 0);
      const consistencyScore = Number(analysis?.consistency?.consistency_score || 0);
      if (candidateLabel === '有望') return `方向が揃い、正規化長 ${normalizedLength.toFixed(2)} と一貫性 ${consistencyScore.toFixed(2)} が十分です。`;
      if (candidateLabel === '監視') return `改善の兆しはありますが、正規化長 ${normalizedLength.toFixed(2)} か一貫性 ${consistencyScore.toFixed(2)} はまだ過熱前です。`;
      if (candidateLabel === '失速警戒') return `位置は高い一方で、勢いが鈍く一貫性 ${consistencyScore.toFixed(2)} も低下しています。`;
      return '中心近傍または方向感不足のため、まだ様子見です。';
    }

    function sectorTooltip(row, analysis) {
      const prev = analysis?.vectors?.previous || {};
      const curr = analysis?.vectors?.current || {};
      const consistency = analysis?.consistency || {};
      const reason = analysis?.candidate_reason || '-';
      return [
        `${row.ticker || '-'} ${row.sector_name_ja || row.ticker || '-'}`,
        `象限 ${analysis?.current_quadrant || 'center'}`,
        `前ベクトル ${prev.direction || 'flat'}`,
        `現ベクトル ${curr.direction || 'flat'}`,
        `正規化長 ${formatSigned(analysis?.normalized_length, 2)}`,
        `一貫性 ${formatSigned(consistency.consistency_score, 2)}`,
        `判定 ${analysis?.candidate_label || '様子見'}: ${reason}`,
      ].join(' | ');
    }

    function buildSectorRotationSvg(sectorRotation) {
      const rows = Array.isArray(sectorRotation?.table) ? sectorRotation.table : [];
      const historyRows = sectorRotation?.history || sectorRotation?.history_points || [];
      if (!rows.length) return '<div class="detail-empty">有効なセクターデータがありません。</div>';
      if (!Array.isArray(historyRows) || !historyRows.length) return buildSectorRotationSvgLegacy(rows);

      const width = 320;
      const height = 320;
      const padding = 34;
      const plotMin = padding;
      const plotMax = width - padding;
      const normalizedHistory = historyRows
        .map((item) => ({ ...item, sector: String(item?.sector || item?.ticker || '').trim() }))
        .filter((item) => item.sector);
      if (!normalizedHistory.length) return buildSectorRotationSvgLegacy(rows);

      const analysisMap = {};
      const serverCandidateMap = sectorRotation?.candidate_map || {};
      const serverVectorAnalysis = sectorRotation?.vector_analysis || {};
      normalizedHistory.forEach((item) => {
        const points = {
          two_weeks_ago: { x: Number(item.x_2w_ago || 0), y: Number(item.y_2w_ago || 0) },
          one_week_ago: { x: Number(item.x_1w_ago || 0), y: Number(item.y_1w_ago || 0) },
          current: { x: Number(item.x_current || 0), y: Number(item.y_current || 0) },
        };
        const prevDx = points.one_week_ago.x - points.two_weeks_ago.x;
        const prevDy = points.one_week_ago.y - points.two_weeks_ago.y;
        const currDx = points.current.x - points.one_week_ago.x;
        const currDy = points.current.y - points.one_week_ago.y;
        const prevLength = Math.hypot(prevDx, prevDy);
        const currLength = Math.hypot(currDx, currDy);
        const avgLength = Math.max(Number(item.avg_length_12w || 1), 1e-6);
        const fallbackNormalizedLength = currLength / avgLength;
        const radius = Math.hypot(points.current.x, points.current.y);
        const prevAngle = prevLength > 1e-6 ? Math.atan2(prevDy, prevDx) : null;
        const currAngle = currLength > 1e-6 ? Math.atan2(currDy, currDx) : null;
        let fallbackConsistencyScore = 0;
        if (prevAngle !== null && currAngle !== null) {
          const rawDiff = Math.abs(currAngle - prevAngle);
          const angleDiff = Math.min(rawDiff, (Math.PI * 2) - rawDiff);
          fallbackConsistencyScore = Math.max(0, 1 - (angleDiff / Math.PI));
        }
        const previousDirection = classifyVectorDirection(prevDx, prevDy);
        const currentDirection = classifyVectorDirection(currDx, currDy);
        const serverAnalysis = serverVectorAnalysis[item.sector] || {};
        const serverCandidate = serverCandidateMap[item.sector] || {};
        const normalizedLength = Number(serverAnalysis?.normalized_length ?? serverCandidate?.normalized_length ?? fallbackNormalizedLength);
        const consistencyScore = Number(serverAnalysis?.consistency?.consistency_score ?? serverCandidate?.consistency_score ?? fallbackConsistencyScore);
        const candidateLabel = String(serverCandidate?.candidate_label || '') || (
          normalizedLength >= 1.1 && consistencyScore >= 0.6
            ? '有望'
            : normalizedLength >= 0.2 || consistencyScore >= 0.3
              ? '監視'
              : radius >= 0.75 && (currentDirection === 'weakening' || currentDirection === 'defensive')
                ? '失速警戒'
                : '様子見'
        );
        analysisMap[item.sector] = {
          points,
          current_quadrant: String(serverAnalysis?.current_quadrant || serverCandidate?.current_quadrant || inferQuadrant(points.current)),
          normalized_length: normalizedLength,
          consistency: { consistency_score: consistencyScore },
          vectors: {
            previous: {
              dx: Number(serverAnalysis?.vectors?.previous?.dx ?? prevDx),
              dy: Number(serverAnalysis?.vectors?.previous?.dy ?? prevDy),
              direction: String(serverAnalysis?.vectors?.previous?.direction || previousDirection),
            },
            current: {
              dx: Number(serverAnalysis?.vectors?.current?.dx ?? currDx),
              dy: Number(serverAnalysis?.vectors?.current?.dy ?? currDy),
              direction: String(serverAnalysis?.vectors?.current?.direction || currentDirection),
            },
          },
          candidate_label: candidateLabel,
        };
        analysisMap[item.sector].candidate_reason = sectorCandidateReason(analysisMap[item.sector], candidateLabel);
      });

      const allPoints = Object.values(analysisMap).flatMap((analysis) => [analysis.points.two_weeks_ago, analysis.points.one_week_ago, analysis.points.current]);
      const xs = allPoints.map((point) => point.x);
      const ys = allPoints.map((point) => point.y);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const spanX = Math.max(maxX - minX, 0.0001);
      const spanY = Math.max(maxY - minY, 0.0001);
      const scalePoint = (point) => {
        const sx = plotMin + ((point.x - minX) / spanX) * (plotMax - plotMin);
        const sy = plotMax - ((point.y - minY) / spanY) * (plotMax - plotMin);
        return [sx, sy];
      };

      const parts = [
        `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="セクターローテーション図">`,
        ``,
        `<rect x="${padding}" y="${padding}" width="${plotMax - plotMin}" height="${plotMax - plotMin}" fill="none" stroke="#d9e2ec" stroke-width="1" rx="16" />`,
        `<line x1="${((plotMin + plotMax) / 2).toFixed(1)}" y1="${plotMin}" x2="${((plotMin + plotMax) / 2).toFixed(1)}" y2="${plotMax}" stroke="#d9e2ec" stroke-width="1" />`,
        `<line x1="${plotMin}" y1="${((plotMin + plotMax) / 2).toFixed(1)}" x2="${plotMax}" y2="${((plotMin + plotMax) / 2).toFixed(1)}" stroke="#d9e2ec" stroke-width="1" />`,
        `<text x="${(width - 52).toFixed(1)}" y="${(plotMin - 12).toFixed(1)}" text-anchor="middle" font-size="12" fill="#52606d">先導</text>`,
        `<text x="${(plotMin + 26).toFixed(1)}" y="${(plotMin - 12).toFixed(1)}" text-anchor="middle" font-size="12" fill="#52606d">改善</text>`,
        `<text x="${(plotMin + 26).toFixed(1)}" y="${(height - 18).toFixed(1)}" text-anchor="middle" font-size="12" fill="#52606d">出遅れ</text>`,
        `<text x="${(width - 52).toFixed(1)}" y="${(height - 18).toFixed(1)}" text-anchor="middle" font-size="12" fill="#52606d">鈍化</text>`,
      ];

      const previousVectors = [];
      const currentVectors = [];
      const oldPoints = [];
      const midPoints = [];
      const currentPoints = [];
      const labels = [];

      rows.forEach((row) => {
        const analysis = analysisMap[row.ticker];
        if (!analysis) return;
        const [xOld, yOld] = scalePoint(analysis.points.two_weeks_ago);
        const [xMid, yMid] = scalePoint(analysis.points.one_week_ago);
        const [xCur, yCur] = scalePoint(analysis.points.current);
        const baseColor = sectorBaseColor(row.ticker);
        const middleColor = blendHexColor(baseColor, '#cbd5e0', 0.45);
        const previousColor = middleColor;
        const currentColor = baseColor;
        const tooltip = escapeHtml(sectorTooltip(row, analysis));
        previousVectors.push(`<g><line x1="${xOld.toFixed(1)}" y1="${yOld.toFixed(1)}" x2="${xMid.toFixed(1)}" y2="${yMid.toFixed(1)}" stroke="${previousColor}" stroke-width="2.2" stroke-linecap="round"><title>${tooltip}</title></line>${buildArrowPolygon(xOld, yOld, xMid, yMid, previousColor)}<title>${tooltip}</title></g>`);
        currentVectors.push(`<g><line x1="${xMid.toFixed(1)}" y1="${yMid.toFixed(1)}" x2="${xCur.toFixed(1)}" y2="${yCur.toFixed(1)}" stroke="${currentColor}" stroke-width="2.8" stroke-linecap="round"><title>${tooltip}</title></line>${buildArrowPolygon(xMid, yMid, xCur, yCur, currentColor)}<title>${tooltip}</title></g>`);
        oldPoints.push(`<circle cx="${xOld.toFixed(1)}" cy="${yOld.toFixed(1)}" r="4.2" fill="#d4d8dd"><title>${tooltip}</title></circle>`);
        midPoints.push(`<circle cx="${xMid.toFixed(1)}" cy="${yMid.toFixed(1)}" r="5" fill="${middleColor}" stroke="#ffffff" stroke-width="1.0"><title>${tooltip}</title></circle>`);
        currentPoints.push(`<circle cx="${xCur.toFixed(1)}" cy="${yCur.toFixed(1)}" r="6.2" fill="${baseColor}" stroke="${sectorOutlineColor(baseColor)}" stroke-width="0.9"><title>${tooltip}</title></circle>`);
        labels.push(`<text x="${(xCur + 8).toFixed(1)}" y="${(yCur - 8).toFixed(1)}" font-size="11" font-weight="700" fill="#1f2933">${escapeHtml(row.ticker || '-')}</text>`);
      });
      parts.push(...previousVectors);
      parts.push(...currentVectors);
      parts.push(...oldPoints);
      parts.push(...midPoints);
      parts.push(...currentPoints);
      parts.push(...labels);
      parts.push('</svg>');
      return parts.join('');
    }

    function renderSectorRotationDetail(sectorRotation) {
      const rows = Array.isArray(sectorRotation?.table) ? sectorRotation.table : [];
      const disclosure = el('detailTableDisclosure');
      el('detailTableSummary').textContent = 'セクター順位と簡易ローテーション図';
      if (!rows.length) {
        el('detailTableWrap').innerHTML = '<div class="detail-empty">有効なセクターデータがありません。</div>';
        disclosure.open = true;
        return;
      }
      const historyRows = sectorRotation?.history || sectorRotation?.history_points || [];
      const historyFlags = Array.isArray(historyRows) ? historyRows.reduce((acc, item) => {
        const ticker = String(item?.sector || item?.ticker || '').trim();
        if (ticker) acc[ticker] = true;
        return acc;
      }, {}) : {};
      const tableHead = ['順位', 'ティッカー', '日本語', '12週騰落率', '位置'].map((header) => `<th>${header}</th>`).join('');
      const tableBody = rows.map((row) => {
        const labelBadge = historyFlags[row.ticker || ''] ? '<br><span class="sector-label-badge">履歴あり</span>' : '';
        return `<tr><td>${row.rank ?? '-'}</td><td>${row.ticker || '-'}</td><td>${row.sector_name_ja || row.ticker || '-'}${labelBadge}</td><td>${formatSigned(row.return_12w, 4)}</td><td>${row.rotation_phase_ja || row.rotation_phase || '-'}</td></tr>`;
      }).join('');
      el('detailTableWrap').innerHTML = `<div class="sector-visual"><div class="sector-visual-card"><h4>簡易ローテーション図</h4>${buildSectorRotationSvg(sectorRotation)}<p>先々週・先週・今週の3点と2本のベクトルで流れを確認します。履歴が無い場合は従来の簡易ローテーション図へ戻ります。</p><p><a href="report.html">最新レポートを見る</a></p></div><div class="sector-visual-card"><h4>セクター順位</h4><table class="list-table"><thead><tr>${tableHead}</tr></thead><tbody>${tableBody}</tbody></table></div></div>`;
      disclosure.open = true;
    }

    function buildChart() {
      const svg = el('scoreChart');
      if (!dashboardData.length) {
        svg.innerHTML = "<text x='24' y='42' fill='#5c6976' font-size='16'>履歴データがありません。</text>";
        chartState.points = [];
        chartState.marker = null;
        return;
      }

      const width = 900;
      const height = 300;
      const left = 48;
      const right = 24;
      const top = 22;
      const bottom = 42;
      const scores = dashboardData.map((entry) => typeof entry.score === 'number' ? entry.score : 0);
      const minScore = Math.min(...scores, 0);
      const maxScore = Math.max(...scores, 1);
      const span = Math.max(maxScore - minScore, 0.0001);
      const stepX = dashboardData.length === 1 ? 0 : (width - left - right) / (dashboardData.length - 1);
      const projectX = (index) => left + stepX * index;
      const projectY = (score) => top + (height - top - bottom) - ((score - minScore) / span) * (height - top - bottom);
      const linePath = dashboardData.map((entry, index) => {
        const score = typeof entry.score === 'number' ? entry.score : 0;
        return `${index === 0 ? 'M' : 'L'} ${projectX(index).toFixed(1)} ${projectY(score).toFixed(1)}`;
      }).join(' ');

      let markup = '';
      for (let step = 0; step <= 4; step += 1) {
        const y = top + ((height - top - bottom) / 4) * step;
        const scoreLabel = (maxScore - (span / 4) * step).toFixed(2);
        markup += `<line x1=\"${left}\" y1=\"${y}\" x2=\"${width - right}\" y2=\"${y}\" stroke=\"#edf2f7\" />`;
        markup += `<text x=\"10\" y=\"${y + 4}\" fill=\"#5c6976\" font-size=\"12\">${scoreLabel}</text>`;
      }
      markup += `<path class=\"score-line\" d=\"${linePath}\" fill=\"none\" stroke=\"#7a5c4d\" stroke-width=\"3\" stroke-linecap=\"round\" stroke-linejoin=\"round\" />`;
      dashboardData.forEach((entry, index) => {
        const x = projectX(index);
        const y = projectY(typeof entry.score === 'number' ? entry.score : 0);
        const color = regimeColors[entry.regime.key] || regimeColors.default;
        markup += `<circle class=\"chart-point\" data-index=\"${index}\" cx=\"${x}\" cy=\"${y}\" r=\"5.5\" fill=\"${color}\" stroke=\"#fff\" stroke-width=\"2\"><title>${entry.generated_at} / ${entry.regime.label} / score ${formatScore(entry.score)}</title></circle>`;
      });
      markup += `<line id=\"chartMarker\" class=\"marker-line\" x1=\"${projectX(detailState.currentIndex)}\" y1=\"${top}\" x2=\"${projectX(detailState.currentIndex)}\" y2=\"${height - bottom}\" stroke=\"#243b53\" stroke-width=\"2\" stroke-dasharray=\"5 5\" />`;
      dashboardData.forEach((entry, index) => {
        if (index % Math.max(Math.ceil(dashboardData.length / 6), 1) === 0 || index === dashboardData.length - 1) {
          markup += `<text x=\"${projectX(index)}\" y=\"${height - 14}\" text-anchor=\"middle\" fill=\"#5c6976\" font-size=\"11\">${entry.generated_at.slice(5, 16).replace('T', ' ')}</text>`;
        }
      });
      svg.innerHTML = markup;
      chartState.points = Array.from(svg.querySelectorAll('.chart-point'));
      chartState.marker = el('chartMarker');
      updateChart(detailState.currentIndex);
    }

    function updateChart(index) {
      const chartShell = el('chartShell');
      if (chartShell) {
        chartShell.classList.add('is-refreshing');
        window.setTimeout(() => chartShell.classList.remove('is-refreshing'), 180);
      }
      chartState.points.forEach((point, pointIndex) => {
        point.setAttribute('r', pointIndex === index ? '7.2' : '5.5');
        point.setAttribute('stroke-width', pointIndex === index ? '3' : '2');
      });
      if (chartState.marker && chartState.points[index]) {
        const x = chartState.points[index].getAttribute('cx');
        chartState.marker.setAttribute('x1', x);
        chartState.marker.setAttribute('x2', x);
      }
    }

    function setActiveNode(nodeName) {
      detailState.selectedNode = nodeName;
      syncRelationState();
    }

    function syncRelationState(hoveredNode = null) {
      const activeNode = hoveredNode || detailState.selectedNode;
      const lines = Array.from(document.querySelectorAll('.relation-svg line'));
      nodeButtons.forEach((button) => {
        const nodeName = button.dataset.node;
        const isSelected = nodeName === detailState.selectedNode;
        const isActive = nodeName === activeNode;
        const shouldDim = Boolean(activeNode) && !isActive && nodeName !== 'score';
        button.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
        button.classList.toggle('is-active', isActive || isSelected);
        button.classList.toggle('is-dim', shouldDim);
      });
      lines.forEach((line) => {
        const target = line.dataset.target;
        const isActiveLine = activeNode === 'score' || activeNode === target;
        line.classList.toggle('is-active', Boolean(activeNode) && isActiveLine);
        line.classList.toggle('is-dim', Boolean(activeNode) && !isActiveLine);
      });
    }

    function renderDetail(entry) {
      if (!entry) {
        el('detailTitle').textContent = '詳細';
        el('detailSubtitle').textContent = '履歴データがありません。';
        setDetailCopy('まずレポートを生成して履歴 JSON を作成してください。', false);
        renderBoxes([]);
        renderBadgeRow('flowBadges', []);
        renderTable('明細を表示', [], []);
        return;
      }

      const node = detailState.selectedNode;
      if (node === 'regime') {
        el('detailTitle').textContent = '市場レジーム';
        el('detailSubtitle').textContent = `${entry.generated_at} の地合い判定`;
        setDetailCopy('市場レジームは相場全体の強弱を大づかみに見る中心指標です。ここで大枠を見たあとに、サイクルやスポット判断へ進むと判断の順番が安定します。');
        renderBoxes([{ key: '判定', value: entry.regime.label }, { key: 'レジームスコア', value: formatSigned(entry.regime.score, 3) }, { key: 'データソース', value: entry.data_source }]);
        renderTable('市場レジームの補助情報', ['項目', '内容'], [['合成スコア', formatScore(entry.score)], ['判定用スコア', formatScore(entry.adjusted_score)], ['スポット判断', entry.spot_signal.label], ['先導セクター', entry.top_sector?.label || '-']]);
        return;
      }
      if (node === 'score') {
        el('detailTitle').textContent = '合成スコア';
        el('detailSubtitle').textContent = '押し目条件のまとまり';
        setDetailCopy('合成スコアは 0 から 1 の範囲で、市場レジームやモメンタム環境をまとめた要約です。高いほど押し目検討の条件が揃っています。');
        renderBoxes([{ key: '合成スコア', value: formatScore(entry.score) }, { key: '判定用スコア', value: formatScore(entry.adjusted_score) }, { key: 'レジーム減点', value: formatScore(entry.regime_penalty) }, { key: 'スポット判断', value: entry.spot_signal.label }]);
        setDetailCopy('合成スコアは押し目条件の要約です。ここでの内部警告件数は alerts/warnings の件数で、危険ライン段階とは別の判定です。危険ライン段階は下の表で独立して確認します。');
        renderBoxes([{ key: '合成スコア', value: formatScore(entry.score) }, { key: '判定用スコア', value: formatScore(entry.adjusted_score) }, { key: 'レジーム減点', value: formatScore(entry.regime_penalty) }, { key: '危険ライン段階', value: formatRiskStageInline(entry.risk_lines) }]);
        renderTable('合成スコアの確認項目', ['項目', '内容'], [['市場レジーム', entry.regime.label], ['サイクル判定', entry.cycle.label], ['二段下げリスク', formatRiskInline(entry.spot_signal.risk)], ['危険ライン段階', formatRiskStageInline(entry.risk_lines)], ['危険ライン件数', emphasizeRiskText(`危険 ${entry.risk_lines?.danger_count || 0} / 非常に危険 ${entry.risk_lines?.extreme_count || 0}`)], ['内部警告件数', internalWarningLabel(entry)], ['内部警告と危険ラインの違い', emphasizeRiskText('内部警告は alerts/warnings の件数、危険ラインは market stress の段階判定です。')]]);
        return;
      }
      if (node === 'cycle') {
        el('detailTitle').textContent = 'サイクル判定';
        el('detailSubtitle').textContent = '位相ベースの相場位置';
        setDetailCopy('サイクル判定は、上昇・終盤・回復・下降のどこに近いかを補助的に見る項目です。レジームより時間の流れを読み取りやすくします。');
        renderBoxes([{ key: '判定', value: entry.cycle.label }, { key: '位相角', value: entry.cycle.angle ?? '-' }, { key: '市場レジーム', value: entry.regime.label }]);
        renderTable('サイクル判定の関連項目', ['項目', '内容'], [['合成スコア', formatScore(entry.score)], ['スポット判断', entry.spot_signal.label], ['先導セクター', entry.top_sector?.label || '-']]);
        return;
      }
      if (node === 'spot') {
        el('detailTitle').textContent = 'スポット投資判断';
        el('detailSubtitle').textContent = '運用向けの要約';
        setDetailCopy('スポット投資判断は、地合いとサイクルとドローダウン状態をまとめた短い結論です。買い検討・監視継続・待機のどこにいるかを確認できます。');
        renderBoxes([{ key: '判断', value: formatActionInline(entry.spot_signal.action, entry.spot_signal.label) }, { key: '二段下げリスク', value: formatRiskInline(entry.spot_signal.risk) }, { key: '合成スコア', value: formatScore(entry.score) }, { key: '判定用スコア', value: formatScore(entry.adjusted_score) }]);
        renderTable('スポット判断の根拠', ['順番', '内容'], (entry.spot_signal.rationale || []).map((reason, idx) => [String(idx + 1), emphasizeRiskText(reason)]));
        return;
      }
      if (node === 'sector') {
        el('detailTitle').textContent = 'セクターローテーション';
        el('detailSubtitle').textContent = '上位セクターの流れ';
        setDetailCopy('その時点で資金がどのセクターへ向かっていたかを確認します。順位と位置をあわせて見ると、単なる騰落率より流れが追いやすくなります。');
        renderBoxes([{ key: '先導セクター', value: entry.top_sector?.label || '-' }, { key: 'ティッカー', value: entry.top_sector?.ticker || '-' }, { key: '12週騰落率', value: formatSigned(entry.top_sector?.return_12w, 4) }]);
        renderSectorRotationDetail(entry.sector_rotation || { table: entry.sector_table || [] });
        return;
      }
      if (node === 'alerts') {
        const alerts = entry.alerts || [];
        const marketCount = alerts.filter((alert) => alert.category === 'market').length;
        const lifeCount = alerts.filter((alert) => alert.category === 'life').length;
        const memoCount = alerts.filter((alert) => alert.category === 'memo').length;
        el('detailTitle').textContent = '警告レイヤー';
        el('detailSubtitle').textContent = '市場と生活の警戒灯';
        setDetailCopy('警告レイヤーは、既存の判定ロジックがどこで警戒を発火しているかを示す補助ビューです。売買判断を直接上書きせず、市場警告、生活影響警告、補足メモに分けて現在の内部状態を見やすくします。', false);
        renderBoxes([
          { key: '市場警告', value: String(marketCount) },
          { key: '生活影響警告', value: String(lifeCount) },
          { key: '補足メモ', value: String(memoCount) },
        ]);
        renderTable('警告一覧', ['区分', '重要度', 'タイトル', '内容'], alerts.map((alert) => [
          alert.category_label || '-',
          formatAlertSeverityInline(alert),
          plainInline(alert.title || '-'),
          emphasizeRiskText(alert.message || '-'),
        ]));
        return;
      }
      if (node === 'asset') {
        el('detailTitle').textContent = '資産クラス比較';
        el('detailSubtitle').textContent = '相対優位の確認';
        setDetailCopy('株式、債券、金、不動産などの相対強弱を並べて確認するセクションです。セクターの流れと合わせると、資金の向かう方向を広い粒度で把握できます。');
        renderBoxes([
          { key: '上位資産', value: entry.top_asset?.label || '-' },
          { key: 'ティッカー', value: entry.top_asset?.ticker || '-' },
          { key: '12週モメンタム', value: formatSigned(entry.top_asset?.momentum_12w, 4) },
          { key: '候補判定', value: entry.investment_candidates?.label || '候補なし' },
        ]);
        const candidate = entry.investment_candidates || {};
        const candidateRows = [
          ['候補判定', candidate.label || '候補なし'],
          ['要約', candidate.summary || '-'],
          ['優先資産', candidate.preferred_asset_class ? `${candidate.preferred_asset_class.asset_class || '-'} / ${candidate.preferred_asset_class.ticker || '-'}` : 'なし'],
          ['優先セクター', candidate.preferred_sector ? `${candidate.preferred_sector.sector_name_ja || '-'} / ${candidate.preferred_sector.ticker || '-'}` : 'なし'],
          ['候補ティッカー', (candidate.candidate_tickers || []).map((item) => `${item.ticker || '-'}(${item.label || '-'})`).join(', ') || 'なし'],
        ];
        (candidate.rationale || []).forEach((reason, idx) => candidateRows.push([`候補理由 ${idx + 1}`, reason]));
        renderTable('投資候補の確認', ['項目', '内容'], candidateRows);
        renderTable('資産クラス比較', ['資産クラス', 'ティッカー', '日本語', '12週モメンタム', '年率ボラ', '最大DD'], (entry.asset_compare || []).map((row) => [row.asset_class || '-', row.ticker || '-', row.ticker_name_ja || row.ticker || '-', formatSigned(row.momentum_12w, 4), formatSigned(row.annualized_volatility, 4), formatSigned(row.max_drawdown, 4)]));
        return;
      }
      if (node === 'candidates') {
        const candidate = entry.investment_candidates || {};
        el('detailTitle').textContent = '追随候補';
        el('detailSubtitle').textContent = '今強い流れを追う候補';
        setDetailCopy('ここでは相対強度が高く、今すでに資金が向かっている候補を見ます。先回り候補とは意味が逆なので、このノードでは追随側だけを表示します。');
        renderBoxes([
          { key: '候補判定', value: candidate.label || '候補なし' },
          { key: '候補数', value: String((candidate.candidate_tickers || []).length) },
          { key: '優先資産', value: candidate.preferred_asset_class ? `${candidate.preferred_asset_class.asset_class || '-'} / ${candidate.preferred_asset_class.ticker || '-'}` : 'なし' },
          { key: '優先セクター', value: candidate.preferred_sector ? `${candidate.preferred_sector.sector_name_ja || '-'} / ${candidate.preferred_sector.ticker || '-'}` : 'なし' },
        ]);
        const rows = [
          ['候補判定', candidate.label || '候補なし'],
          ['要約', candidate.summary || '-'],
          ['優先資産', candidate.preferred_asset_class ? `${candidate.preferred_asset_class.asset_class || '-'} / ${candidate.preferred_asset_class.ticker || '-'} / ${candidate.preferred_asset_class.ticker_name_ja || '-'}` : 'なし'],
          ['優先セクター', candidate.preferred_sector ? `${candidate.preferred_sector.sector_name_ja || '-'} / ${candidate.preferred_sector.ticker || '-'} / 12週 ${formatSigned(candidate.preferred_sector.return_12w, 4)}` : 'なし'],
          ['候補ティッカー', (candidate.candidate_tickers || []).map((item) => `${item.ticker || '-'}(${item.label || '-'})`).join(', ') || 'なし'],
        ];
        (candidate.rationale || []).forEach((reason, idx) => rows.push([`理由 ${idx + 1}`, reason]));
        renderTable('追随候補の詳細', ['項目', '内容'], rows);
        return;
      }
      if (node === 'recovery_candidates') {
        const recovery = entry.recovery_candidates || {};
        el('detailTitle').textContent = '先回り候補';
        el('detailSubtitle').textContent = '底打ち初期を狙う候補';
        setDetailCopy('ここでは今はまだ強すぎないものの、深い下落のあとで改善し始めた候補を見ます。追随候補より時間軸が長く、安く仕込む前提の補助ビューです。');
        renderBoxes([
          { key: '候補判定', value: recovery.label || '候補なし' },
          { key: '候補数', value: String((recovery.candidate_tickers || []).length) },
          { key: '優先資産', value: recovery.preferred_asset_class ? `${recovery.preferred_asset_class.label || '-'} / ${recovery.preferred_asset_class.ticker || '-'}` : 'なし' },
          { key: '優先セクター', value: recovery.preferred_sector ? `${recovery.preferred_sector.ticker_name_ja || '-'} / ${recovery.preferred_sector.ticker || '-'}` : 'なし' },
        ]);
        const rows = [
          ['候補判定', recovery.label || '候補なし'],
          ['要約', recovery.summary || '-'],
          ['優先資産', recovery.preferred_asset_class ? `${recovery.preferred_asset_class.label || '-'} / ${recovery.preferred_asset_class.ticker || '-'} / ${recovery.preferred_asset_class.ticker_name_ja || '-'}` : 'なし'],
          ['優先セクター', recovery.preferred_sector ? `${recovery.preferred_sector.ticker_name_ja || '-'} / ${recovery.preferred_sector.ticker || '-'} / 4週 ${formatSigned(recovery.preferred_sector.momentum_4w, 4)}` : 'なし'],
          ['候補ティッカー', (recovery.candidate_tickers || []).map((item) => `${item.ticker || '-'}(${item.label || '-'})`).join(', ') || 'なし'],
        ];
        (recovery.rationale || []).forEach((reason, idx) => rows.push([`理由 ${idx + 1}`, reason]));
        renderTable('先回り候補の詳細', ['項目', '内容'], rows);
        return;
      }
      if (node === 'regime_leading_candidates') {
        const regimeLeading = entry.regime_leading_candidates || {};
        el('detailTitle').textContent = 'レジーム先回り候補';
        el('detailSubtitle').textContent = '次の地合いで効きやすい資産・地域・セクター';
        setDetailCopy('ここでは大きく下げた反転銘柄ではなく、次のレジームで効きやすい資産・地域・セクターを見ます。価格の底打ちそのものより、現レジームとの相性と直近の改善兆候を重視する補助ビューです。');
        renderBoxes([
          { key: '候補判定', value: regimeLeading.label || '候補なし' },
          { key: '候補数', value: String((regimeLeading.candidate_tickers || []).length) },
          { key: '優先セクター', value: regimeLeading.preferred_sector ? `${regimeLeading.preferred_sector.ticker_name_ja || '-'} / ${regimeLeading.preferred_sector.ticker || '-'}` : 'なし' },
          { key: '優先地域', value: regimeLeading.preferred_region ? `${regimeLeading.preferred_region.ticker_name_ja || '-'} / ${regimeLeading.preferred_region.ticker || '-'}` : 'なし' },
          { key: '優先資産', value: regimeLeading.preferred_asset_class ? `${regimeLeading.preferred_asset_class.ticker_name_ja || '-'} / ${regimeLeading.preferred_asset_class.ticker || '-'}` : 'なし' },
          { key: '現レジーム', value: entry.regime.label || '-' },
        ]);
        const rows = [
          ['候補判定', regimeLeading.label || '候補なし'],
          ['要約', regimeLeading.summary || '-'],
          ['優先セクター', regimeLeading.preferred_sector ? `${regimeLeading.preferred_sector.ticker_name_ja || '-'} / ${regimeLeading.preferred_sector.ticker || '-'} / 4週 ${formatSigned(regimeLeading.preferred_sector.momentum_4w, 4)} / 12週 ${formatSigned(regimeLeading.preferred_sector.momentum_12w, 4)}` : 'なし'],
          ['優先地域', regimeLeading.preferred_region ? `${regimeLeading.preferred_region.ticker_name_ja || '-'} / ${regimeLeading.preferred_region.ticker || '-'} / 4週 ${formatSigned(regimeLeading.preferred_region.momentum_4w, 4)} / 12週 ${formatSigned(regimeLeading.preferred_region.momentum_12w, 4)}` : 'なし'],
          ['優先資産', regimeLeading.preferred_asset_class ? `${regimeLeading.preferred_asset_class.ticker_name_ja || '-'} / ${regimeLeading.preferred_asset_class.ticker || '-'} / 4週 ${formatSigned(regimeLeading.preferred_asset_class.momentum_4w, 4)} / 12週 ${formatSigned(regimeLeading.preferred_asset_class.momentum_12w, 4)}` : 'なし'],
          ['候補ティッカー', (regimeLeading.candidate_tickers || []).map((item) => `${item.ticker || '-'}(${item.label || '-'}: ${item.reason || '-'})`).join(', ') || 'なし'],
        ];
        (regimeLeading.rationale || []).forEach((reason, idx) => rows.push([`理由 ${idx + 1}`, reason]));
        renderTable('レジーム先回り候補の詳細', ['項目', '内容'], rows);
        return;
      }
      el('detailTitle').textContent = 'データ取得状況';
      el('detailSubtitle').textContent = '代替取得や欠損の監査';
      setDetailCopy('ここで見ているのは履歴時点の取得状況です。上段の「今回の実行結果」とは独立しているため、値が違う場合は過去履歴との差です。', false);
      const counts = formatStatusCounts(entry.availability_summary);
      renderBoxes([{ key: '問題件数', value: `${entry.availability_summary.issues} / ${entry.availability_summary.total}` }, ...counts.slice(0, 2).map((item) => ({ key: item.label, value: String(item.count) }))]);
      renderTable('取得状況の明細', ['要求系列', '状態', '実使用系列', '説明'], (entry.availability || []).slice(0, 10).map((row) => [cellWithSub(row.requested_ticker || '-', row.requested_ticker_name_ja), row.status === 'ok' ? '取得成功' : row.status === 'proxy_fallback' ? '代替ティッカーで取得' : row.status === 'sample_fallback' ? 'サンプル代替' : '未取得', cellWithSub(row.used_ticker || '-', row.used_ticker_name_ja), row.message || '-']));
    }

    function updateSummary(entry) {
      if (!entry) {
        el('focusTimestamp').value = '履歴なし';
        el('timelineCount').value = '0件';
        el('timestampLabel').value = '履歴なし';
        el('metricScoreDelta').textContent = '-';
        el('metricScoreDelta').className = 'v delta-neutral';
        el('metricAdjusted').textContent = '-';
        el('metricPenalty').textContent = '-';
        el('metricRegimeCopy').textContent = '現在の地合いを最優先で読む領域です。';
        renderBadgeRow('metricRegimeBadges', []);
        return;
      }
      const previousEntry = detailState.currentIndex > 0 ? dashboardData[detailState.currentIndex - 1] : null;
      const scoreDelta = previousEntry && typeof previousEntry.score === 'number' && typeof entry.score === 'number'
        ? entry.score - previousEntry.score
        : null;
      el('focusTimestamp').innerHTML = formatTimestampStacked(entry.generated_at);
      el('timelineCount').value = `${dashboardData.length}件の履歴`;
      el('timestampLabel').value = formatTimestampInline(entry.generated_at);
      el('metricRegime').textContent = entry.regime.label;
      el('metricRegime').style.color = regimeColors[entry.regime.key] || regimeColors.default;
      el('metricRegimeSub').textContent = `データソース: ${entry.data_source} / 前回比較 ${previousEntry ? 'あり' : 'なし'}`;
      el('metricRegimeCopy').textContent = entry.data_reliability?.decision_allowed
        ? `判定用スコア ${formatScore(entry.adjusted_score)} を踏まえて、現在の主導レジームを読む領域です。`
        : '重要系列の live 取得不足により、通常の市場判定は保留しています。';
      renderBadgeRow('metricRegimeBadges', stageBadges(entry));
      pulseMetric('primary');
      el('metricScore').textContent = formatScore(entry.score);
      el('metricScoreSub').innerHTML = `判定用 ${formatScore(entry.adjusted_score)} / 減点 ${formatScore(entry.regime_penalty)} / ${formatRiskStageInline(entry.risk_lines)}`;
      el('metricScoreDelta').textContent = formatDelta(scoreDelta);
      el('metricScoreDelta').className = `v ${deltaClass(scoreDelta)}`;
      el('metricAdjusted').textContent = formatScore(entry.adjusted_score);
      el('metricPenalty').textContent = formatScore(entry.regime_penalty);
      el('metricCycle').textContent = entry.cycle.label;
      el('metricCycleSub').textContent = `位相角 ${entry.cycle.angle ?? '-'} 度`;
      pulseMetric('cycle');
      el('metricSpot').innerHTML = formatActionInline(entry.spot_signal.action, entry.spot_signal.label);
      el('metricSpotSub').innerHTML = entry.data_reliability?.decision_allowed
        ? emphasizeRiskText(`二段下げリスク: ${formatRisk(entry.spot_signal.risk)}`)
        : emphasizeRiskText('データ不足のため参考値ではなく保留扱い');
      pulseMetric('spot');
      const okCount = entry.availability_summary?.status_counts?.ok || 0;
      el('metricAvailability').textContent = `${okCount} / ${entry.availability_summary.total}`;
      const issueCount = entry.availability_summary?.issues || 0;
      const issueLabel = issueCount === 0 ? '異常なし' : `問題 ${issueCount}件`;
      const availabilitySub = el('metricAvailabilitySub');
      if (availabilitySub) availabilitySub.innerHTML = `<strong>${issueLabel}</strong><br>今回の実行結果で監査`;
      pulseMetric('availability');
      el('nodeRegime').textContent = entry.regime.label;
      el('nodeRegime').style.color = regimeColors[entry.regime.key] || regimeColors.default;
      el('nodeRegimeSub').textContent = `source: ${entry.data_source}`;
      el('nodeScore').textContent = formatScore(entry.score);
      el('nodeScoreSub').innerHTML = `判定用 ${formatScore(entry.adjusted_score)} / ${entry.regime.label} / ${formatRiskStageInline(entry.risk_lines)}`;
      el('nodeCycle').textContent = entry.cycle.label;
      el('nodeCycleSub').textContent = `位相角 ${entry.cycle.angle ?? '-'} 度`;
      el('nodeSpot').innerHTML = formatActionInline(entry.spot_signal.action, entry.spot_signal.label);
      el('nodeSpotSub').innerHTML = entry.data_reliability?.decision_allowed
        ? emphasizeRiskText(`二段下げリスク ${formatRisk(entry.spot_signal.risk)}`)
        : emphasizeRiskText('live 取得不足で判定保留');
      el('nodeSector').textContent = entry.top_sector?.label || '-';
      el('nodeSectorSub').textContent = entry.top_sector ? `${entry.top_sector.ticker} / 12週 ${formatSigned(entry.top_sector.return_12w, 4)}` : 'データなし';
      const alerts = entry.alerts || [];
      const highAlert = alerts.find((alert) => alert.severity === 'high') || alerts[0];
      el('nodeAlerts').innerHTML = highAlert ? escapeHtml(highAlert.title) : '追加警告なし';
      el('nodeAlertsSub').innerHTML = highAlert
        ? `${escapeHtml(highAlert.category_label)} / ${formatAlertSeverityInline(highAlert)}`
        : '内部警告は静穏';
      el('nodeAsset').textContent = entry.top_asset?.label || '-';
      el('nodeAssetSub').textContent = entry.top_asset ? `${entry.top_asset.ticker} / 12週 ${formatSigned(entry.top_asset.momentum_12w, 4)}` : 'データなし';
      el('nodeCandidates').innerHTML = decorateAttentionValue(entry.investment_candidates?.label || '候補なし');
      el('nodeCandidatesSub').innerHTML = decorateAttentionValue(entry.investment_candidates?.summary || '今強い流れを追う候補');
      el('nodeRecoveryCandidates').innerHTML = decorateAttentionValue(entry.recovery_candidates?.label || '候補なし');
      el('nodeRecoveryCandidatesSub').innerHTML = decorateAttentionValue(entry.recovery_candidates?.summary || '底打ち初期を狙う候補');
      el('nodeRegimeLeadingCandidates').innerHTML = decorateAttentionValue(entry.regime_leading_candidates?.label || '候補なし');
      el('nodeRegimeLeadingCandidatesSub').innerHTML = decorateAttentionValue(entry.regime_leading_candidates?.summary || '次の地合いで効きやすい候補');
      syncRelationState();
      window.requestAnimationFrame(updateRelationLines);
    }

    function selectIndex(index) {
      if (!dashboardData.length) {
        renderDetail(null);
        return;
      }
      detailState.currentIndex = index;
      timeline.value = String(index);
      const entry = dashboardData[index];
      updateSummary(entry);
      updateChart(index);
      renderDetail(entry);
    }

    function stopPlayback() {
      if (detailState.timer) {
        window.clearInterval(detailState.timer);
        detailState.timer = null;
      }
      playButton.textContent = '再生';
    }

    function togglePlayback() {
      if (!dashboardData.length) return;
      if (detailState.timer) {
        stopPlayback();
        return;
      }
      playButton.textContent = '停止';
      detailState.timer = window.setInterval(() => {
        const next = detailState.currentIndex >= dashboardData.length - 1 ? 0 : detailState.currentIndex + 1;
        selectIndex(next);
      }, 1300);
    }

    timeline.addEventListener('input', (event) => {
      stopPlayback();
      selectIndex(Number(event.target.value));
    });
    playButton.addEventListener('click', togglePlayback);
    latestButton.addEventListener('click', () => {
      stopPlayback();
      if (dashboardData.length) selectIndex(dashboardData.length - 1);
    });
    nodeButtons.forEach((button) => {
      button.addEventListener('click', () => {
        setActiveNode(button.dataset.node);
        renderDetail(dashboardData[detailState.currentIndex] || null);
      });
      button.addEventListener('mouseenter', () => {
        syncRelationState(button.dataset.node);
      });
      button.addEventListener('mouseleave', () => {
        syncRelationState();
      });
      button.addEventListener('focus', () => {
        syncRelationState(button.dataset.node);
      });
      button.addEventListener('blur', () => {
        syncRelationState();
      });
    });

    window.addEventListener('resize', updateRelationLines);

    renderCurrentRun(currentRun);
    renderCalibrationSummary();

    if (dashboardData.length) {
      timeline.max = String(dashboardData.length - 1);
      timeline.value = String(dashboardData.length - 1);
      buildChart();
      selectIndex(dashboardData.length - 1);
    } else {
      timeline.max = '0';
      timeline.value = '0';
      buildChart();
      renderDetail(null);
    }
  </script>
</body>
</html>
"""


def write_dashboard(reports_dir: str | Path) -> Path:
    reports_path = Path(reports_dir)
    history_entries = load_history_entries(reports_path / "history")
    current_run = load_current_run_entry(reports_path / "report_summary.json")
    dashboard_path = reports_path / "dashboard.html"
    dashboard_path.write_text(render_dashboard_html(history_entries, current_run=current_run), encoding="utf-8")
    return dashboard_path


def load_history_entries(history_dir: str | Path) -> list[dict[str, Any]]:
    history_path = Path(history_dir)
    if not history_path.exists():
        return []

    entries: list[dict[str, Any]] = []
    for file_path in sorted(history_path.glob("report_*.json")):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        entries.append(_normalize_dashboard_entry(data))
    return entries


def load_current_run_entry(summary_path: str | Path) -> dict[str, Any] | None:
    path = Path(summary_path)
    if not path.exists():
        return None
    return _normalize_dashboard_entry(json.loads(path.read_text(encoding="utf-8")))


def render_dashboard_html(entries: list[dict[str, Any]], current_run: dict[str, Any] | None = None) -> str:
    payload = json.dumps(
        {
            "current_run": current_run,
            "history": entries,
            "meta": _build_dashboard_meta(entries),
        },
        ensure_ascii=False,
    )
    return DASHBOARD_TEMPLATE.replace("__PAYLOAD__", payload)


def _normalize_dashboard_entry(data: dict[str, Any]) -> dict[str, Any]:
    sector_rotation = data.get("sector_rotation", {})
    sector_table = sector_rotation.get("table", [])
    asset_rows = data.get("asset_compare", [])
    availability = data.get("data_availability", [])
    issue_count = sum(
        1 for item in availability if item.get("status") in {"proxy_fallback", "sample_fallback", "unavailable"}
    )
    return {
        "generated_at": data.get("generated_at", ""),
        "data_source": data.get("data_source", "-"),
        "data_reliability": data.get("data_reliability", {"level": "high", "decision_allowed": True, "reason": ""}),
        "regime": {
            "key": data.get("regime", {}).get("regime_label", ""),
            "label": REGIME_LABELS.get(
                data.get("regime", {}).get("regime_label", ""),
                data.get("regime", {}).get("regime_label", ""),
            ),
            "score": data.get("regime", {}).get("regime_score"),
            "credit_flag": data.get("regime", {}).get("credit_regime_flag", "neutral"),
            "inflation_flag": data.get("regime", {}).get("inflation_regime_flag", "neutral"),
        },
        "cycle": {
            "key": data.get("cycle", {}).get("phase_label", ""),
            "label": CYCLE_LABELS.get(
                data.get("cycle", {}).get("phase_label", ""),
                data.get("cycle", {}).get("phase_label", ""),
            ),
            "angle": data.get("cycle", {}).get("phase_angle_deg"),
        },
        "score": data.get("score", {}).get("total_score"),
        "adjusted_score": data.get("spot_signal", {}).get("adjusted_score", data.get("score", {}).get("total_score")),
        "regime_penalty": data.get("spot_signal", {}).get("regime_penalty", 0),
        "spot_signal": {
            "key": data.get("spot_signal", {}).get("action", ""),
            "label": ACTION_LABELS.get(
                data.get("spot_signal", {}).get("action", ""),
                data.get("spot_signal", {}).get("action", ""),
            ),
            "risk": data.get("spot_signal", {}).get("second_leg_risk", ""),
            "rationale": _translate_spot_rationale(data.get("spot_signal", {}).get("rationale", [])),
            "risk_off_relief_applied": bool(data.get("spot_signal", {}).get("risk_off_relief_applied", False)),
        },
        "alerts": _normalize_alerts(data.get("alerts", [])),
        "risk_lines": {
            "stage_key": data.get("risk_lines", {}).get("stage_key", "normal"),
            "stage_label": data.get("risk_lines", {}).get("stage_label", "通常"),
            "danger_count": data.get("risk_lines", {}).get("danger_count", 0),
            "extreme_count": data.get("risk_lines", {}).get("extreme_count", 0),
            "summary": data.get("risk_lines", {}).get("summary", "-"),
            "precision_label": data.get("risk_lines", {}).get("precision_label", "-"),
        },
        "investment_candidates": data.get("investment_candidates", {"label": "候補なし", "summary": "-", "candidate_tickers": [], "rationale": []}),
        "recovery_candidates": data.get("recovery_candidates", {"label": "候補なし", "summary": "-", "candidate_tickers": [], "rationale": []}),
        "regime_leading_candidates": data.get("regime_leading_candidates", {"label": "候補なし", "summary": "-", "candidate_tickers": [], "rationale": [], "preferred_sector": None, "preferred_region": None, "preferred_asset_class": None}),
        "top_sector": _top_sector(sector_table),
        "top_asset": _top_asset(asset_rows),
        "sector_rotation": sector_rotation,
        "sector_table": sector_table,
        "asset_compare": asset_rows,
        "availability_summary": {
            "issues": issue_count,
            "total": len(availability),
            "status_counts": _status_counts(availability),
        },
        "availability": availability,
        "warnings": data.get("warnings", []),
    }


def _build_dashboard_meta(entries: list[dict[str, Any]]) -> dict[str, Any]:
    deduped = _dedupe_entries_by_day(entries)
    return {
        "history_count": len(entries),
        "daily_latest_count": len(deduped),
        "primary_basis": "daily_latest",
        "primary_label": "主基準: daily_latest",
        "secondary_label": "参考: all_history",
    }


def _dedupe_entries_by_day(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_by_day: dict[str, dict[str, Any]] = {}
    for entry in entries:
        generated_at = str(entry.get("generated_at", ""))
        day_key = generated_at[:10]
        existing = latest_by_day.get(day_key)
        if existing is None or generated_at > str(existing.get("generated_at", "")):
            latest_by_day[day_key] = entry
    return [latest_by_day[key] for key in sorted(latest_by_day)]


def _status_counts(availability: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in availability:
        key = item.get("status", "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _translate_spot_rationale(rationale: list[str]) -> list[str]:
    translated: list[str] = []
    for reason in rationale:
        if reason.startswith("Regime is ") and reason.endswith("."):
            key = reason[len("Regime is ") : -1]
            translated.append(f"市場レジームは {REGIME_LABELS.get(key, key)} です。")
        elif reason.startswith("Cycle phase is ") and reason.endswith("."):
            key = reason[len("Cycle phase is ") : -1]
            translated.append(f"サイクル判定は {CYCLE_LABELS.get(key, key)} です。")
        elif reason.startswith("Composite score is ") and reason.endswith("."):
            value = reason[len("Composite score is ") : -1]
            translated.append(f"合成スコアは {value} です。")
        else:
            translated.append(reason)
    return translated


def _normalize_alerts(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for alert in alerts:
        category = str(alert.get("category", "memo"))
        severity = str(alert.get("severity", "low"))
        normalized.append(
            {
                "id": alert.get("id", ""),
                "category": category,
                "category_label": _alert_category_label(category),
                "severity": severity,
                "severity_label": _alert_severity_label(severity),
                "title": alert.get("title", ""),
                "message": alert.get("message", ""),
                "evidence": alert.get("evidence", []),
                "source_flags": alert.get("source_flags", []),
            }
        )
    return normalized


def _alert_category_label(value: str) -> str:
    labels = {
        "market": "市場警告",
        "life": "生活影響警告",
        "memo": "補足メモ",
    }
    return labels.get(value, value)


def _alert_severity_label(value: str) -> str:
    labels = {
        "high": "重要",
        "moderate": "注意",
        "low": "監視",
    }
    return labels.get(value, value)


def _top_sector(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    row = rows[0]
    return {
        "ticker": row.get("ticker", "-"),
        "label": row.get("sector_name_ja", row.get("ticker", "-")),
        "return_12w": row.get("return_12w", "-"),
    }


def _top_asset(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    row = rows[0]
    return {
        "ticker": row.get("ticker", "-"),
        "label": row.get("ticker_name_ja", row.get("ticker", "-")),
        "momentum_12w": row.get("momentum_12w", "-"),
    }
