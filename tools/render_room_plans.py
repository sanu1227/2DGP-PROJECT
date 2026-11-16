"""현재 실행 데이터에서 방의 좌표 배치도와 크기·행동 제한 문서를 생성한다."""
from html import escape
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.solutions import MINIMUM_ACTIONS

NOTES = (
    "위쪽 작업장에서 함정을 고치고 시험로를 건넌다. 통로 끝 옆칸에 있는 시운전 레버를 당기면 작업장으로 돌아가는 길이 닫힌다. 출구는 아래 통로의 반대편에 있다.",
    "서쪽 납골 구역과 동쪽 묘실의 뼈를 작업대 한 곳에 모은다. 서쪽 작업대는 32회, 동쪽 작업대는 40회에 끝낼 수 있다. 중앙 초소에 병사를 세운 뒤 출구 방향으로 나간다.",
    "북·남 서가의 재료를 꺼내고 두 입구의 함정을 고친다. 북쪽 안의 레버도 두 함정을 가동하지만, 그 자리에서 가동하면 돌아올 통로를 잃는다. 출구 근처 레버로 봉쇄할 길을 살펴야 한다.",
    "간수 통로의 잔해를 P1에 밀어 첫 감방을 연다. 그 안의 뼈를 감방 입구 앞 P2에 놓고, 두 번째 뼈는 서쪽 벽 앞 P3에 둔다. 안쪽 무기고에 가려면 P2와 P3을 함께 열어 둬야 한다. 부품을 꺼낸 뒤 남쪽에서 병사를 조립해 동쪽 끝 초소를 채우고, 하단 복도에서 레버를 당긴 뒤 출구로 나간다.",
    "수문 광선을 막는 잔해를 옆으로 밀어 반사 경로를 비운다. 광선 방향으로 밀기만 하면 계속 막힌다. 상류에서 뼈를 보내 남쪽 집수실을 개방한다. 집수실의 뼈를 빼낸 뒤 발판의 뼈를 회수한다.",
    "남쪽 수신실에서 부품과 뼈를 빼낸다. 북쪽에만 작업대가 있어 남쪽 뼈는 두 전력 상태를 건너야 한다. 거울은 빈손으로 돌려야 하므로 뼈를 중앙 통로에 잠시 내려놓고 전환한다. 북쪽에 놓인 뼈와 합쳐 조립한 뒤 초소를 채운다.",
    "첫 기록석은 문양을 첫걸음에 밟고 두 번째에 벗어나도록 기록한다. 되감긴 자리에서 바로 문에 들어간다. 안쪽 부품을 P1 발판에 올려 해골을 회수하고, 발판의 부품으로 첫 함정을 복구한다. 두 번째 기록석은 네 걸음 중 두 번째에 문양을 밟는다. 재생이 시작되면 한 칸 접근한 뒤 바로 건넌다. 마지막 부품과 출구는 금고 안쪽에 있다.",
    "해골을 초소에 배치하고 M2를 열어 기록석으로 간다. 위쪽 길에서 2번째 걸음에 J1 문양, 4번째 걸음에 J2 문양을 밟는다. 재생이 시작되면 수리공은 아래쪽 복도를 따라 두 문을 순서대로 건넌다. 두 번째 문 바로 안쪽의 부품을 집어 함정을 복구하고 출구로 나간다.",
)
LEGEND = "@ 출발 · E 출구 · P 부품 · B 뼈 · K 조립된 해골 · T 함정 · L 레버 · A 조립대 · S 초소 · F 발판 · G 문 · C 투입구 · O 배출구 · Q 광원 · M 거울 · Y 수신기 · R 잔해 · J 기록석 · U 분신 문양"


