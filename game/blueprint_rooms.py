"""기존 방 배치에 마력 배선을 추가하는 시범 모드."""

from dataclasses import replace

from game.levels import Circuit, Level


def blueprint_rooms(levels: list[Level]) -> list[Level]:
    circuits = {
        "stage_01": (
            Circuit(((4, 3), (4, 4), (2, 4), (2, 3)), ((4, 4), (2, 4)), ("레버", "함정")),
        ),
        "stage_05": (
            Circuit(((3, 5), (3, 4), (4, 4)), ((3, 4), (4, 4)), ("M1 수신기", "창고 문")),
            Circuit(((3, 1), (1, 1), (1, 5), (2, 5), (2, 7)), ((1, 1), (1, 5)),
                    ("M2 수신기", "출구 문")),
        ),
    }
    return [replace(level, circuits=circuits[level.id]) if level.id in circuits else level for level in levels]
