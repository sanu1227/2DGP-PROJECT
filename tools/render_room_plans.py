"""현재 실행 데이터에서 소형 방의 좌표 배치도와 크기·행동 제한 문서를 생성한다."""
from html import escape
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.solutions import MINIMUM_ACTIONS

NOTES = (
    "부품을 가져와 함정을 설치하고 건넌다. 남쪽 레버로 가동하면 시작 구역으로 돌아갈 수 없지만 서쪽 출구로 나갈 수 있다.",
    "동쪽 두 보관 구역의 뼈를 작업대로 가져온다. 조립한 병사를 가운데 초소에 배치하고 서쪽으로 이탈한다.",
    "위쪽 함정 너머 부품과 뼈, 아래쪽 함정 너머 부품과 뼈를 모두 회수한다. 초소를 배치할 때 서쪽으로 나가고 마지막에 함정을 가동한다.",
    "잔해 바로 위에서 아래 방향키를 눌러 발판에 민다. 문으로 들어가 함정과 병사를 복구한다. 발판과 문 사이에 통로 한 칸을 두어 잔해가 보이게 했다.",
    "거울을 돌려 수신기에 빛을 보낸다. 안쪽 뼈 하나를 투입구로 보내고 다른 뼈를 들고 돌아와 조립한다. 두 뼈를 직접 왕복 운반하는 풀이는 행동 제한을 넘는다.",
    "광원 (1,2)의 빛을 거울 (3,2), (3,4)에서 두 번 반사해 수신기 (5,4)에 보낸다. 두 거울 모두 돌려야 문이 열린다. 문 안의 부품을 가져와 함정을 설치하고 병사를 복구한 뒤 돌아온다.",
    "병사를 조립해 윈치에 배치한다. 열린 창고의 부품으로 함정을 설치하고 인부를 회수해 초소에 배치한다. 함정을 건넌 뒤 레버를 가동해 출구로 나간다.",
    "광원 (1,1)에서 거울 (1,2), (3,2), (3,4)를 거쳐 수신기 (4,4)로 빛을 보낸다. 세 거울을 모두 맞춰야 재료 구역 입구가 열린다. 투입구로 뼈를 회수하고 인부로 금고를 연다. 잔해 너머 두 번째 부품을 회수한 뒤 인부를 초소에 배치하고 복구를 마친다.",
)
LEGEND = "@ 출발 · E 출구 · P 부품 · B 뼈 · T 함정 · L 레버 · A 조립대 · S 초소 · F 발판 · G 문 · C 투입구 · O 배출구 · Q 광원 · M 거울 · Y 수신기 · R 잔해 · J 윈치"


