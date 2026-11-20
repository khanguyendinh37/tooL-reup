import ast
import unittest
from pathlib import Path


class FreezeSupportTests(unittest.TestCase):
    def test_freeze_support_runs_before_any_cli_branch(self):
        """A frozen app must divert multiprocessing helpers before starting the UI."""
        tree = ast.parse(Path(__file__).with_name("desktop_main.py").read_text(encoding="utf-8"))
        freeze_line = first_branch_line = None
        for node in tree.body:
            if isinstance(node, ast.Expr) and "freeze_support" in ast.unparse(node):
                freeze_line = freeze_line or node.lineno
            if isinstance(node, ast.If) and "sys.argv" in ast.unparse(node.test):
                first_branch_line = first_branch_line or node.lineno
        self.assertIsNotNone(freeze_line, "multiprocessing.freeze_support() missing")
        self.assertLess(freeze_line, first_branch_line)


if __name__ == "__main__":
    unittest.main()
