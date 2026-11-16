"""Queued and archived jobs estimate from the latest matching finished run."""

import heapq
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import threading
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from src.comfyui_queue_manager import qm_db
from src.comfyui_queue_manager.render_estimate import clear_render_estimate_cache


@pytest.fixture
def estimate_queue(monkeypatch):
    for name, attributes in {
        "execution": {"PromptQueue": type("PromptQueue", (), {})},
        "server": {"PromptServer": type("PromptServer", (), {})},
        "folder_paths": {},
    }.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    path = Path(__file__).parents[1] / "src/comfyui_queue_manager/qm_queue.py"
    spec = importlib.util.spec_from_file_location("src.comfyui_queue_manager._render_estimate_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clear_render_estimate_cache()
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        monkeypatch.setattr(qm_db, "get_conn", lambda: conn)
        monkeypatch.setattr(module, "get_conn", lambda: conn)
        qm_db.init_schema()
        queue = module.QM_Queue.__new__(module.QM_Queue)
        queue.paused = False
        queue.takeover_client = None
        queue.restored = True
        native = SimpleNamespace(mutex=threading.RLock(), queue=[], currently_running={}, task_counter=1)
        native.not_empty = threading.Condition(native.mutex)
        queue.native_queue = native
        queue.pause_lock = threading.Condition(native.mutex)
        queue.original_put = Mock(side_effect=lambda item: heapq.heappush(native.queue, item))
        queue.original_get = Mock(side_effect=lambda timeout: (heapq.heappop(native.queue), native.task_counter))
        queue.original_task_done = Mock()
        module.PromptServer.instance = SimpleNamespace(send_sync=Mock(), queue_updated=Mock(), prompt_queue=native, number=100)
        yield queue
    clear_render_estimate_cache()


def studio_job(number, workflow_id="studio-still", prompt="a red bicycle on a grey studio floor", duration=4, name="Studio still"):
    nodes = [{"id": 1, "type": "CLIPTextEncode", "title": "Positive", "widgets_values": [prompt]}]
    graph = {"1": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt}}}
    if duration is not None:
        nodes.append({"id": 2, "type": "PrimitiveFloat", "title": "Float (Duration)", "widgets_values": [duration]})
        graph["2"] = {"class_type": "PrimitiveFloat", "inputs": {"value": duration}}
    extra = {"extra_pnginfo": {"workflow": {"id": workflow_id, "workflow_name": name, "nodes": nodes}}}
    return [number, f"{number:08d}-job", graph, extra, ["1"]]


