"""스테이지 파일을 읽고 실행 전에 구조와 재료 수를 검사한다."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re


Pos = tuple[int, int]
DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


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
    plates: frozenset[Pos] = frozenset()
    gates: dict[Pos, Pos] = field(default_factory=dict)
    device_labels: dict[Pos, str] = field(default_factory=dict)
    chutes: dict[Pos, Pos] = field(default_factory=dict)
    mirrors: frozenset[Pos] = frozenset()
    sources: dict[Pos, str] = field(default_factory=dict)
    receivers: frozenset[Pos] = frozenset()
    rubble: frozenset[Pos] = frozenset()
    jobs: frozenset[Pos] = frozenset()
    action_limit: int | None = None


def read_links(raw, field_name, first_name, second_name, first_tiles, second_tiles, prefix, used_ids):
    """지도에 표시한 장치를 명시적 ID와 두 좌표로 연결한다."""
    links = raw.get(field_name, [])
    if not isinstance(links, list):
        raise ValueError(prefix + f"{field_name}는 목록이어야 합니다.")
    pairs, labels = {}, {}
    destinations = set()
    for link in links:
        if not isinstance(link, dict) or set(link) != {"id", first_name, second_name}:
            raise ValueError(prefix + f"{field_name} 연결 필드가 잘못되었습니다.")
        identifier = link["id"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,7}", identifier) or identifier in used_ids:
            raise ValueError(prefix + "장치 ID는 중복 없는 영문 시작 1~8자여야 합니다.")
        points = []
        for key, allowed in ((first_name, first_tiles), (second_name, second_tiles)):
            point = link[key]
            if not isinstance(point, list) or len(point) != 2 or any(type(n) is not int for n in point) or tuple(point) not in allowed:
                raise ValueError(prefix + f"{identifier}의 {key} 좌표와 지도 기호가 맞지 않습니다.")
            points.append(tuple(point))
        first, second = points
        if first in pairs or second in destinations or first == second:
            raise ValueError(prefix + "같은 장치를 중복 연결할 수 없습니다.")
        pairs[first] = second
        destinations.add(second)
        labels.update({first: identifier, second: identifier})
        used_ids.add(identifier)
    return pairs, labels


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
    glyphs = "#.@EPBTLASFGCOMQYRJ"
    for index, raw in enumerate(stages, start=1):
        prefix = f"스테이지 {index}: "
        required = {"id", "title", "hint", "map"}
        if not isinstance(raw, dict) or not required <= set(raw) or set(raw) - required - {"plate_links", "chute_links", "action_limit", "power_links", "worker_links", "magic_sources"}:
            raise ValueError(prefix + "id, title, hint, map 필드가 필요합니다.")
        action_limit = raw.get("action_limit")
        if action_limit is not None and (type(action_limit) is not int or action_limit <= 0):
            raise ValueError(prefix + "action_limit는 양의 정수 또는 null이어야 합니다.")
        if any(not isinstance(raw[key], str) or not raw[key].strip() for key in ("id", "title", "hint")):
            raise ValueError(prefix + "id, title, hint는 비어 있지 않은 문자열이어야 합니다.")
        if raw["id"] in identifiers:
            raise ValueError(prefix + "id가 중복되었습니다.")
        identifiers.add(raw["id"])
        rows = raw["map"]
        if not isinstance(rows, list) or not 6 <= len(rows) <= 12 or any(not isinstance(row, str) for row in rows):
            raise ValueError(prefix + "map에는 6~12개의 문자열 행이 필요합니다.")
        width, height = len(rows[0]), len(rows)
        if not 6 <= width <= 12 or any(len(row) != width for row in rows):
            raise ValueError(prefix + "지도는 너비 6~12칸의 직사각형이어야 합니다.")
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
        used_ids = set()
        plate_links, labels = read_links(raw, "plate_links", "plate", "gate", positions["F"], positions["G"], prefix, used_ids)
        power_links, power_labels = read_links(raw, "power_links", "receiver", "gate", positions["Y"], positions["G"], prefix, used_ids)
        worker_links, worker_labels = read_links(raw, "worker_links", "station", "gate", positions["J"], positions["G"], prefix, used_ids)
        links = {**plate_links, **power_links, **worker_links}
        if (set(plate_links) != positions["F"] or set(power_links) != positions["Y"]
                or set(worker_links) != positions["J"] or set(links.values()) != positions["G"]
                or len(links) != len(positions["G"])):
            raise ValueError(prefix + "모든 발판·수신기·작업대와 문을 한 번씩 연결해야 합니다.")
        labels.update(power_labels)
        labels.update(worker_labels)
        chutes, chute_labels = read_links(raw, "chute_links", "inlet", "outlet", positions["C"],
                                         positions["O"] | positions["."] | positions["F"], prefix, used_ids)
        if set(chutes) != positions["C"] or not positions["O"] <= set(chutes.values()):
            raise ValueError(prefix + "모든 투입구와 표시된 배출구를 연결해야 합니다.")
        for pos, identifier in chute_labels.items():
            labels[pos] = labels[pos] + "/" + identifier if pos in labels else identifier
        items = {pos: "part" for pos in positions["P"]}
        items.update({pos: "bone" for pos in positions["B"]})
        sources = {}
        raw_sources = raw.get("magic_sources", [])
        if not isinstance(raw_sources, list):
            raise ValueError(prefix + "magic_sources는 목록이어야 합니다.")
        for source in raw_sources:
            if not isinstance(source, dict) or set(source) != {"cell", "direction"}:
                raise ValueError(prefix + "마력 광원 필드가 잘못되었습니다.")
            cell = source["cell"]
            if (not isinstance(cell, list) or len(cell) != 2 or any(type(n) is not int for n in cell)
                    or tuple(cell) not in positions["Q"] or tuple(cell) in sources
                    or not isinstance(source["direction"], str) or source["direction"] not in DIRECTIONS):
                raise ValueError(prefix + "마력 광원 좌표나 방향이 잘못되었습니다.")
            sources[tuple(cell)] = source["direction"]
        if set(sources) != positions["Q"] or (positions["M"] | positions["Y"] and not sources):
            raise ValueError(prefix + "거울·수신기에는 방향이 지정된 광원이 필요합니다.")
        if positions["J"] and not positions["S"]:
            raise ValueError(prefix + "해골 인부는 병사 복구 목표와 함께 배치해야 합니다.")
        levels.append(Level(
            id=raw["id"], title=raw["title"], hint=raw["hint"], rows=tuple(rows),
            width=width, height=height, start=next(iter(positions["@"])), exit=next(iter(positions["E"])),
            walls=positions["#"], traps=positions["T"], levers=positions["L"],
            benches=positions["A"], posts=positions["S"], initial_items=items,
            plates=positions["F"], gates={gate: control for control, gate in links.items()}, device_labels=labels,
            chutes=chutes, action_limit=action_limit,
            mirrors=positions["M"], sources=sources, receivers=positions["Y"],
            rubble=positions["R"], jobs=positions["J"],
        ))
    return levels
