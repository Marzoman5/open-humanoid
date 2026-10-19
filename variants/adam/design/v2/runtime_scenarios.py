"""Software-in-the-loop acceptance scenarios (openhumanoid.runtime.scenarios, the 18 of docs/software.md) on a v2 concept.

`python -m openhumanoid.runtime scenarios` always uses the module's DEFAULT_CONCEPT (R1-P1r): its --concept option is not passed to the
scenario functions (toolkit gap, reported in the R2a-v2 review). This wrapper reads the concept from a config copy and puts that robot
model into the scenarios' model cache under the default key, so every scenario runs on it. Nothing in openhumanoid/ is changed.

Run:  .venv/Scripts/python variants/adam/design/v2/runtime_scenarios.py [--config variants/adam/design/v2/runtime-adam-v2.yaml] [--concept X.yaml]
Out:  variants/adam/design/v2/results/runtime_<concept id>.{txt,json}
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "runtime-adam-v2.yaml"))
    ap.add_argument("--concept", default=None, help="overrides the config's concept")
    ap.add_argument("names", nargs="*")
    a = ap.parse_args(argv)
    from openhumanoid.runtime import scenarios as S
    from openhumanoid.runtime.config import load_config
    from openhumanoid.runtime.model import RobotModel
    cfg = load_config(a.config)
    concept = a.concept or cfg["concept"]
    S._MODEL_CACHE[S.DEFAULT_CONCEPT] = RobotModel.from_concept(concept)
    names = a.names or list(S.ALL)
    rows, fails, lines = [], 0, []
    for n in names:
        t0 = time.time()
        r = S.ALL[n]()
        for x in (r if isinstance(r, list) else [r]):
            line = x.row() + f"   [{time.time() - t0:.0f} s]"
            print(line, flush=True)
            lines.append(line)
            rows.append({"name": getattr(x, "name", n), "passed": bool(x.passed), "row": x.row()})
            fails += 0 if x.passed else 1
    cid = Path(concept).stem
    out = HERE / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"runtime_{cid}.txt").write_text(f"concept: {concept}\n" + "\n".join(lines) + f"\n{fails} failing of {len(rows)}\n", encoding="utf-8")
    (out / f"runtime_{cid}.json").write_text(json.dumps({"concept": concept, "n": len(rows), "failing": fails, "rows": rows}, indent=1), encoding="utf-8")
    print(f"{fails} failing of {len(rows)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
