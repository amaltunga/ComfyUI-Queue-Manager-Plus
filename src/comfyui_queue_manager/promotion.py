"""Queue promotion colours. Grey means the job is still in, or behind, its queued order."""

import zlib

WORKFLOW_PALETTE = (
    "#5b8def",
    "#c084fc",
    "#2dd4bf",
    "#f472b6",
    "#f0a202",
    "#60a5fa",
    "#a3e635",
    "#fb7185",
    "#22d3ee",
    "#e879f9",
)


def workflow_block_color(workflow_id):
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        return None
    return WORKFLOW_PALETTE[zlib.crc32(workflow_id.encode()) % len(WORKFLOW_PALETTE)]


def promotion_color(current_index, original_index):
    moved_up = original_index - current_index
    if moved_up <= 0:
        return "grey"
    if current_index == 0:
        return "red"
    if moved_up >= 3:
        return "orange"
    return "green"
