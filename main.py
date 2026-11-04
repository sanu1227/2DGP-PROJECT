"""용사가 지나간 자리: 저장소 밖에서도 실행 가능한 진입점."""

import argparse
import sys

from game.levels import load_levels


def main() -> int:
    parser = argparse.ArgumentParser(description="용사가 지나간 자리 — 기초 프로토타입")
    parser.add_argument("--stage", type=int, default=1, help="시작할 방 번호 (1부터)")
    parser.add_argument("--check", action="store_true", help="창 없이 스테이지 데이터 검사")
    parser.add_argument("--smoke-frames", type=int, help="지정 프레임만 표시한 뒤 종료 (창 검사)")
    args = parser.parse_args()
    if args.smoke_frames is not None and args.smoke_frames < 1:
        parser.error("--smoke-frames는 1 이상이어야 합니다.")
    try:
        levels = load_levels()
        if not 1 <= args.stage <= len(levels):
            parser.error(f"--stage는 1~{len(levels)} 사이여야 합니다.")
        if args.check:
            for number, level in enumerate(levels, 1):
                print(f"{number}. {level.title} ({level.width}x{level.height}) OK")
            return 0
        # 논리 검사와 테스트는 SDL 또는 화면 없이 실행할 수 있다.
        from game.view import run

        run(levels, args.stage - 1, args.smoke_frames)
    except ModuleNotFoundError as error:
        print(f"의존성을 불러올 수 없습니다: {error}\npython -m pip install -r requirements.txt", file=sys.stderr)
        return 1
    except (ValueError, OSError, RuntimeError) as error:
        print(f"실행 오류: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