def main():
    rooms = json.loads((ROOT / "data/stages.json").read_text(encoding="utf-8"))["stages"]
    folder = ROOT / "docs/screenshots/compact-rooms"
    folder.mkdir(parents=True, exist_ok=True)
    doc = ["# 기믹에 맞춘 방 크기와 배치", "", "2026-11-13. 외곽 벽을 포함한 크기다. 여덟 방과 복구 재료 수를 유지한다. 수문·수위는 제거했고, 5번 1회·6번 2회·8번 3회 반사로 거울을 확장했다. 1번은 무제한, 2~8번은 실제 게임 규칙으로 검증한 최소 행동 수+2회를 적용한다.", "",
           "| 방 | 크기 | 바닥 칸 | 최소 행동 | 제한 |", "| --- | --- | ---: | ---: | ---: |"]
    for number, room in enumerate(rooms, 1):
        width, height = len(room["map"][0]), len(room["map"])
        floor = sum(c != "#" for row in room["map"] for c in row)
        limit = room["action_limit"] if room["action_limit"] is not None else "무제한"
        doc.append(f"| {number} | {width}×{height} | {floor} | {MINIMUM_ACTIONS[room['id']]} | {limit} |")
    doc += ["", "![여덟 방 실제 화면](screenshots/compact-rooms/overview.png)", "", "## 배치와 풀이", "", LEGEND, ""]
    for number, room in enumerate(rooms, 1):
        width, height = len(room["map"][0]), len(room["map"])
        cell, ox, oy = 42, 34, 60
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width*cell+68}" height="{height*cell+90}" viewBox="0 0 {width*cell+68} {height*cell+90}">',
               '<rect width="100%" height="100%" fill="#151d23"/>',
               '<g font-family="Malgun Gothic, sans-serif" fill="#eff3f5">',
               f'<text x="20" y="27" font-size="16">{number}. {escape(room["title"])} ({width}×{height})</text>']
        for x in range(width):
            svg.append(f'<text x="{ox+x*cell+20}" y="50" text-anchor="middle" font-size="11">{x}</text>')
        for y, row in enumerate(room["map"]):
            svg.append(f'<text x="22" y="{oy+y*cell+26}" text-anchor="middle" font-size="11">{y}</text>')
            for x, glyph in enumerate(row):
                color = "#29333e" if glyph == "#" else "#46555e" if glyph == "." else "#326d68"
                svg.append(f'<rect x="{ox+x*cell}" y="{oy+y*cell}" width="40" height="40" rx="3" fill="{color}"/>')
                if glyph not in "#.":
                    svg.append(f'<text x="{ox+x*cell+20}" y="{oy+y*cell+27}" text-anchor="middle" font-size="22">{glyph}</text>')
        for field, source, target in (("plate_links", "plate", "gate"), ("power_links", "receiver", "gate"), ("worker_links", "station", "gate"), ("chute_links", "inlet", "outlet")):
            for link in room.get(field, []):
                x, y = link[source]
                tx, ty = link[target]
                svg.append(f'<path d="M{ox+x*cell+20},{oy+y*cell+20} L{ox+tx*cell+20},{oy+ty*cell+20}" stroke="#ffd789" stroke-width="2" stroke-dasharray="4 4" opacity=".6"/>')
        svg.append("</g></svg>")
        (folder / f"stage-{number:02}-plan.svg").write_text("\n".join(svg), encoding="utf-8")
        doc += [f"### {number}번 — {room['title']}", "", NOTES[number-1], "", f"![좌표 배치도](screenshots/compact-rooms/stage-{number:02}-plan.svg)", "", f"[시작 화면](screenshots/compact-rooms/stage-{number:02}.png) · [완료 화면](screenshots/compact-rooms/stage-{number:02}-cleared.png)", ""]
    doc += ["## 검증", "", "- 실제 `Game.act`로 최단 풀이를 탐색했다. 유일한 수신 경로에서 맞춘 거울을 다시 틀어 문을 닫는 입력만 최단성 보존 조건에 따라 제외한다. 인부가 반드시 필요한 문 안의 부품은 인부 운반·배치·회수 비용도 하한에 반영한다. 작은 방의 전체 상태 그래프로 이 하한과 최단 결과를 독립 검사한다.",
            "- 4번 잔해·발판, 5번 거울·투입구, 6번 거울, 7번 인부, 8번 잔해·거울·인부·투입구를 각각 생략하면 행동 제한 안에 완료할 수 없다.",
            "- 최소 행동과 1회 부족한 예산, 자원 보존, 전체 되돌리기, 작은 격자의 클릭 판정, 튜토리얼과 SDL 키보드 완주를 검사한다.",
            "- 모니터에 창을 띄우지 않고 SDL dummy/software로 시작·작동·완료 화면을 확인했다. 물리 입력과 사람의 초회 플레이 난이도는 미측정이다.", "",
            "```powershell", "python tools/solve_levels.py --check --check-mechanics --output docs/balance-report.json", "python -m unittest discover -q", "python tools/render_room_plans.py", "```", "",
            "[탐색 결과와 입력 SHA-256](balance-report.json) · [퍼즐 배치 규칙](퍼즐배치규칙.md)", ""]
    (ROOT / "docs/방크기조정.md").write_text("\n".join(doc), encoding="utf-8")
    print("8 room plans and docs/방크기조정.md generated")


if __name__ == "__main__":
    main()