def store(item, workflow_id, status, updated_at, execution_time=None):
    qm_db.write_query(
        """
        INSERT INTO queue (prompt_id, number, name, workflow_id, prompt, status, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (item[1], item[0], "Studio still", workflow_id, json.dumps(item), status, updated_at),
    )
    if execution_time is not None:
        row_id = qm_db.read_single("SELECT id FROM queue WHERE prompt_id = ?", (item[1],))["id"]
        qm_db.write_query(
            "INSERT INTO meta (item_id, key, value) VALUES (?, 'execution_time', ?)",
            (row_id, str(execution_time)),
        )


def listed(queue, route):
    _running, pending = queue.get_current_queue(page_size=50, route=route)
    return pending


def test_same_workflow_and_duration_uses_the_latest_finish(estimate_queue):
    store(studio_job(1, prompt="a red bicycle on a grey studio floor", duration=4), "studio-still", 2, "2026-11-16 10:00:00", 10)
    store(studio_job(2, prompt="a yellow bicycle on a grey studio floor", duration=4), "studio-still", 2, "2026-11-16 11:00:00", 12.5)
    store(studio_job(3, prompt="a blue kettle on a wooden table", duration=6), "studio-still", 2, "2026-11-16 12:00:00", 30)
    store(studio_job(4, prompt="a red bicycle against a white wall", duration=4), "studio-still", 0, "2026-11-16 13:00:00")
    store(studio_job(5, prompt="a blue kettle on a wooden table", duration=6), "studio-still", 0, "2026-11-16 13:00:01")
    store(studio_job(6, prompt="a green bottle on a shelf", duration=8), "studio-still", 0, "2026-11-16 13:00:02")
    store(studio_job(7, prompt="a quiet street after rain", duration=None, workflow_id="studio-still", name="Studio still"), "studio-still", 0, "2026-11-16 13:00:03")
    store(studio_job(8, workflow_id="street-scene", prompt="sunlight through a tall window", duration=8, name="Street scene"), "street-scene", 0, "2026-11-16 13:00:04")

    pending = {item[1]: item[3] for item in listed(estimate_queue, "queue")}
    assert pending["00000004-job"]["estimated_time"] == 12.5
    assert pending["00000004-job"]["estimate_match"] == "duration"
    assert "execution_time" not in pending["00000004-job"]
    assert pending["00000005-job"]["estimated_time"] == 30
    assert pending["00000005-job"]["estimate_match"] == "duration"
    assert "estimated_time" not in pending["00000006-job"]
    assert pending["00000007-job"]["estimated_time"] == 30
    assert pending["00000007-job"]["estimate_match"] == "workflow"
    assert "estimated_time" not in pending["00000008-job"]


def test_duration_match_ignores_a_newer_different_duration_and_integer_float(estimate_queue):
    store(studio_job(1, duration=4), "studio-still", 2, "2026-11-16 10:00:00", 10)
    store(studio_job(2, duration=6), "studio-still", 2, "2026-11-16 12:00:00", 30)
    store(studio_job(3, duration=4.0), "studio-still", 0, "2026-11-16 13:00:00")
    pending = listed(estimate_queue, "queue")
    assert pending[0][3]["estimated_time"] == 10
    assert pending[0][3]["estimate_match"] == "duration"


def test_failed_finish_does_not_invent_a_time(estimate_queue):
    store(studio_job(1, duration=4), "studio-still", 2, "2026-11-16 10:00:00", None)
    store(studio_job(2, duration=4), "studio-still", 0, "2026-11-16 11:00:00")
    assert "estimated_time" not in listed(estimate_queue, "queue")[0][3]

    store(studio_job(3, duration=4), "studio-still", 2, "2026-11-16 09:00:00", 8)
    clear_render_estimate_cache()
    pending = {item[1]: item[3] for item in listed(estimate_queue, "queue")}
    assert pending["00000002-job"]["estimated_time"] == 8


def test_archived_job_uses_the_same_estimate(estimate_queue):
    store(studio_job(1, duration=4), "studio-still", 2, "2026-11-16 10:00:00", 10)
    store(studio_job(2, prompt="a yellow bicycle on a grey studio floor", duration=4), "studio-still", 3, "2026-11-16 11:00:00")
    archived = listed(estimate_queue, "archive")
    assert archived[0][3]["estimated_time"] == 10
    assert archived[0][3]["estimate_match"] == "duration"


def test_completed_job_keeps_measured_time(estimate_queue):
    store(studio_job(1, duration=4), "studio-still", 2, "2026-11-16 10:00:00", 10)
    completed = listed(estimate_queue, "completed")
    assert completed[0][3]["execution_time"] == 10
    assert "estimated_time" not in completed[0][3]


def test_completion_feeds_the_next_queued_job(estimate_queue):
    first = studio_job(1, prompt="a red bicycle on a grey studio floor", duration=4)
    estimate_queue.queue_put(tuple(first))
    queued, item_id = estimate_queue.queue_get()
    estimate_queue.native_queue.currently_running[item_id] = queued
    status = ("success", True, [("execution_start", {"timestamp": 1000}), ("execution_success", {"timestamp": 11500})])
    estimate_queue.task_done(item_id, {"outputs": {}}, status)
    estimate_queue.native_queue.currently_running.pop(item_id, None)

    second = studio_job(2, prompt="a yellow bicycle on a grey studio floor", duration=4)
    estimate_queue.queue_put(tuple(second))
    pending = listed(estimate_queue, "queue")
    assert len(pending) == 1
    assert pending[0][1] == second[1]
    assert pending[0][3]["estimated_time"] == 10.5
    assert pending[0][3]["estimate_match"] == "duration"

    db_id = pending[0][3]["db_id"]
    assert estimate_queue.archive_items([db_id]) == 1
    archived = listed(estimate_queue, "archive")
    assert archived[0][3]["estimated_time"] == 10.5

    _running, completed = estimate_queue.get_current_queue(page_size=20, route="completed")
    assert completed[0][3]["execution_time"] == 10.5
    assert "estimated_time" not in completed[0][3]


def subgraph_job(number, seconds, workflow_id="studio-still", prompt_id=None):
    """Duration lives on the executed subgraph float. The widget value is not the duration."""
    graph = {
        "105:111": {"class_type": "PrimitiveFloat", "inputs": {"value": seconds}},
        "105:104": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"length": ["105:107", 0]}},
    }
    workflow = {
        "id": workflow_id,
        "workflow_name": "Studio still",
        "nodes": [{"id": 105, "type": "4c314f31-ecda-4b08-ae98-faaba1bf613f", "title": "Image to Video"}],
        "definitions": {
            "subgraphs": [
                {
                    "id": "4c314f31-ecda-4b08-ae98-faaba1bf613f",
                    "nodes": [
                        {
                            "id": 111,
                            "type": "PrimitiveFloat",
                            "title": "Float (duration)",
                            "widgets_values": [2],
                        }
                    ],
                }
            ]
        },
    }
    return [number, prompt_id or f"{number:08d}-sub", graph, {"extra_pnginfo": {"workflow": workflow}}, []]


def test_subgraph_duration_ignores_a_newer_different_length(estimate_queue):
    store(subgraph_job(1, 10.0), "studio-still", 2, "2026-11-16 10:00:00", 356.716)
    store(subgraph_job(2, 8.000000000000007), "studio-still", 2, "2026-11-16 11:00:00", 259.169)
    store(subgraph_job(3, 8), "studio-still", 0, "2026-11-16 12:00:00")
    store(subgraph_job(4, 10), "studio-still", 0, "2026-11-16 12:00:01")
    store(subgraph_job(5, 12), "studio-still", 0, "2026-11-16 12:00:02")
    store(studio_job(6, prompt="a quiet street after rain", duration=None, name="Studio still"), "studio-still", 0, "2026-11-16 12:00:03")

    pending = {item[1]: item[3] for item in listed(estimate_queue, "queue")}
    assert pending["00000003-sub"]["estimated_time"] == 259.169
    assert pending["00000003-sub"]["estimate_match"] == "duration"
    assert pending["00000004-sub"]["estimated_time"] == 356.716
    assert pending["00000004-sub"]["estimate_match"] == "duration"
    assert "estimated_time" not in pending["00000005-sub"]
    assert pending["00000006-job"]["estimated_time"] == 259.169
    assert pending["00000006-job"]["estimate_match"] == "workflow"


def test_a_later_finish_replaces_the_cached_estimate(estimate_queue):
    store(studio_job(1, duration=4), "studio-still", 2, "2026-11-16 10:00:00", 10)
    store(studio_job(2, duration=4), "studio-still", 0, "2026-11-16 10:05:00")
    assert listed(estimate_queue, "queue")[0][3]["estimated_time"] == 10
    store(studio_job(3, prompt="a yellow bicycle on a grey studio floor", duration=4), "studio-still", 2, "2026-11-16 10:10:00", 18)
    assert listed(estimate_queue, "queue")[0][3]["estimated_time"] == 18
