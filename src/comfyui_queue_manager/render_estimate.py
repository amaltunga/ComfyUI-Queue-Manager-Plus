"""Estimate a waiting job from the latest finished run of the same workflow."""

import json
import math

from .job_fields import read_job_fields
from .qm_db import read_query, read_single

_CACHE = {}
_CACHE_LIMIT = 256


def clear_render_estimate_cache():
    _CACHE.clear()


def attach_render_estimates(jobs):
    """Set estimated_time on pending or archived items. A first run stays blank."""
    grouped = {}
    for workflow_id, item in jobs:
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            continue
        if not isinstance(item, (list, tuple)) or len(item) < 4 or not isinstance(item[3], dict):
            continue
        duration = _job_duration(item)
        grouped.setdefault(workflow_id, []).append((item[3], duration))

    for workflow_id, entries in grouped.items():
        runs = finished_runs(workflow_id)
        if not runs:
            continue
        for extra, duration in entries:
            match = _latest_match(runs, duration)
            if match is None:
                continue
            seconds, basis = match
            extra["estimated_time"] = seconds
            extra["estimate_match"] = basis


def finished_runs(workflow_id):
    """Newest finished runs first, as (seconds, duration key or None)."""
    stamp = read_single(
        """
        SELECT MAX(queue.updated_at) AS stamp, COUNT(queue.id) AS total
        FROM queue
        INNER JOIN meta AS exec_time
            ON queue.id = exec_time.item_id AND exec_time.key = 'execution_time'
        WHERE queue.status = 2 AND queue.workflow_id = ?
        """,
        (workflow_id,),
    )
    key = (stamp["stamp"] if stamp else None, int(stamp["total"]) if stamp else 0)
    cached = _CACHE.get(workflow_id)
    if cached is not None and cached[0] == key:
        return cached[1]

    rows = read_query(
        """
        SELECT queue.prompt, exec_time.value AS execution_time
        FROM queue
        INNER JOIN meta AS exec_time
            ON queue.id = exec_time.item_id AND exec_time.key = 'execution_time'
        WHERE queue.status = 2 AND queue.workflow_id = ?
        ORDER BY queue.updated_at DESC, queue.id DESC
        """,
        (workflow_id,),
    )
    runs = []
    for row in rows:
        seconds = _seconds(row["execution_time"])
        if seconds is None:
            continue
        runs.append((seconds, _duration_key(_prompt_duration(row["prompt"]))))
    if len(_CACHE) >= _CACHE_LIMIT:
        _CACHE.clear()
    _CACHE[workflow_id] = (key, runs)
    return runs


def _latest_match(runs, duration):
    if not runs:
        return None
    key = _duration_key(duration)
    if key is None:
        return runs[0][0], "workflow"
    for seconds, run_key in runs:
        if run_key == key:
            return seconds, "duration"
    return None


def _job_duration(item):
    """Seconds for this job. The executed float wins over a stale subgraph widget."""
    duration = read_job_fields(item).get("duration")
    if duration is not None:
        return duration
    return _subgraph_duration(item)


def _subgraph_duration(item):
    if not isinstance(item, (list, tuple)) or len(item) < 4 or not isinstance(item[3], dict):
        return None
    graph = item[2] if isinstance(item[2], dict) else {}
    pnginfo = item[3].get("extra_pnginfo")
    workflow = pnginfo.get("workflow") if isinstance(pnginfo, dict) else None
    definitions = workflow.get("definitions") if isinstance(workflow, dict) else None
    subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
    if not isinstance(subgraphs, list):
        return None
    inner_ids = set()
    for subgraph in subgraphs:
        if not isinstance(subgraph, dict):
            continue
        for node in subgraph.get("nodes") or []:
            if not isinstance(node, dict) or node.get("type") != "PrimitiveFloat":
                continue
            title = node.get("title")
            if isinstance(title, str) and "duration" in title.casefold():
                inner_ids.add(str(node.get("id")))
    if not inner_ids:
        return None
    found = []
    for node_id, api_node in graph.items():
        if not isinstance(api_node, dict) or api_node.get("class_type") != "PrimitiveFloat":
            continue
        if str(node_id).split(":")[-1] not in inner_ids:
            continue
        inputs = api_node.get("inputs") if isinstance(api_node.get("inputs"), dict) else {}
        value = inputs.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            continue
        found.append(float(value))
    if not found:
        return None
    if any(round(value, 3) != round(found[0], 3) for value in found):
        return None
    return found[0]


def _prompt_duration(prompt_text):
    try:
        item = json.loads(prompt_text)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(item, (list, tuple)):
        return None
    return _job_duration(item)


def _duration_key(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, 3)


def _seconds(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number
