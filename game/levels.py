"""스테이지 파일을 읽고 실행 전에 구조와 재료 수를 검사한다."""

from dataclasses import dataclass
import json
from pathlib import Path


Pos = tuple[int, int]


@dataclass(frozen=True)
class Level:
    id: str
    title: str
    hint: str
    rows: tuple[str, ...]
    width: int
    height: int
    start: Pos
    exit: Pos
    walls: frozenset[Pos]
    traps: frozenset[Pos]
    levers: frozenset[Pos]
    benches: frozenset[Pos]
    posts: frozenset[Pos]
    initial_items: dict[Pos, str]


def load_levels(path: Path | str | None = None) -> list[Level]:
    """프로젝트 경로 기준 JSON을 읽는다. 잘못된 내용은 ValueError를 낸다."""
    source = Path(path) if path is not None else Path(__file__).resolve().parents[1] / "data" / "stages.json"
    with source.open(encoding="utf-8") as stream:
        document = json.load(stream)
    if not isinstance(document, dict) or set(document) != {"stages"}:
        raise ValueError("스테이지 문서에는 stages 목록만 있어야 합니다.")
    stages = document["stages"]
    if not isinstance(stages, list) or not stages:
        raise ValueError("stages는 비어 있지 않은 목록이어야 합니다.")

    levels = []
    identifiers = set()
    glyphs = "#.@EPBTLAS"
    for index, raw in enumerate(stages, start=1):
        prefix = f"스테이지 {index}: "
        if not isinstance(raw, dict) or set(raw) != {"id", "title", "hint", "map"}:
            raise ValueError(prefix + "id, title, hint, map 필드가 필요합니다.")
        if any(not isinstance(raw[key], str) or not raw[key].strip() for key in ("id", "title", "hint")):
            raise ValueError(prefix + "id, title, hint는 비어 있지 않은 문자열이어야 합니다.")
        if raw["id"] in identifiers:
            raise ValueError(prefix + "id가 중복되었습니다.")
        identifiers.add(raw["id"])
        rows = raw["map"]
        if not isinstance(rows, list) or not 8 <= len(rows) <= 12 or any(not isinstance(row, str) for row in rows):
            raise ValueError(prefix + "map에는 8~12개의 문자열 행이 필요합니다.")
        width, height = len(rows[0]), len(rows)
        if not 8 <= width <= 12 or any(len(row) != width for row in rows):
            raise ValueError(prefix + "지도는 너비 8~12칸의 직사각형이어야 합니다.")
        if any(char not in glyphs for row in rows for char in row):
            raise ValueError(prefix + "지도에 알 수 없는 기호가 있습니다.")
        if any(char != "#" for char in rows[0] + rows[-1]) or any(row[0] != "#" or row[-1] != "#" for row in rows):
            raise ValueError(prefix + "지도 테두리는 모두 벽이어야 합니다.")

        positions = {glyph: frozenset((x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == glyph) for glyph in glyphs}
        if len(positions["@"]) != 1 or len(positions["E"]) != 1:
            raise ValueError(prefix + "출발점과 출구는 각각 하나여야 합니다.")
        if not positions["T"] and not positions["S"]:
            raise ValueError(prefix + "복구할 함정이나 초소가 하나 이상 필요합니다.")
        if len(positions["P"]) != len(positions["T"]):
            raise ValueError(prefix + "함정 하나마다 부품 하나가 필요합니다.")
        if len(positions["B"]) != 2 * len(positions["S"]):
            raise ValueError(prefix + "초소 하나마다 뼈 묶음 두 개가 필요합니다.")
        if positions["T"] and not positions["L"]:
            raise ValueError(prefix + "함정이 있는 방에는 레버가 필요합니다.")
        if positions["S"] and not positions["A"]:
            raise ValueError(prefix + "초소가 있는 방에는 작업대가 필요합니다.")
        items = {pos: "part" for pos in positions["P"]}
        items.update({pos: "bone" for pos in positions["B"]})
        levels.append(Level(
            id=raw["id"], title=raw["title"], hint=raw["hint"], rows=tuple(rows),
            width=width, height=height, start=next(iter(positions["@"])), exit=next(iter(positions["E"])),
            walls=positions["#"], traps=positions["T"], levers=positions["L"],
            benches=positions["A"], posts=positions["S"], initial_items=items,
        ))
    return levels
