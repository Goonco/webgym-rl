from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
INSTANCE_PATH = (
    ROOT_DIR / "environment" / "webgym" / "omniboxes" / "node" / "instances" / "playwright_instance.py"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class CursorOverlayStyleTests(unittest.TestCase):
    def test_overlay_renderer_uses_pointer_position_for_cursor_overlay(self) -> None:
        source = _read(INSTANCE_PATH)
        tree = ast.parse(source)

        overlay_fn = next(
            member
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "PlaywrightInstance"
            for member in node.body
            if isinstance(member, ast.FunctionDef) and member.name == "_overlay_cursor"
        )

        overlay_source = ast.get_source_segment(source, overlay_fn) or ""

        self.assertIn("self.controller.pointer_position", overlay_source)
        self.assertNotIn("self.controller.overlay_cursor_position", overlay_source)
        self.assertIn("draw.polygon(outer", overlay_source)
        self.assertIn("fill=(0, 0, 0, 255)", overlay_source)
        self.assertIn("(x, y + 22)", overlay_source)
        self.assertNotIn("shadow =", overlay_source)
        self.assertNotIn("draw.polygon(shadow", overlay_source)
        self.assertNotIn("inner =", overlay_source)
        self.assertNotIn("draw.polygon(inner", overlay_source)


if __name__ == "__main__":
    unittest.main()
