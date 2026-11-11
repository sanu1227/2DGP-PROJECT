# 2DGP 순차 등장 레이어

`assets/splash_v1/2dgp.png`를 참조해 내장 `image_gen`으로 배경과 투명 글자 두 묶음을 따로 제작했다. 전체 프롬프트는 `prompts.json`에 보존한다.

- `sources/background.png`: 글자만 제거하고 석조 아치·해골·수리공·작업 섬을 유지한 배경
- `sources/letters.png`: 왼쪽 `2D`, 오른쪽 `GP`인 투명 2열 시트
- `sprites/2d.png`, `sprites/gp.png`: 게임에서 사용하는 개별 글자 묶음
- `manifest.json`: 원본·출력 SHA-256, 크기, 셀 범위와 보이는 글자 영역

`node tools/art/build-splash-motion.mjs`로 시트를 분리한다. 알파와 색상을 그대로 유지하며, 투명 여백과 잘림 여부를 검사한다. 생성 도구와 Sharp는 개발용이고 게임 실행 의존성을 추가하지 않는다.

배경 위로 `2D`가 먼저 들어오고 `GP`가 뒤이어 붙는다. 각 묶음은 약간 커졌다가 안착하며, 완성된 글자를 보여 준 뒤 기존 타이틀로 이어진다. 기존 단일 일러스트는 보존용이며 애니메이션 재생에는 이 레이어들을 사용한다.
