# 독립적인 2DGP 우주 일러스트

게임의 던전·정비소 세계관과 분리한 2DGP 시작 일러스트다. 짙은 파란 우주와 색색의 행성·궤도·픽셀 조각을 배경으로, 청록색 `2D`와 주황색 `GP`가 차례로 등장한다. 게임 캐릭터나 기존 게임 그림은 참조하지 않았다.

내장 `image_gen`으로 배경과 투명 글자 시트를 각각 새로 생성했다. [전체 프롬프트](prompts.json)를 보존한다.

- `sources/background.png`: 글자 없는 불투명 우주 배경
- `sources/letters.png`: 왼쪽 `2D`, 오른쪽 `GP`인 투명 2열 시트
- `sprites/2d.png`, `sprites/gp.png`: 게임이 읽는 개별 글자 묶음
- `manifest.json`: 원본·출력의 크기와 SHA-256, 셀 범위, 보이는 글자 영역

프로젝트 루트에서 `node tools/art/build-splash-motion.mjs assets/splash_identity_v2`로 시트를 분리한다. 이미지의 색상과 알파를 유지하며, 빈 셀·투명 여백·가장자리 잘림을 검사한다. Sharp는 제작 도구에만 필요하며 게임 실행 의존성은 추가하지 않는다.

등장 순서와 시간은 기존 로고 모드와 같다. 한국공학대학교 로고 2.2초, 2DGP 일러스트 2.6초, 게임 타이틀 순서다. 2DGP 화면의 0.12초부터 `2D`, 0.70초부터 `GP`가 등장한다. 학교 로고·게임 타이틀과 이전 버전 `splash_v1`, `splash_motion_v1`은 보존한다.

[실제 게임 캡처 미리보기](../../docs/screenshots/startup-identity-v2/startup-preview.gif)
