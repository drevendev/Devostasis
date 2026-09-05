"""Command-line interface."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, canonical, timeutil
from .adapters.github import CollectionError, GitHubClient, UrllibTransport
from .bundle import verify_dir, load_bundle_dir
from .config import ConfigError, load_config, single_project
from .history import FilesystemHistoryStore
from .observations import ObservationSet
from .runner import build_from_observations, evaluate, observe, run_all, write_fleet_index
from . import render

TOKEN_ENVS = ("DEVOSTASIS_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")


def resolve_token(explicit: str | None, extra_env: str | None = None) -> tuple[str | None, str]:
    if explicit:
        return explicit, "argument"
    names = ([extra_env] if extra_env else []) + list(TOKEN_ENVS)
    for name in names:
        value = os.environ.get(name)
        if value:
            return value, f"env:{name}"
    gh = shutil.which("gh")
    if gh:
        try:
            result = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=15, check=False)
            token = result.stdout.strip()
            if result.returncode == 0 and token:
                return token, "gh auth token"
        except (OSError, subprocess.SubprocessError):
            pass
    return None, "none (unauthenticated: public repositories only, low rate limit)"


def _now(value: str | None):
    return timeutil.parse_ts(value) if value else timeutil.now_utc()


def _bands_line(bands: dict[str, str | None]) -> str:
    order = ("pulse", "flow", "integrity", "clutter", "horizon", "direction", "debt")
    return " ".join(f"{name}={bands.get(name) or 'UNKNOWN'}" for name in order)


def cmd_observe(args: argparse.Namespace) -> int:
    token, source = resolve_token(args.token)
    project = single_project(args.repo, planning={"source": args.planning}, debt=_debt_from_args(args))
    client = GitHubClient(UrllibTransport(token))
    print(f"token: {source}", file=sys.stderr)
    try:
        obs = observe(project, client, _now(args.now))
    except CollectionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    obs.save(args.out)
    print(f"observations: {args.out} ({len(obs)} keys, {client.request_count} requests)")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    obs = ObservationSet.load(args.observations)
    project = single_project(f"{obs.subject.get('owner', 'unknown')}/{obs.subject.get('repo', 'unknown')}") if args.derive else None
    snapshot = evaluate(obs, project)
    canonical.write_pretty(args.out, snapshot)
    bands = {item["vital_id"]: item["band"] for item in snapshot["vitals"]}
    print(f"snapshot: {args.out}")
    print(_bands_line(bands))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except (ConfigError, OSError, ValueError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    token, source = resolve_token(args.token, config.token_env)
    print(f"token: {source}", file=sys.stderr)
    store = FilesystemHistoryStore(args.store or config.store_path)
    outcomes = run_all(config, store, token, _now(args.now), only=args.project or None, user_agent=config.user_agent)
    failed = 0
    for outcome in outcomes:
        if outcome.ok:
            print(f"[ok] {outcome.locator}: {outcome.comparison_status} bundle {outcome.bundle_id[:12]} ({outcome.requests} requests)")
            print(f"     {_bands_line(outcome.bands)}")
        else:
            failed += 1
            print(f"[failed] {outcome.locator}: {outcome.error}")
    print(f"store: {store.root}")
    return 1 if failed else 0


def cmd_build(args: argparse.Namespace) -> int:
    """Build and persist a bundle from a saved observation set (offline)."""
    obs = ObservationSet.load(args.observations)
    project = single_project(f"{obs.subject.get('owner', 'unknown')}/{obs.subject.get('repo', 'unknown')}", planning={"source": args.planning}, debt=_debt_from_args(args))
    from .normalize import derive
    derive(obs, project)
    store = FilesystemHistoryStore(args.store)
    bundle = build_from_observations(project, obs, store)
    path = store.commit(bundle, bundle.bands())
    write_fleet_index(store)
    print(f"bundle {bundle.bundle_id[:12]} ({bundle.manifest['comparison_status']}) written to {path}")
    print(_bands_line(bundle.bands()))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    problems = verify_dir(args.bundle)
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
    print("verified: digests, identity preimage, persisted effective config and report reproducibility all match")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    members = load_bundle_dir(args.bundle)
    manifest = canonical.loads(members["manifest.json"].decode("utf-8"))
    snapshot = canonical.loads(members["snapshot.json"].decode("utf-8"))
    delta = canonical.loads(members["delta.json"].decode("utf-8"))
    activity = canonical.loads(members["activity.json"].decode("utf-8")) if "activity.json" in members else None
    sys.stdout.write(render.render_report(manifest, snapshot, delta, activity))
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    path = write_fleet_index(FilesystemHistoryStore(args.store))
    print(f"fleet overview: {path}" if path else "no projects in store")
    return 0


def _debt_from_args(args: argparse.Namespace):
    labels = getattr(args, "debt_label", None)
    if not labels:
        return None
    return {"labels": list(labels), "mapping_version": getattr(args, "debt_mapping_version", None) or "cli-1"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devostasis", description="Deterministic, model-free vital signs for software repositories.")
    parser.add_argument("--version", action="version", version=f"devostasis {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    observe_p = sub.add_parser("observe", help="collect a read-only observation set for one repository")
    observe_p.add_argument("--repo", required=True, help="owner/name")
    observe_p.add_argument("--out", default="observations.json")
    observe_p.add_argument("--token")
    observe_p.add_argument("--now", help="observation timestamp (RFC 3339) for reproducible runs")
    observe_p.add_argument("--planning", choices=("milestones", "none"), default="milestones")
    observe_p.add_argument("--debt-label", action="append", help="issue label that marks a registered debt item (repeatable)")
    observe_p.add_argument("--debt-mapping-version")
    observe_p.set_defaults(func=cmd_observe)

    eval_p = sub.add_parser("evaluate", help="evaluate the seven Vitals from a saved observation set")
    eval_p.add_argument("--observations", required=True)
    eval_p.add_argument("--out", default="snapshot.json")
    eval_p.add_argument("--derive", action="store_true", help="derive aggregates from inventories before evaluating")
    eval_p.set_defaults(func=cmd_evaluate)

    run_p = sub.add_parser("run", help="observe, evaluate, compare and persist bundles for every configured project")
    run_p.add_argument("--config", required=True)
    run_p.add_argument("--store", help="history store root (defaults to store.path in the config)")
    run_p.add_argument("--token")
    run_p.add_argument("--now")
    run_p.add_argument("--project", action="append", help="limit to owner/name (repeatable)")
    run_p.set_defaults(func=cmd_run)

    build_p = sub.add_parser("build", help="build and persist a bundle from a saved observation set (offline)")
    build_p.add_argument("--observations", required=True)
    build_p.add_argument("--store", required=True)
    build_p.add_argument("--planning", choices=("milestones", "none"), default="milestones")
    build_p.add_argument("--debt-label", action="append")
    build_p.add_argument("--debt-mapping-version")
    build_p.set_defaults(func=cmd_build)

    verify_p = sub.add_parser("verify", help="verify digests, identity and report reproducibility of a bundle directory")
    verify_p.add_argument("--bundle", required=True)
    verify_p.set_defaults(func=cmd_verify)

    render_p = sub.add_parser("render", help="re-render report.md from a bundle directory to stdout")
    render_p.add_argument("--bundle", required=True)
    render_p.set_defaults(func=cmd_render)

    index_p = sub.add_parser("index", help="regenerate the fleet overview of a store")
    index_p.add_argument("--store", required=True)
    index_p.set_defaults(func=cmd_index)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
