"""Edit the prompt and MiniMax duration stored on a queued workflow."""

import json

_MISSING = object()

DURATION_MIN = 1
DURATION_MAX = 15


def read_job_fields(item):
    prompt, nodes, _workflow = _parts(item)
    text, editable = _read_prompt(prompt, nodes)
    seconds, duration_editable = _read_duration(prompt, nodes)
    workflow_name = _workflow_name(item)
    return {
        "name": workflow_name,
        "prompt": text,
        "prompt_editable": editable,
        "duration": seconds,
        "duration_editable": duration_editable,
        "duration_min": DURATION_MIN,
        "duration_max": DURATION_MAX,
    }


def apply_job_fields(item, prompt=_MISSING, duration=_MISSING):
    """Mutate a queue tuple. Raises ValueError when a requested field cannot be saved."""
    graph, nodes, workflow = _parts(item)
    if prompt is not _MISSING:
        if not isinstance(prompt, str):
            raise ValueError("Prompt must be text")
        if len(prompt) > 20000:
            raise ValueError("Prompt is too long")
        _write_prompt(graph, nodes, prompt)
    if duration is not _MISSING:
        seconds = _validate_duration(duration)
        _write_duration(graph, nodes, workflow, seconds)
    return read_job_fields(item)


def _parts(item):
    graph = item[2] if len(item) > 2 and isinstance(item[2], dict) else {}
    extra = item[3] if len(item) > 3 and isinstance(item[3], dict) else {}
    pnginfo = extra.get("extra_pnginfo")
    workflow = pnginfo.get("workflow") if isinstance(pnginfo, dict) else None
    if not isinstance(workflow, dict):
        workflow = {}
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        nodes = []
    return graph, nodes, workflow


def _workflow_name(item):
    _graph, _nodes, workflow = _parts(item)
    name = workflow.get("workflow_name")
    if isinstance(name, str) and name.strip():
        return name
    extra = item[3] if len(item) > 3 and isinstance(item[3], dict) else {}
    stored = extra.get("queue_manager")
    if isinstance(stored, dict) and isinstance(stored.get("name"), str):
        return stored["name"]
    return ""


def _title(node):
    title = node.get("title")
    return title.casefold() if isinstance(title, str) else ""


def _api_node(graph, node_id):
    node = graph.get(str(node_id))
    return node if isinstance(node, dict) else None


def _inputs(api_node):
    inputs = api_node.get("inputs") if isinstance(api_node, dict) else None
    return inputs if isinstance(inputs, dict) else {}


def _widget(node, index):
    values = node.get("widgets_values")
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None


def _set_widget(node, index, value):
    values = node.get("widgets_values")
    if not isinstance(values, list):
        values = []
        node["widgets_values"] = values
    while len(values) <= index:
        values.append("")
    values[index] = value


_TEXT_KEYS = ("prompt_text", "positive_text", "prompt", "text", "value")
_PASS_THROUGH = {"A1111AppendNegativeToPrompt", "A1111JoinPrompts", "A1111NegativePrompt"}
_WIDGET_INDEX = {
    "MiniMaxH3PromptBuilder": {"prompt_text": 0, "builder_state": 1},
    "PrimitiveString": {"value": 0},
    "PrimitiveStringMultiline": {"value": 0},
    "PrimitiveFloat": {"value": 0},
    "CLIPTextEncode": {"text": 0},
    "A1111PromptStyle": {"style": 0, "prompt": 1, "positive_text": 2, "style_negative": 3, "extra_negative": 4},
    "A1111AppendNegativeToPrompt": {"style": 0, "negative_text": 1, "extra_negative": 2},
}


def _ui_nodes(nodes):
    return {str(node.get("id")): node for node in nodes if isinstance(node, dict)}


def _bypassed(ui_node):
    return isinstance(ui_node, dict) and ui_node.get("mode") in (2, 4)


def _is_link(value):
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], (str, int))
        and not isinstance(value[0], bool)
        and isinstance(value[1], int)
    )


def _text_field(api_node):
    """The prompt field on this node, or a link to follow upstream."""
    inputs = _inputs(api_node)
    for key in _TEXT_KEYS:
        if key not in inputs:
            continue
        value = inputs[key]
        if key == "value" and not _is_link(value):
            class_type = str(api_node.get("class_type") or "")
            if "String" not in class_type:
                continue
        if _is_link(value):
            return key, value
        if isinstance(value, str):
            if key == "positive_text" and not value.strip() and isinstance(inputs.get("prompt"), str):
                continue
            return key, value
    return None


def _follow_text(graph, node_id, seen):
    node_key = str(node_id)
    if node_key in seen:
        return None
    seen.add(node_key)
    api_node = _api_node(graph, node_key)
    if api_node is None:
        return None
    found = _text_field(api_node)
    if found is None:
        return None
    key, value = found
    if _is_link(value):
        return _follow_text(graph, value[0], seen)
    return node_key, key


def _link_roles(graph, node_id):
    roles = set()
    target = str(node_id)
    for api_node in graph.values():
        if not isinstance(api_node, dict):
            continue
        for name, value in _inputs(api_node).items():
            if _is_link(value) and str(value[0]) == target:
                roles.add(name)
    return roles


