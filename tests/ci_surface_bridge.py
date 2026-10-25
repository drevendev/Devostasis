"""R11–R53 drivers: native projection and real governed/store executions."""

from copy import deepcopy

from devostasis import canonical
from devostasis.adapters import ci
from devostasis.bundle import verify_dir
from devostasis.config import single_project
from devostasis.delta import compare
from devostasis.gauges import gauge_for
from devostasis.history import FilesystemHistoryStore
from devostasis.observations import Observation
from devostasis.runner import build_from_observations
from devostasis.vitals import clutter
from helpers import SUBJECT, finalize, obs_set


def consumer(given, root):
    ci.fields(given, ("observed_at", "observations"))
    obs = obs_set(given["observed_at"])
    for row in given["observations"]:
        obs.add(Observation(**row))
    result = clutter.evaluate(obs).to_dict()
    previous = {**deepcopy(result), "evaluation_status": "AVAILABLE", "band_semantics": "EXACT", "band": "CLEAN"}
    delta = compare({"vitals": [result]}, {"vitals": [previous]}, "COMPARABLE", "synthetic-predecessor")
    return {"result": result, "gauge": gauge_for(result),
            "delta": next(row for row in delta["vitals"] if row["vital_id"] == "clutter")}


def revisions(given, root):
    ci.fields(given, ("variants",))
    ci.require(isinstance(given["variants"], list) and given["variants"], "CI variants required")
    variants = {}
    for variant in given["variants"]:
        ci.fields(variant, ("name", "steps"))
        name = ci.text(variant["name"])
        ci.require(name not in variants, "duplicate CI variant")
        ci.require(isinstance(variant["steps"], list) and variant["steps"], "CI scenario steps required")
        store = FilesystemHistoryStore(root / str(len(variants)))
        project, checkpoints, previous_path = single_project("acme/widget", config_version="1"), [], None
        for step in variant["steps"]:
            ci.fields(step, ("history", "evidence"))
            ci.require(step["history"] in ("BASELINE", "CONTINUE", "GAP"), "unknown history operation")
            ci.require((previous_path is None) == (step["history"] == "BASELINE"), "history baseline must be explicit and first")
            if step["history"] == "GAP":
                # Retention/provenance loss is an actual broken predecessor,
                # never a made-up current snapshot or a fresh BASELINE.
                (previous_path / "snapshot.json").unlink()
            subject = {**SUBJECT, **step["evidence"]["project"]}
            obs = finalize(ci.observations(step["evidence"], subject))
            normalized = ci.normalize(step["evidence"])
            bundle = build_from_observations(project, obs, store)
            previous_path = store.commit(bundle)
            snapshot = canonical.loads(bundle.members["snapshot.json"].decode())
            result = next(v for v in snapshot["vitals"] if v["vital_id"] == "integrity")
            current = {r["revision"]: r for r in normalized["records"]}
            history = {r["revision"]: r for r in result["derived"]["revision_history"]["records"]}
            checkpoints.append({"normalization": normalized["metadata"], "current": current, "history": history,
                "integrity": result, "comparison": bundle.manifest["comparison_status"], "verified": verify_dir(previous_path) == [],
                "current_revision_count": len(current),
                "current_decisive_count": sum(r["current_verdict"] in ("VERIFY_PASS", "VERIFY_FAIL") for r in current.values()),
                "current_failed_count": sum(r["current_verdict"] == "VERIFY_FAIL" for r in current.values())})
        variants[name] = {"steps": checkpoints}
    return variants
