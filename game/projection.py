"""화면 상하좌우와 논리 격자의 방향을 일치시키는 정면 3/4 투영."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardProjection:
    width: int
    height: int

    @property
    def cell_width(self):
        return min(88, 1152 / self.width)

    @property
    def cell_height(self):
        return min(44, 528 / self.height)

    def screen(self, pos):
        x, y = pos
        return (640 + (x - (self.width - 1) / 2) * self.cell_width,
                438 - (y - (self.height - 1) / 2) * self.cell_height)

    def bounds(self, pos, inset=0):
        sx, sy = self.screen(pos)
        return (sx - self.cell_width / 2 + inset, sy - self.cell_height / 2 + inset,
                sx + self.cell_width / 2 - inset, sy + self.cell_height / 2 - inset)

    def ground_offset(self, u, v):
        """기존 224×112 마름모 바닥의 픽셀 오프셋을 새 평면에 옮긴다."""
        return (self.cell_width * (u / 224 - v / 112),
                self.cell_height * (u / 224 + v / 112))