def main():
    rooms = json.loads((ROOT / "data/stages.json").read_text(encoding="utf-8"))["stages"]
    folder = ROOT / "docs/screenshots/compact-rooms"
    folder.mkdir(parents=True, exist_ok=True)
    margins = [room["action_limit"] - MINIMUM_ACTIONS[room["id"]] for room in rooms if room["action_limit"] is not None]
    doc = ["# 기믹에 맞춘 방 크기와 배치", "", f"2026-11-16. 외곽 벽을 포함한 크기다. 1번은 무제한이다. 2~8번의 행동 제한에는 최소 풀이보다 {min(margins)}~{max(margins)}회의 여유를 뒀다. 표와 좌표 배치도는 현재 게임 데이터 기준이다.", "",
           "| 방 | 크기 | 바닥 칸 | 최소 행동 | 제한 | 여유 |", "| --- | --- | ---: | ---: | ---: | ---: |"]
    for number, room in enumerate(rooms, 1):
        width, height = len(room["map"][0]), len(room["map"])
        floor = sum(c != "#" for row in room["map"] for c in row)
        minimum, limit = MINIMUM_ACTIONS[room["id"]], room["action_limit"]
        spare = limit - minimum if limit is not None else "—"
        doc.append(f"| {number} | {width}×{height} | {floor} | {minimum} | {limit or '무제한'} | {spare} |")
    doc += ["", "## 배치와 풀이", "", LEGEND, ""]
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
                if "seal" in link:
                    px, py = link["seal"]
                    svg.append(f'<path d="M{ox+x*cell+20},{oy+y*cell+20} L{ox+px*cell+20},{oy+py*cell+20}" stroke="#dda5ff" stroke-width="2" stroke-dasharray="2 4"/>')
                    x, y = px, py
                tx, ty = link[target]
                svg.append(f'<path d="M{ox+x*cell+20},{oy+y*cell+20} L{ox+tx*cell+20},{oy+ty*cell+20}" stroke="#ffd789" stroke-width="2" stroke-dasharray="4 4" opacity=".6"/>')
        svg.append("</g></svg>")
        (folder / f"stage-{number:02}-plan.svg").write_text("\n".join(svg), encoding="utf-8")
        doc += [f"### {number}번 — {room['title']}", ""]
        recordings = {}
        for link in room.get("worker_links", []):
            if "steps" in link:
                recordings.setdefault(tuple(link["station"]), []).append(link)
        records = []
        for links in recordings.values():
            ids = "/".join(link["id"] for link in links)
            mode = " · 한 턴 개방" if links[0].get("timed") else ""
            records.append(f"`{ids}` {links[0]['steps']}걸음{mode}")
        if records:
            doc += ["기록석 " + " · ".join(records), ""]
        doc += [NOTES[number-1], "", f"![좌표 배치도](screenshots/compact-rooms/stage-{number:02}-plan.svg)", ""]
    doc += ["## 검증", "", "- 실제 `Game.act`로 최단 풀이를 탐색했다. 분신 위치와 남은 재생 입력을 탐색 상태에 포함한다. 작은 방의 전체 상태 그래프로 이동 하한과 최단 결과를 독립 검사한다.",
            "- 4번 잔해·발판, 5번 잔해·거울·투입구·발판, 6번 거울, 7번 분신·발판, 8번 거울·분신은 생략하면 행동 제한 안에 완료할 수 없다.",
            "- 최소 행동과 1회 부족한 예산, 자원 보존, 전체 되돌리기, 작은 격자의 클릭 판정, 튜토리얼과 SDL 키보드 완주를 검사한다.",
            "- 화면을 열지 않고 SDL의 탑다운 모드에서 키보드 입력으로 여덟 방을 재생했다. 사람의 초회 체감 난이도는 미측정이다.", "",
            "```powershell", "python tools/solve_levels.py --check --check-mechanics --output docs/balance-report.json", "python -m unittest discover -q", "python tools/render_room_plans.py", "```", "",
            "[탐색 결과와 입력 SHA-256](balance-report.json) · [퍼즐 배치 규칙](퍼즐배치규칙.md)", ""]
    (ROOT / "docs/방크기조정.md").write_text("\n".join(doc), encoding="utf-8")
    print("8 room plans and docs/방크기조정.md generated")


if __name__ == "__main__":
    main()
