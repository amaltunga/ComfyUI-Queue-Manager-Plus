import json
import unittest

from src.comfyui_queue_manager.job_fields import apply_job_fields, read_job_fields
from src.comfyui_queue_manager.promotion import promotion_color, workflow_block_color


def _item(graph, nodes, name="Job"):
    workflow = {"workflow_name": name, "nodes": nodes}
    return [1, "prompt-id", graph, {"extra_pnginfo": {"workflow": workflow}}, [], {}]


class JobFieldTests(unittest.TestCase):
    def test_minimax_prompt_and_duration(self):
        nodes = [
            {
                "id": 138,
                "type": "PrimitiveStringMultiline",
                "title": "Prompt box",
                "widgets_values": ["example prompt"],
            },
            {
                "id": 132,
                "type": "PrimitiveFloat",
                "title": "Float (Duration)",
                "widgets_values": [7],
            },
            {
                "id": 143,
                "type": "MiniMaxH3PromptBuilder",
                "widgets_values": [json.dumps({"duration": 7, "mode": "REF"})],
            },
        ]
        graph = {
            "138": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "example prompt"}},
            "132": {"class_type": "PrimitiveFloat", "inputs": {"value": 7}},
        }
        item = _item(graph, nodes, "Example")
        self.assertEqual(read_job_fields(item)["prompt"], "example prompt")
        self.assertEqual(read_job_fields(item)["duration"], 7)

        updated = apply_job_fields(item, prompt="updated example prompt", duration=5)
        self.assertEqual(updated["prompt"], "updated example prompt")
        self.assertEqual(updated["duration"], 5)
        self.assertEqual(graph["138"]["inputs"]["value"], "updated example prompt")
        self.assertEqual(graph["132"]["inputs"]["value"], 5)
        self.assertEqual(nodes[0]["widgets_values"][0], "updated example prompt")
        self.assertEqual(nodes[1]["widgets_values"][0], 5)
        self.assertEqual(json.loads(nodes[2]["widgets_values"][0])["duration"], 5)

    def test_a1111_edits_resolved_positive(self):
        nodes = [
            {
                "id": 13,
                "type": "A1111PromptStyle",
                "title": "A1111 style",
                "widgets_values": ["Cinematic", "short prompt", "resolved positive", "anime", ""],
            }
        ]
        graph = {
            "13": {
                "class_type": "A1111PromptStyle",
                "inputs": {
                    "style": "Cinematic",
                    "prompt": "short prompt",
                    "positive_text": "resolved positive",
                    "style_negative": "anime",
                },
            }
        }
        item = _item(graph, nodes)
        self.assertEqual(read_job_fields(item)["prompt"], "resolved positive")
        self.assertFalse(read_job_fields(item)["duration_editable"])
        apply_job_fields(item, prompt="a woman in daylight")
        self.assertEqual(graph["13"]["inputs"]["positive_text"], "a woman in daylight")
        self.assertEqual(graph["13"]["inputs"]["prompt"], "short prompt")
        self.assertEqual(nodes[0]["widgets_values"][2], "a woman in daylight")

    def test_a1111_empty_positive_edits_prompt_field(self):
        nodes = [
            {
                "id": 13,
                "type": "A1111PromptStyle",
                "widgets_values": ["Cinematic", "short prompt", "  ", "", ""],
            }
        ]
        graph = {
            "13": {
                "class_type": "A1111PromptStyle",
                "inputs": {"style": "Cinematic", "prompt": "short prompt", "positive_text": "  "},
            }
        }
        item = _item(graph, nodes)
        self.assertEqual(read_job_fields(item)["prompt"], "short prompt")
        apply_job_fields(item, prompt="new short prompt")
        self.assertEqual(graph["13"]["inputs"]["prompt"], "new short prompt")
        self.assertEqual(graph["13"]["inputs"]["positive_text"], "  ")

    def test_follows_prompt_wire_and_skips_bypassed_box(self):
        builder = "example builder prompt"
        nodes = [
            {
                "id": 138,
                "type": "PrimitiveStringMultiline",
                "mode": 4,
                "title": "Bypassed prompt",
                "widgets_values": ["old unused prompt"],
            },
            {
                "id": 143,
                "type": "MiniMaxH3PromptBuilder",
                "mode": 0,
                "title": "Prompt builder",
                "widgets_values": [builder, "{}"],
            },
            {"id": 136, "type": "MiniMaxH3ReferenceToVideo", "title": "MiniMax"},
            {"id": 4, "type": "CLIPTextEncode", "title": "Negative", "widgets_values": ["bad hands"]},
            {"id": 3, "type": "CLIPTextEncode", "title": "Positive", "widgets_values": ["a woman in daylight"]},
        ]
        graph = {
            "138": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "old unused prompt"}},
            "143": {"class_type": "MiniMaxH3PromptBuilder", "inputs": {"prompt_text": builder}},
            "136": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {"prompt": ["143", 0]}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "bad hands"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "a woman in daylight"}},
            "6": {
                "class_type": "KSampler",
                "inputs": {"positive": ["3", 0], "negative": ["4", 0]},
            },
        }
        item = _item(graph, nodes)
        self.assertEqual(read_job_fields(item)["prompt"], builder)
        apply_job_fields(item, prompt="a new scene")
        self.assertEqual(graph["143"]["inputs"]["prompt_text"], "a new scene")
        self.assertEqual(nodes[1]["widgets_values"][0], "a new scene")
        self.assertEqual(graph["138"]["inputs"]["value"], "old unused prompt")

    def test_follows_string_through_appended_negative(self):
        nodes = [
            {
                "id": 138,
                "type": "PrimitiveStringMultiline",
                "title": "Scene text",
                "widgets_values": ["example scene prompt"],
            },
            {"id": 144, "type": "A1111AppendNegativeToPrompt", "widgets_values": ["Default_Negative", "watermark", ""]},
            {"id": 136, "type": "MiniMaxH3ReferenceToVideo"},
        ]
        graph = {
            "138": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "example scene prompt"}},
            "144": {
                "class_type": "A1111AppendNegativeToPrompt",
                "inputs": {"prompt": ["138", 0], "negative_text": "watermark"},
            },
            "136": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {"prompt": ["144", 0]}},
        }
        item = _item(graph, nodes)
        self.assertEqual(read_job_fields(item)["prompt"], "example scene prompt")
        apply_job_fields(item, prompt="updated scene prompt")
        self.assertEqual(graph["138"]["inputs"]["value"], "updated scene prompt")
        self.assertEqual(nodes[0]["widgets_values"][0], "updated scene prompt")

    def test_positive_clip_not_negative(self):
        nodes = [
            {"id": 4, "type": "CLIPTextEncode", "title": "Negative", "widgets_values": ["bad hands"]},
            {"id": 3, "type": "CLIPTextEncode", "title": "Positive", "widgets_values": ["a woman in daylight"]},
        ]
        graph = {
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "bad hands"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "a woman in daylight"}},
            "6": {"class_type": "KSampler", "inputs": {"positive": ["3", 0], "negative": ["4", 0]}},
        }
        item = _item(graph, nodes)
        self.assertEqual(read_job_fields(item)["prompt"], "a woman in daylight")

    def test_same_workflow_keeps_the_same_colour(self):
        first = workflow_block_color("workflow-one")
        self.assertEqual(first, workflow_block_color("workflow-one"))
        self.assertNotEqual(first, workflow_block_color("workflow-two"))
        self.assertIsNone(workflow_block_color(""))
        self.assertIn(first, (
            "#5b8def", "#c084fc", "#2dd4bf", "#f472b6", "#f0a202",
            "#60a5fa", "#a3e635", "#fb7185", "#22d3ee", "#e879f9",
        ))

    def test_promotion_colours(self):
        self.assertEqual(promotion_color(0, 0), "grey")
        self.assertEqual(promotion_color(2, 1), "grey")
        self.assertEqual(promotion_color(1, 2), "green")
        self.assertEqual(promotion_color(1, 3), "green")
        self.assertEqual(promotion_color(1, 5), "orange")
        self.assertEqual(promotion_color(0, 1), "red")
        self.assertEqual(promotion_color(0, 4), "red")

    def test_duration_limits(self):
        nodes = [{"id": 1, "type": "PrimitiveFloat", "title": "Float (Duration)", "widgets_values": [7]}]
        graph = {"1": {"class_type": "PrimitiveFloat", "inputs": {"value": 7}}}
        item = _item(graph, nodes)
        with self.assertRaises(ValueError):
            apply_job_fields(item, duration=16)
        with self.assertRaises(ValueError):
            apply_job_fields(item, duration=0)
        self.assertEqual(graph["1"]["inputs"]["value"], 7)


if __name__ == "__main__":
    unittest.main()