def _sink_score(api_node, ui_node):
    if _bypassed(ui_node):
        return -1
    title = _title(ui_node) if isinstance(ui_node, dict) else ""
    if "negative" in title and "positive" not in title:
        return -1
    class_type = str(api_node.get("class_type") or "")
    inputs = _inputs(api_node)
    has_prompt = "prompt" in inputs or "prompt_text" in inputs or "text" in inputs
    if not has_prompt and class_type not in ("A1111PromptStyle", "PrimitiveString", "PrimitiveStringMultiline"):
        return -1
    if class_type in _PASS_THROUGH:
        return 5
    if "MiniMax" in class_type or "Wan" in class_type or "Kling" in class_type or "Hunyuan" in class_type:
        return 100 if "prompt" in inputs or "prompt_text" in inputs else -1
    if class_type == "CLIPTextEncode":
        return 80 if "text" in inputs else -1
    if class_type == "A1111PromptStyle":
        return 70
    if "prompt" in inputs or "prompt_text" in inputs:
        return 60
    if class_type in ("PrimitiveString", "PrimitiveStringMultiline"):
        return 20
    return -1


def _ranked_sinks(graph, ui_nodes):
    ranked = []
    for node_id, api_node in graph.items():
        if not isinstance(api_node, dict):
            continue
        ui_node = ui_nodes.get(str(node_id))
        score = _sink_score(api_node, ui_node)
        if score < 0:
            continue
        roles = _link_roles(graph, node_id)
        if "negative" in roles and "positive" not in roles and "prompt" not in roles:
            continue
        if "positive" in roles or "prompt" in roles:
            score += 30
        ranked.append((score, str(node_id)))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [node_id for _score, node_id in ranked]


def _locate_prompt(graph, nodes):
    ui_nodes = _ui_nodes(nodes)
    seen_leaves = []
    for node_id in _ranked_sinks(graph, ui_nodes):
        found = _follow_text(graph, node_id, set())
        if found is None:
            continue
        if found not in seen_leaves:
            seen_leaves.append(found)
        if seen_leaves:
            return seen_leaves[0]
    return None


def _widget_index(ui_node, key):
    class_type = str((ui_node or {}).get("type") or "")
    mapped = _WIDGET_INDEX.get(class_type, {}).get(key)
    if mapped is not None:
        return mapped
    names = []
    for entry in (ui_node or {}).get("inputs") or []:
        widget = entry.get("widget") if isinstance(entry, dict) else None
        if isinstance(widget, dict) and widget.get("name"):
            names.append(widget["name"])
    if key in names:
        return names.index(key)
    return None


def _duration_node(nodes):
    for node in nodes:
        if node.get("type") == "PrimitiveFloat" and "duration" in _title(node):
            return node
    return None


def _text_value(value):
    return value if isinstance(value, str) else None


def _number_value(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _read_prompt(graph, nodes):
    located = _locate_prompt(graph, nodes)
    if located is None:
        return None, False
    node_id, key = located
    value = _inputs(_api_node(graph, node_id)).get(key)
    if not isinstance(value, str):
        ui_node = _ui_nodes(nodes).get(str(node_id))
        index = _widget_index(ui_node, key)
        widget_value = _widget(ui_node, index) if index is not None else None
        value = widget_value if isinstance(widget_value, str) else ""
    return value, True


def _read_duration(graph, nodes):
    node = _duration_node(nodes)
    if node is None:
        return None, False
    api_value = _number_value(_inputs(_api_node(graph, node.get("id"))).get("value"))
    if api_value is None:
        api_value = _number_value(_widget(node, 0))
    return api_value, True


def _write_prompt(graph, nodes, text):
    located = _locate_prompt(graph, nodes)
    if located is None:
        raise ValueError("This job has no prompt box to edit")
    node_id, key = located
    api_node = _api_node(graph, node_id)
    if api_node is None or not isinstance(api_node.get("inputs"), dict):
        raise ValueError("The prompt box is not in this queued job")
    if _is_link(api_node["inputs"].get(key)):
        raise ValueError("The prompt box is linked to another node and cannot be edited here")
    api_node["inputs"][key] = text
    ui_node = _ui_nodes(nodes).get(str(node_id))
    index = _widget_index(ui_node, key)
    if ui_node is not None and index is not None:
        _set_widget(ui_node, index, text)


def _validate_duration(duration):
    seconds = _number_value(duration)
    if seconds is None:
        raise ValueError("Duration must be a number of seconds")
    if seconds < DURATION_MIN or seconds > DURATION_MAX:
        raise ValueError(f"Duration must be between {DURATION_MIN} and {DURATION_MAX} seconds")
    return seconds


def _write_duration(graph, nodes, workflow, seconds):
    node = _duration_node(nodes)
    if node is None:
        raise ValueError("This job has no duration box to edit")
    api_node = _api_node(graph, node.get("id"))
    if api_node is None or not isinstance(api_node.get("inputs"), dict):
        raise ValueError("The duration box is not in this queued job")
    if isinstance(api_node["inputs"].get("value"), list):
        raise ValueError("The duration box is linked to another node and cannot be edited here")
    api_node["inputs"]["value"] = seconds
    _set_widget(node, 0, seconds)
    _sync_builder_duration(workflow, seconds)


def _sync_builder_duration(workflow, seconds):
    for node in workflow.get("nodes") or []:
        if node.get("type") != "MiniMaxH3PromptBuilder":
            continue
        values = node.get("widgets_values")
        if not isinstance(values, list):
            continue
        for index, value in enumerate(values):
            if not isinstance(value, str) or not value.startswith("{") or '"duration"' not in value:
                continue
            try:
                data = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and "duration" in data:
                data["duration"] = seconds
                values[index] = json.dumps(data, ensure_ascii=False)
