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
    "서쪽 납골 구역과 동쪽 묘실의 뼈를 작업대 한 곳에 모은다. 서쪽 작업대는 28회, 동쪽 작업대는 36회에 끝낼 수 있다. 중앙 초소에 병사를 세운 뒤 출구 방향으로 나간다.",
    "북·남 서가의 재료를 꺼내고 두 입구의 함정을 고친다. 북쪽 안의 레버도 두 함정을 가동하지만, 그 자리에서 가동하면 돌아올 통로를 잃는다. 출구 근처 레버로 봉쇄할 길을 살펴야 한다.",
    "간수 통로의 잔해를 P1에 밀어 첫 감방을 연다. 그 안의 뼈를 감방 입구 앞 P2에 놓고, 두 번째 뼈는 서쪽 벽 앞 P3에 둔다. 안쪽 무기고에 가려면 P2와 P3을 함께 열어 둬야 한다. 부품을 꺼낸 뒤 남쪽에서 병사를 조립해 동쪽 끝 초소를 채우고, 하단 복도에서 레버를 당긴 뒤 출구로 나간다.",
    "이동 거울을 수신기 열에 맞추고 아래로 돌린 뒤 잔해를 밀어 M1 광로를 연다. 동쪽 뼈를 C1로 보내 남쪽 집수실을 열고, 안쪽 뼈를 꺼낸 뒤 발판의 뼈를 회수한다. 두 뼈로 병사를 조립해 초소를 채운다. 같은 거울을 위로 돌려 M2를 열고 남서쪽 출구로 나간다.",
    "차광 블록을 위로 밀어 M1 보관실의 뼈를 꺼내고 중앙 P1 발판에 둔다. 블록을 아래로 밀어 M2 작업실을 열면 P1 뒤에서 두 번째 뼈와 부품을 꺼낼 수 있다. 뼈를 회수해 병사를 조립하고, 부품은 광로를 다시 M1로 전환해 보관실 입구의 함정에 설치한다. 병사를 배치한 뒤 레버를 가동해 남서쪽 출구로 복귀한다.",
    "J1에 위, 아래, 위를 기록해 첫 문을 연다. 부품으로 P1을 눌러 해골을 꺼낸 뒤 같은 부품을 P2로 옮겨 두 번째 인부의 길을 연다. J2에 오른쪽, 위, 위, 위를 기록한다. 인부가 금고 발판에서 멈추면 P2 부품을 회수한다. 그 부품을 금고까지 가져가 함정을 설치하고 레버를 가동한다.",
    "거울을 아래로 돌리고 차광 블록을 밀어 M1 보급실을 연다. 꺼낸 부품으로 중앙 함정을 설치한 뒤 위쪽 M2 광로로 전환한다. J1에는 위, 위, 오른쪽, 오른쪽을, J2에는 아래, 오른쪽, 아래, 오른쪽을 기록해 인부 둘을 각자의 발판에 둔다. 안쪽 부품으로 두 번째 함정을 고친 뒤 중앙으로 돌아온다. 레버를 당기면 M2 쪽 길이 함정으로 막히므로, 거울을 아래로 돌려 M1 쪽 출구를 연다.",
)
LEGEND = "@ 출발 · E 출구 · P 부품 · B 뼈 · K 해골 · T 함정 · L 레버 · A 조립대 · S 초소 · F 발판 · G 문 · C 투입구 · O 배출구 · Q 광원 · M 거울 · N 이동 거울 · Y 수신기 · R 잔해 · J 기록석 · U 문양"


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
        track = {tuple(pos) for pos in room.get("rubble_track", [])}
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
                if (x, y) in track:
                    color = "#88643e"
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
            mode = " · 한 번 기록"
            records.append(f"`{ids}` {links[0]['steps']}걸음{mode}")
        if records:
            doc += ["기록석 " + " · ".join(records), ""]
        doc += [NOTES[number-1], "", f"![좌표 배치도](screenshots/compact-rooms/stage-{number:02}-plan.svg)", ""]
    doc += ["## 검증", "", "- 실제 `Game.act`로 최단 풀이를 탐색했다. 해골 인부의 현재 위치와 아직 수행할 방향을 탐색 상태에 포함한다. 작은 방의 전체 상태 그래프로 이동 하한과 최단 결과를 독립 검사한다.",
            "- 4번 잔해·발판, 5번 잔해·거울 밀기와 회전·투입구·발판, 6번 차광 블록·발판, 7번 인부·발판, 8번 차광 블록·거울·인부는 생략하면 행동 제한 안에 완료할 수 없다.",
            "- 최소 행동과 1회 부족한 예산, 자원 보존, 전체 되돌리기, 작은 격자의 클릭 판정, 튜토리얼과 SDL 키보드 완주를 검사한다.",
            "- 화면을 열지 않고 SDL의 탑다운 모드에서 키보드 입력으로 여덟 방을 재생했다. 사람의 초회 체감 난이도는 미측정이다.", "",
            "```powershell", "python tools/solve_levels.py --check --check-mechanics --output docs/balance-report.json", "python -m unittest discover -q", "python tools/render_room_plans.py", "```", "",
            "[탐색 결과와 입력 SHA-256](balance-report.json) · [퍼즐 배치 규칙](퍼즐배치규칙.md)", ""]
    (ROOT / "docs/방크기조정.md").write_text("\n".join(doc), encoding="utf-8")
    print("8 room plans and docs/방크기조정.md generated")


if __name__ == "__main__":
    main()
