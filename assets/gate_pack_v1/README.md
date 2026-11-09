# 발판 연동 격자문

기존 석축과 황동 발판을 참고하여 내장 `image_gen`으로 닫힘·열림 원본을 제작했다. 열린 문은 격자가 상부로 올라가고 중앙은 투명하다. 원본과 전체 프롬프트는 [sources/prompts.json](sources/prompts.json)에 보존한다.

`node tools/art/build-gates.mjs`로 원본 두 장에 동일한 좌표 변환을 적용한다. 스프라이트는 512×512이며 바닥 접점은 `(256, 384)`, 게임 배율은 기존 224×112 바닥 타일 기준이다. 변환은 캔버스 전체를 기준으로 하므로 열린 문을 개별 알파 영역으로 잘라 정렬하지 않는다. 기본 방향은 화면의 왼쪽 아래에서 오른쪽 위로 이어지는 벽이며, 반대 축은 런타임 좌우 반전으로 처리한다.

검증: `python tools/art/check.py --root assets/gate_pack_v1 --window`. PNG 크기·RGBA·SHA-256, 제작 중 투명 여백·잘림, SDL 개별 이미지와 아틀라스 표시를 검사한다. 게임 통합 검사는 `python -m tests.smoke_gates`로 수행한다.
