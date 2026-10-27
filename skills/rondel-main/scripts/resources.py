"""汇总本地登记的机器资源；不连接、预留或执行远程任务。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from datetime import UTC, datetime
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "rondel_resource_records", Path(__file__).with_name("records.py")
)
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)


def _nonnegative(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def inventory(
    workspace: Path,
    *,
    gpu_count: int = 0,
    gpu_memory_gb: float = 0,
    fresh_for_seconds: int = 3600,
    now: datetime | None = None,
) -> dict:
    """按观测筛选候选；可用性仍需在实际执行前复核。"""
    if (
        not isinstance(gpu_count, int)
        or _nonnegative(gpu_count) is None
        or _nonnegative(gpu_memory_gb) is None
        or fresh_for_seconds <= 0
    ):
        raise ValueError("Resource requirements must be nonnegative.")
    root = records.archive_root(workspace)
    project, _ = records.read_note(root / "init.md")
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("Resource observation time needs a timezone.")
    machines = []
    required_gpus = max(gpu_count, 1 if gpu_memory_gb else 0)
    identifiers = set()
    for path in sorted((root / "setup/resources").glob("*.md")):
        meta, _ = records.read_note(path)
        if meta.get("type") != "resource" or meta.get("purpose") != "machine":
            continue
        records.check_meta(meta)
        if meta.get("project_id") != project["project_id"]:
            raise ValueError("Machine record belongs to another project.")
        host = meta.get("host_id")
        if not isinstance(host, str) or not host.strip() or host in identifiers:
            raise ValueError("Machine host_id is missing or duplicated.")
        identifiers.add(host)
        reasons = []
        observation = meta.get("observation", {})
        if not isinstance(observation, dict):
            observation = {}
        age = None
        observed_at = observation.get("at")
        try:
            observed = datetime.fromisoformat(str(observation.get("at", "")))
            observed_at = observed.isoformat()
            if observed.tzinfo is not None:
                age = (now - observed).total_seconds()
        except ValueError:
            observed_at = str(observed_at) if observed_at is not None else None
        fresh = age is not None and 0 <= age <= fresh_for_seconds
        if meta["status"] != "checked":
            reasons.append("resource_not_checked")
        if not fresh:
            reasons.append("observation_missing_stale_or_future")
        availability = observation.get("availability", "unknown")
        if availability != "available":
            reasons.append("availability_not_confirmed")
        if not observation.get("source"):
            reasons.append("observation_source_missing")
        transport = meta.get("transport", "unknown")
        if transport not in {"local", "ssh", "scheduler"}:
            reasons.append("transport_not_supported")
        elif transport != "local" and not meta.get("connection_ref"):
            reasons.append("connection_reference_missing")
        devices = observation.get("gpus", [])
        if not isinstance(devices, list):
            devices = []
        qualified = []
        seen_devices = set()
        for device in devices:
            if not isinstance(device, dict):
                continue
            identifier = str(device.get("id", ""))
            if not identifier or identifier in seen_devices:
                reasons.append("gpu_identifiers_missing_or_duplicated")
                continue
            seen_devices.add(identifier)
            free = _nonnegative(device.get("free_memory_gb"))
            if device.get("available") is True and (
                not gpu_memory_gb
                or (free is not None and free >= gpu_memory_gb)
            ):
                qualified.append(identifier)
        if len(qualified) < required_gpus:
            reasons.append("insufficient_or_unknown_eligible_gpus")
        locations = meta.get("locations", {})
        if not isinstance(locations, dict) or any(
            not isinstance(value, str) for value in locations.values()
        ):
            raise ValueError("Machine locations must be target-system strings.")
        machines.append(
            {
                "host_id": host,
                "record_ref": "record:" + meta["id"],
                "display_name": meta["display_name"],
                "transport": transport,
                "system": meta.get("system", "unknown"),
                "locations": locations,
                "observed_at": observed_at,
                "availability": availability,
                "fresh": fresh,
                "eligible": not reasons,
                "candidate_gpu_ids": qualified[:required_gpus],
                "reasons": reasons,
                "requires_preflight": True,
            }
        )
    return {
        "schema_version": 1,
        "project_id": project["project_id"],
        "generated_at": now.isoformat(),
        "requirements": {
            "gpu_count": required_gpus,
            "gpu_memory_gb": gpu_memory_gb,
            "fresh_for_seconds": fresh_for_seconds,
        },
        "machines": machines,
        "candidate_hosts": [m["host_id"] for m in machines if m["eligible"]],
        "reservation_created": False,
    }


def save_summary(workspace: Path, relative: str, result: dict) -> Path:
    root = records.archive_root(workspace)
    target = records.within(root, relative)
    reports = root / ".state/resources"
    if (
        not target.is_relative_to(reports)
        or target == reports
        or target.suffix != ".json"
    ):
        raise ValueError(
            "Use a JSON file inside the .state/resources report directory."
        )
    records.atomic_write(
        target, json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect registered resources")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--gpu-count", type=int, default=0)
    parser.add_argument("--gpu-memory-gb", type=float, default=0)
    parser.add_argument("--fresh-for-seconds", type=int, default=3600)
    parser.add_argument("--out")
    args = parser.parse_args()
    try:
        result = inventory(
            args.root,
            gpu_count=args.gpu_count,
            gpu_memory_gb=args.gpu_memory_gb,
            fresh_for_seconds=args.fresh_for_seconds,
        )
        if args.out:
            target = save_summary(args.root, args.out, result)
            print("Resource summary:", target)
        print("Registered machines:", len(result["machines"]))
        print("Candidates requiring preflight:", len(result["candidate_hosts"]))
        return 0
    except (OSError, ValueError, TypeError) as error:
        print("Error:", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
