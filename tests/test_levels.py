"""Stage schema errors fail before starting a game window."""

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest

from game.levels import load_levels


VALID_STAGE = {
    "id": "valid", "title": "검증 방", "hint": "함정을 복구하세요.",
    "map": [
        "########", "#@P.TLE#", "#......#", "#......#",
        "#......#", "#......#", "#......#", "########",
    ],
}


class LevelTests(unittest.TestCase):
    def load_document(self, document):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stages.json"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            return load_levels(path)

    def test_shipped_levels_load_from_another_working_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                levels = load_levels()
            finally:
                os.chdir(previous)
        self.assertEqual(len(levels), 3)
        self.assertEqual(len({level.id for level in levels}), 3)
        for level in levels:
            self.assertEqual((level.width, level.height), (8, 8))
            self.assertTrue(level.title)
            self.assertTrue(level.hint)

    def test_rejects_invalid_document_and_stage_metadata(self):
        documents = [[], {}, {"stages": []}, {"stages": "room"},
                     {"stages": [None]}, {"stages": [VALID_STAGE, VALID_STAGE]}]
        for field, value in (("id", ""), ("title", ""), ("hint", None), ("map", "map")):
            stage = deepcopy(VALID_STAGE)
            stage[field] = value
            documents.append({"stages": [stage]})
        for document in documents:
            with self.subTest(document=document):
                with self.assertRaises(ValueError):
                    self.load_document(document)

    def test_rejects_invalid_geometry_and_missing_resources(self):
        maps = []
        for row_index, row in (
            (0, "#######."), (2, "#.....#"), (2, "#..?..?#"),
            (1, "#.P.TLE#"), (2, "#@.....#"), (1, "#@P.TL.#"),
            (2, "#E.....#"), (1, "#@..TLE#"), (1, "#@P.T.E#"),
            (1, "#@....E#"), (2, "#S.....#"),
        ):
            rows = list(VALID_STAGE["map"])
            rows[row_index] = row
            maps.append(rows)
        maps.append(VALID_STAGE["map"][:-1])
        maps.append(["#" * 13] * 8)
        maps.append([
            "########", "#@....E#", "#BB..S.#", "#......#",
            "#......#", "#......#", "#......#", "########",
        ])  # Correct bone count but no assembly bench.
        for rows in maps:
            stage = dict(VALID_STAGE, map=rows)
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    self.load_document({"stages": [stage]})

    def test_missing_or_malformed_files_report_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                load_levels(path)
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_levels(path)


if __name__ == "__main__":
    unittest.main()
