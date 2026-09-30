"""Logistikkarte — Dienst in Modulen (aus mapd.py aufgeteilt am 30.09.2026).

  core      gemeinsamer Zustand (ST), Datenbank (DB), Log, FRM-Status
  factory   Warenbilanz, Blockadegrund, Veröffentlichen, Verlauf, Fabrik-Cluster
  events    Ereignisse mit Flanke/Hysterese, Änderungsprotokoll, Wachstum, Lager-Warnungen
  logistics Füllstände, Zugdurchsatz, Rundenzeiten, Fahrplan-Prüfung
  collect   Takte: Save, FRM-Fabrik, Live, Sink
  planner   Produktionsrechner-Anbindung (/api/plan)
  http      Website + API
"""
