"""그림판에 표시할 배선도와 저장된 PNG의 연결 판정."""

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFilter, ImageFont


CELL = 52
LEFT, TOP = 26, 116
PAD = 13
CHANNEL = 20
FONT = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Jua-Regular.ttf"
INK = (29, 60, 82)
AMBER = (174, 99, 24)
TEAL = (0, 108, 109)


def paper_point(pos):
    x, y = pos
    return LEFT + x * CELL + CELL // 2, TOP + y * CELL + CELL // 2


def paper_size(level):
    return max(540, 2 * LEFT + level.width * CELL), TOP + level.height * CELL + 65


def circle(center, radius):
    x, y = center
    return x - radius, y - radius, x + radius, y + radius


def channel_box(start, end):
    xs, ys = zip(start, end)
    return min(xs) - CHANNEL, min(ys) - CHANNEL, max(xs) + CHANNEL + 1, max(ys) + CHANNEL + 1


def write_blueprint(path, level, selected):
    sheet = Image.new("RGB", paper_size(level), "#e9f1f6")
    draw = ImageDraw.Draw(sheet)
    title = ImageFont.truetype(FONT, 30)
    body = ImageFont.truetype(FONT, 19)
    small = ImageFont.truetype(FONT, 16)
    width, height = sheet.size
    draw.rectangle((0, 0, width, 53), fill="#25445b")
    draw.text((LEFT, 13), f"마력 배선도  /  {level.title}", font=title, fill="white")
    draw.text((LEFT, 65), "검은색 선 도구로 같은 번호 단자 2개를 잇고 Ctrl+S.", font=body, fill=INK)
    guide = ("배선은 한 쌍만 연결할 수 있어요. 기존 선은 흰색으로 지우세요."
             if len(level.circuits) > 1 else "저장하고 게임으로 돌아가 레버를 당기세요.")
    draw.text((LEFT, 89), guide, font=small, fill=INK)
    for y, row in enumerate(level.rows):
        for x, tile in enumerate(row):
            sx, sy = LEFT + x * CELL, TOP + y * CELL
            draw.rectangle((sx, sy, sx + CELL, sy + CELL),
                           fill="#d0dfe8" if tile == "#" else "#f1f6fa", outline="#b9cddc")

    for index, circuit in enumerate(level.circuits, start=1):
        color = AMBER if index == 1 else TEAL
        points = tuple(map(paper_point, circuit.path))
        start, end = map(paper_point, circuit.gap)
        draw.line(points, fill=color, width=5, joint="curve")
        draw.rounded_rectangle(channel_box(start, end), radius=14,
                               fill="white", outline="#b9cddc", width=2)
        draw.line((start, end), fill="#c6d7e3", width=2)
        for terminal in (start, end):
            draw.ellipse(circle(terminal, PAD), fill="#ffffff", outline=color, width=3)
            draw.text(terminal, str(index), fill=color, font=small, anchor="mm")
        if selected == index:
            draw.line((start, end), fill="black", width=5)
        for endpoint, label in zip((points[0], points[-1]), circuit.labels):
            draw.rounded_rectangle((endpoint[0] - 43, endpoint[1] + 11,
                                    endpoint[0] + 43, endpoint[1] + 33),
                                   radius=5, fill="#25445b")
            draw.text((endpoint[0], endpoint[1] + 22), label, fill="white", font=small, anchor="mm")
        draw.text((LEFT, height - 57 + (index - 1) * 24),
                  f"{index}   {circuit.labels[0]}  /  {circuit.labels[1]}", font=body, fill=color)
    sheet.save(path, format="PNG")


def read_blueprint(path, level):
    with Image.open(path, formats=("PNG",)) as saved:
        if saved.size != paper_size(level):
            raise ValueError("도면 크기가 바뀌었습니다. 그림판에서 크기 변경을 되돌리세요.")
        sheet = saved.convert("RGBA")
    # 투명 영역은 빈 종이로 취급하고 검은 잉크만 배선으로 읽는다.
    paper = Image.new("RGBA", sheet.size, "white")
    paper.alpha_composite(sheet)
    black = paper.convert("L").point(lambda value: 255 if value <= 35 else 0)
    connected = []
    for index, circuit in enumerate(level.circuits, start=1):
        start, end = map(paper_point, circuit.gap)
        area = channel_box(start, end)
        # 1px 대각선도 이어서 인식하도록 잉크의 경계를 한 픽셀 넓힌다.
        mask = black.crop(area).filter(ImageFilter.MaxFilter(3))
        a, b = ((x - area[0], y - area[1]) for x, y in (start, end))
        draw = ImageDraw.Draw(mask)
        draw.ellipse(circle(a, PAD), fill=255)
        draw.ellipse(circle(b, PAD), fill=255)
        ImageDraw.floodfill(mask, a, 128)
        if mask.getpixel(b) == 128:
            connected.append(index)
    if len(connected) > 1:
        raise ValueError("도선은 하나뿐입니다. 한쪽 선을 흰색으로 지우세요.")
    return connected[0] if connected else 0


def launch_paint(path):
    subprocess.Popen(["mspaint.exe", str(path)])


class BlueprintEditor:
    def __init__(self):
        self.folder = TemporaryDirectory(prefix="dungeon-blueprint-", ignore_cleanup_errors=True)
        self.serial = 0
        self.reset()

    def reset(self):
        self.path = None
        self.stamp = self.pending = None
        self.next_check = 0.0
        self.notice = ""

    def open(self, game):
        blocker = game.blueprint_blocker()
        if blocker:
            self.notice = blocker
            return
        try:
            if self.path is None or not self.path.exists():
                self.serial += 1
                path = Path(self.folder.name) / f"{game.level.title} 도면 {self.serial}.png"
                write_blueprint(path, game.level, game.state.circuit)
                self.stamp = self.file_stamp(path)
                self.pending = None
                self.path = path
            launch_paint(self.path)
        except OSError:
            self.notice = "그림판을 열 수 없습니다. 설치 상태를 확인하세요."
        else:
            self.notice = "그림판에서 검은 선을 그리고 Ctrl+S로 저장"

    @staticmethod
    def file_stamp(path):
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size

    def update(self, game, now):
        if self.path is None or now < self.next_check or game.blueprint_blocker():
            return
        self.next_check = now + .15
        try:
            stamp = self.file_stamp(self.path)
        except OSError:
            return
        if stamp == self.stamp:
            self.pending = None
            return
        if stamp != self.pending:
            self.pending = stamp
            return
        # 그림판이 쓰는 중인 파일을 읽지 않도록 두 번 확인한다.
        try:
            circuit = read_blueprint(self.path, game.level)
        except (OSError, Image.DecompressionBombError):
            self.notice = "도면을 읽을 수 없습니다. PNG로 다시 저장하세요."
        except ValueError as error:
            self.notice = str(error)
        else:
            game.apply_circuit(circuit)
            self.notice = (f"도면 반영 · {game.level.circuits[circuit - 1].labels[-1]} 연결"
                           if circuit else "도면 반영 · 두 단자를 잇는 선이 없습니다.")
        self.stamp = stamp

    def close(self):
        self.folder.cleanup()
