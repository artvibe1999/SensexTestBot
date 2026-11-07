"""Greedy portfolio build on the train period with the screen3 portfolio replay.

usage: python scripts/greedy.py DATA MEMBERS_JSON OUT_JSON [workers]
MEMBERS_JSON: {"name": [family, params], ...}. Start from "start" names (if given in the
file under "_start"), then repeatedly append (lowest priority) the member that adds the most
train-period net; every step's full/holdout result is recorded so the holdout is only read.
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
import screen3 as S3  # noqa: E402


def evaluate(names_members):
    names, members = names_members
    return names, S3.summarize(S3.portfolio(members))


if __name__ == "__main__":
    data, mem_p, out_p = sys.argv[1:4]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 9
    spec = json.load(open(mem_p))
    start = spec.pop("_start", [])
    pool = {k: v for k, v in spec.items()}
    chosen = list(start)
    steps = []
    with ProcessPoolExecutor(max_workers=workers, initializer=S3.init, initargs=(data,)) as ex:
        while True:
            cands = [n for n in pool if n not in chosen]
            if not cands:
                break
            jobs = [(chosen + [n], [[x, *pool[x]] for x in chosen + [n]]) for n in cands]
            res = list(ex.map(evaluate, jobs))
            best = max(res, key=lambda r: r[1]["train"]["net"])
            chosen = best[0]
            s = best[1]
            steps.append({"members": list(chosen), "summary": s})
            print(len(chosen), chosen[-1], "| train", s["train"]["net"], s["train"]["pf"], s["train"]["dd"], "| hold",
                  s["holdout"]["net"], s["holdout"]["pf"], s["holdout"]["dd"], "|", s["years"], flush=True)
            json.dump(steps, open(out_p, "w"), indent=1, default=str)
