"""Logistics map — the service split into modules (split out of mapd.py on 2026-09-30).

  core      shared state (ST), database (DB), log, FRM status
  factory   item balance, block reason, publishing, history, factory clusters
  events    events with edge detection/hysteresis, change log, growth, storage warnings
  logistics fill levels, train throughput, round times, schedule check
  collect   loops: save, FRM factory, live, sink
  planner   production planner integration (/api/plan)
  http      website + API
"""
