# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import tempfile
import textwrap
from pathlib import Path
from typing import List

import libcst as cst

import testslide

from ...tests import setup
from ..coverage import (
    collect_coverage_for_module,
    collect_coverage_for_paths,
    FileCoverage,
    find_root_path,
)


class CoverageTest(testslide.TestCase):
    def assert_coverage_equal(
        self,
        file_content: str,
        expected_covered: List[int],
        expected_uncovered: List[int],
    ) -> None:
        module = cst.MetadataWrapper(
            cst.parse_module(textwrap.dedent(file_content).strip())
        )
        actual_coverage = collect_coverage_for_module(
            "test.py", module, strict_default=False
        )
        self.assertEqual(
            expected_covered, actual_coverage.covered_lines, "Covered mismatch"
        )
        self.assertEqual(
            expected_uncovered, actual_coverage.uncovered_lines, "Not covered mismatch"
        )

    def test_coverage_covered(self) -> None:
        self.assert_coverage_equal(
            """
            def foo() -> int:
                return 5
            """,
            expected_covered=[0, 1],
            expected_uncovered=[],
        )

    def test_coverage_uncovered(self) -> None:
        self.assert_coverage_equal(
            """
            def foo():
                return 5
            """,
            expected_covered=[],
            expected_uncovered=[0, 1],
        )

    def test_coverage_mixed(self) -> None:
        self.assert_coverage_equal(
            """
            import os

            X = 5

            def foo():
                return 5

            class Bar():

                def baz(self, y) -> int:
                    return y + 5
            """,
            expected_covered=[0, 1, 2, 3, 6, 7, 8, 9, 10],
            expected_uncovered=[4, 5],
        )

    def test_coverage_nested(self) -> None:
        self.assert_coverage_equal(
            """
            def f():

                def bar(x: int) -> None:
                    return x

                return 5
            """,
            expected_covered=[2, 3],
            expected_uncovered=[0, 1, 4, 5],
        )
        self.assert_coverage_equal(
            """
            level0: None = None
            def level1():
                def level2() -> None:
                    def level3():
                        def level4() -> None:
                            def level5(): ...
            """,
            expected_covered=[0, 2, 4],
            expected_uncovered=[1, 3, 5],
        )

    def contains_uncovered_lines(self, file_content: str, strict_default: bool) -> bool:
        module = cst.MetadataWrapper(
            cst.parse_module(textwrap.dedent(file_content).strip())
        )
        actual_coverage = collect_coverage_for_module("test.py", module, strict_default)
        return len(actual_coverage.uncovered_lines) > 0

    def test_coverage_strict(self) -> None:
        self.assertTrue(
            self.contains_uncovered_lines(
                """
                # No file specific comment
                def foo(): ...
                """,
                strict_default=False,
            )
        )
        self.assertFalse(
            self.contains_uncovered_lines(
                """
                # pyre-strict
                def foo(): ...
                """,
                strict_default=False,
            )
        )
        self.assertFalse(
            self.contains_uncovered_lines(
                """
                # No file specific comment
                def foo(): ...
                """,
                strict_default=True,
            )
        )
        self.assertTrue(
            self.contains_uncovered_lines(
                """
                # pyre-unsafe
                def foo(): ...
                """,
                strict_default=True,
            )
        )

    def test_find_root(self) -> None:
        self.assertEqual(
            find_root_path(
                local_root=Path("/root/local"),
                working_directory=Path("/irrelevant"),
            ),
            Path("/root/local"),
        )
        self.assertEqual(
            find_root_path(
                local_root=None,
                working_directory=Path("/working/dir"),
            ),
            Path("/working/dir"),
        )

    def test_collect_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path: Path = Path(root)
            setup.ensure_files_exist(root_path, ["foo.py", "bar.py"])
            foo_path = root_path / "foo.py"
            bar_path = root_path / "bar.py"
            baz_path = root_path / "baz.py"

            data: List[FileCoverage] = collect_coverage_for_paths(
                [foo_path, bar_path, baz_path],
                working_directory=root,
                strict_default=False,
            )

            def is_collected(path: Path) -> bool:
                return any(
                    str(path.relative_to(root_path)) == coverage.filepath
                    for coverage in data
                )

            self.assertTrue(is_collected(foo_path))
            self.assertTrue(is_collected(bar_path))
            self.assertFalse(is_collected(baz_path))
