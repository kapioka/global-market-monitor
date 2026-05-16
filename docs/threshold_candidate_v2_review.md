# Threshold Candidate V2 Review

Updated: 2026-05-15 JST

## Decision

`diagnostic_only`

candidate_v2 is useful for diagnostics, but it is not certified for final action in v0.7.0.

## Candidate V2 Components

- family cap: `CL=F` and `BZ=F` share `commodity_oil`; oil family severity is counted once.
- multi-family extreme confirmation: extreme requires multiple critical families or very high composite score.
- stage jump limiter: normal to extreme is blocked unless strong multi-family evidence exists.
- fallback isolation: fallback/review-derived rules must not drive final action.

## Replay Finding

The earlier proposed set changed:

- active: `wait 60 / watch 7 / buy_window 0`
- proposed: `wait 67 / watch 0 / buy_window 0`

candidate policies reduce some severity labels, but current evidence does not restore reliable action balance or prove better forward returns.

## Current Status

- final action impact: `false`
- certification: not granted
- next requirement: longer history with completed 13w / 26w / 52w outcomes and buy_window cases
