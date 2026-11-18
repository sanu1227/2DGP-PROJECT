"""방 클리어 기록과 이어하기 지점을 저장한다."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def progress_path():
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        root = Path.home() / ".local" / "share"
    return Path(root) / "2DGP-DungeonRestoration" / "progress.json"


def atomic_write(path, data):
    with NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        pending = Path(temp.name)
        try:
            temp.write(data)
            temp.flush()
            os.fsync(temp.fileno())
            temp.close()
            pending.replace(path)
        finally:
            temp.close()
            pending.unlink(missing_ok=True)


class Progress:
    def __init__(self, path, levels):
        self.path = path
        self.backup = path.with_suffix(".bak")
        self.ids = tuple(level.id for level in levels)
        self.records = {}
        self.notice = ""
        self.read_only = False
        self.saved = {}
        for candidate in (self.path, self.backup):
            try:
                raw = candidate.read_bytes()
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError
                version = data.get("version")
                if type(version) is int and version > 2:
                    self.read_only = True
                    self.notice = "더 최신 버전의 저장 파일입니다."
                    break
                rooms = data.get("completed")
                if type(version) is int and version == 1 and isinstance(rooms, list):
                    if any(not isinstance(room, str) for room in rooms):
                        raise ValueError
                    rooms = dict.fromkeys(rooms)
                elif (type(version) is not int or version != 2 or not isinstance(rooms, dict)
                      or any(count is not None and (type(count) is not int or count <= 0)
                             for count in rooms.values())):
                    raise ValueError
            except FileNotFoundError:
                continue
            except (OSError, ValueError):
                self.notice = "진행 기록을 읽을 수 없습니다."
                continue
            self.records = rooms
            self.saved = rooms.copy()
            if candidate == self.backup:
                self.notice = "백업에서 진행 기록을 불러왔습니다."
            break

    @property
    def completed(self):
        return self.records.keys()

    @property
    def checkpoint(self):
        return next((i for i, room in enumerate(self.ids) if room not in self.completed), None)

    def complete(self, room, moves):
        best = self.records.get(room)
        self.records[room] = moves if best is None else min(best, moves)
        if self.read_only or self.records == self.saved:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.saved:
                atomic_write(self.backup, self.encode(self.saved))
            atomic_write(self.path, self.encode(self.records))
        except OSError:
            self.notice = "진행 기록을 저장할 수 없습니다."
        else:
            self.saved = self.records.copy()
            self.notice = ""

    @staticmethod
    def encode(rooms):
        return json.dumps({"version": 2, "completed": rooms}, indent=2, sort_keys=True).encode("utf-8")
