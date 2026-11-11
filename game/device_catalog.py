"""실제 게임 그림과 짧은 작동 조건으로 읽는 장치 도감."""

from dataclasses import dataclass
import ctypes

import pico2d.pico2d as p

from game.front_end import Button, bevel
from game.logo_mode import fade_to_black

INK = (239, 237, 219)
MUTED = (164, 182, 177)
GOLD = (231, 190, 108)
TEAL = (112, 216, 190)
CARDS_PER_PAGE = 3


@dataclass(frozen=True)
class DeviceCard:
    kind: str
    title: str
    pictures: tuple[tuple[str, str], ...]
    action: str
    rule: str


CARDS = (
    DeviceCard("trap", "함정 복구", (("trap_broken", "파손"), ("trap_active", "가동")),
               "부품을 들고 함정 위에서 E / Space로 설치하세요.",
               "설치만 한 함정은 통과 가능. 가동하면 지나갈 수 없어요."),
    DeviceCard("lever", "레버 가동", (("lever_off", "대기"), ("lever_on", "가동")),
               "모든 함정을 설치한 뒤 빈손으로 레버 위에서 E / Space를 누르세요.",
               "가동 전에 남은 작업과 출구로 돌아갈 길을 확인하세요."),
    DeviceCard("assembly", "해골 병사 조립", (("bench_empty", "작업대"), ("soldier_deployed", "병사")),
               "작업대에 뼈 2묶음을 하나씩 납품하고, 완성된 병사를 배치대로 옮기세요.",
               "배치대에서 E / Space로 배치. 배치한 칸은 다시 들어갈 수 없어요."),
    DeviceCard("plate", "발판과 연결문", (("plate_down", "발판"), ("gate_open", "연결문")),
               "수리공이나 물건으로 발판을 누르면 연결된 문이 열려요.",
               "무게가 사라지면 닫혀요. 문 위에 있으면 나갈 때까지 기다려요."),
    DeviceCard("chute", "뼈 투입구", (("chute_inlet", "투입구"), ("chute_outlet", "배출구")),
               "뼈를 들고 투입구 위에서 E / Space를 누르면 연결된 배출구로 보내요.",
               "뼈만 전송 가능. 배출구가 물건이나 병사로 막히면 보낼 수 없어요."),
    DeviceCard("belt", "운반 벨트", (("conveyor_se", "벨트"), ("part", "운반할 부품")),
               "부품이나 조립한 병사를 내려놓으면 화살표 방향으로 자동 운반해요.",
               "뼈와 수리공은 운반 불가. 막히면 정지하며 추가 행동은 쓰지 않아요."),
)
PAGE_COUNT = (len(CARDS) + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE


def present_devices(level):
    return {kind for kind, exists in (
        ("trap", level.traps), ("lever", level.levers),
        ("assembly", level.benches and level.posts), ("plate", level.gates),
        ("chute", level.chutes), ("belt", level.belts)) if exists}


def catalog_buttons():
    return (Button("catalog_prev", "이전 카드", (94, 206, 354, 262)),
            Button("catalog_next", "다음 카드", (1246, 206, 1506, 262)),
            Button("catalog_back", "메뉴로 돌아가기", (600, 140, 1000, 196)))


def picture(view, name, x, y, width=160, height=126):
    entry = view.art.manifest["sprites"][name]
    rect = entry["content_rect"]
    scale = min(width / rect["width"], height / rect["height"])
    anchor = {"x": rect["left"] + rect["width"] / 2,
              "y": rect["top"] + rect["height"] / 2}
    view.art.draw(name, x, y, scale, anchor=anchor)


def card_text(view, x, y, value, size, color):
    """짧은 고정 문구를 단어 단위로 감싸 조작키와 낱말이 쪼개지지 않게 한다."""
    current = ""
    for word in value.split():
        candidate = f"{current} {word}" if current else word
        width = ctypes.c_int()
        p.TTF_SizeUTF8(view.fonts[size].font, candidate.encode(), ctypes.byref(width), None)
        if current and width.value > 388:
            view.text(x, y, current, size, color)
            y -= size + 9
            current = word
        else:
            current = candidate
    if current:
        view.text(x, y, current, size, color)
    return y


def draw_catalog(view, game, page):
    fade_to_black(.8)
    bevel((64, 120, 1536, 886), (22, 35, 40), (104, 139, 127))
    view.centered(800, 840, "던전 정비 수첩", 48, GOLD)
    view.centered(800, 792, "장치의 모습과 작동 조건을 확인하세요.", 18, INK)
    present = present_devices(game.level)
    cards = CARDS[page * CARDS_PER_PAGE:(page + 1) * CARDS_PER_PAGE]
    if any(name.startswith("gate_") for card in cards for name, _ in card.pictures):
        view.art.load_gates()
    for index, card in enumerate(cards):
        left, bottom, right, top = 94 + index * 476, 298, 530 + index * 476, 746
        in_room = card.kind in present
        bevel((left, bottom, right, top), (30, 48, 52), TEAL if in_room else (81, 99, 99))
        view.text(left + 24, top - 27, "이 방에 있음" if in_room else "다른 구역의 장치", 16, TEAL if in_room else MUTED)
        view.text(left + 24, top - 68, card.title, 32, INK)
        for i, (name, label) in enumerate(card.pictures):
            x = left + 114 + i * 206
            picture(view, name, x, top - 167)
            view.centered(x, top - 247, label, 16, MUTED)
        view.text(left + 24, top - 284, "사용 방법", 16, TEAL)
        last = card_text(view, left + 24, top - 313, card.action, 18, INK)
        card_text(view, left + 24, last - 39, card.rule, 16, GOLD)
    view.centered(800, 234, f"{page + 1} / {PAGE_COUNT}    ← → 페이지 이동", 18, INK)
    view.centered(800, 78, "도감을 읽는 동안 게임은 멈춥니다.    Esc 메뉴로 돌아가기", 18, INK)
