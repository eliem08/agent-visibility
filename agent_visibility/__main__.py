import argparse
import csv
import json
import os
import sys

from .core import MockPlatform, Project, alerts, load_history, metrics, run


def _print(m, brand):
    o = m["overall"]
    print(
        f"{brand}: mentioned in {o['mention_rate']:.0%} of answers, share of voice {o['share_of_voice']:.0%}, "
        f"avg rank {o['avg_rank']}, top-3 {o['top3_rate']:.0%}, sentiment {o['sentiment']:+.2f}"
    )
    for plat, pm in m["by_platform"].items():
        print(
            f"  {plat:<14} mention {pm['mention_rate']:.0%}  SoV {pm['share_of_voice']:.0%}  rank {pm['avg_rank']}  top3 {pm['top3_rate']:.0%}"
        )
    print("  top cited: " + ", ".join(f"{d} ({n})" for d, n in o["top_citations"]))


def build_parser():
    ap = argparse.ArgumentParser(prog="agent-visibility")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("project")
    r.add_argument("--history", default="history.jsonl")
    rep = sub.add_parser("report")
    rep.add_argument("history")
    rep.add_argument("--brand")
    return ap


def _run(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.cmd == "run":
        proj = Project.load(a.project)
        everyone = [proj.brand, *proj.competitors]
        rows = run(proj, [MockPlatform(p, everyone) for p in proj.platforms])
        prev = None
        if os.path.exists(a.history):
            runs = load_history(a.history)
            if runs:
                prev = metrics(list(runs.values())[-1], proj.brand)
        with open(a.history, "a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        m = metrics(rows, proj.brand)
        _print(m, proj.brand)
        for al in alerts(prev, m) if prev else []:
            print(f"  ALERT {al}")
        return 0
    runs = load_history(a.history)
    first = next(iter(runs.values()))
    brand = a.brand or next(iter(first[0]["entities"]))
    for ts, rows in runs.items():
        o = metrics(rows, brand)["overall"]
        print(f"{ts}  mention {o['mention_rate']:.0%}  SoV {o['share_of_voice']:.0%}  rank {o['avg_rank']}")
    return 0


def main(argv=None):
    """Run the CLI; a bad input file or argument exits 2 with a one-line error instead of a traceback.

    Set AGENT_ECONOMY_DEBUG=1 to see the full traceback.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        return _run(argv)
    except (OSError, ValueError, KeyError, csv.Error) as e:
        if os.environ.get("AGENT_ECONOMY_DEBUG"):
            raise
        msg = e.args[0] if isinstance(e, KeyError) and e.args else e
        print(f"error: {msg}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
