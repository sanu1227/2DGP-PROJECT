# 레이어 애니메이션 타이틀

기존 `menu_v2/title.png`를 참조해 내장 `image_gen`으로 분리 제작했다. 기존 원본과 글자는 보존하며 새 레이어로 게임 타이틀을 구성한다. 전체 생성·투명 배경 정리 프롬프트는 `prompts.json`에 있다.

- `sources/background.png`: 로고·인물·불꽃을 제거한 던전 배경. 횃불 받침은 남아 있다.
- `sources/logo.png`: ‘용사가 / 지나간 자리’ 글자와 성벽·톱니·렌치가 있는 투명 로고.
- `sources/characters.png`: 위쪽 해골 손짓 4포즈, 아래쪽 수리공 눈 깜박임 4포즈.
- `sources/flames.png`: 횃불 8포즈.

`node tools/art/build-title-motion.mjs`로 로고 1개·인물 8개·불꽃 8개의 투명 PNG를 추출한다. 투명 여백·셀 경계·포즈 고유성을 검사하고 크기·발 기준점·SHA-256을 `manifest.json`에 저장한다. 원본의 알파 채널을 보존하며 포즈를 임의로 새로 그리지 않는다.
