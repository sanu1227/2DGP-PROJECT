# 시작 로고 화면 v1

게임 실행 시 한국공학대학교 공식 시그니처, 2DGP 일러스트, 기존 게임 타이틀 순서로 표시한다.

## 한국공학대학교

- 출처: [학교 공식 UI 시그니처](https://www.tukorea.ac.kr/tukorea/8200/subview.do)
- 원본: [공식 Illustrator 파일](https://www.tukorea.ac.kr/sites/tukorea/files/UI/signature.ai), `sources/tukorea-signature.ai`에 그대로 보존
- 사용한 형태: 세로형 기본 시그니처(심벌·한글 교명·영문 교명)
- 생성형 AI를 사용하지 않았다. 공식 벡터의 색상·글자·비율을 유지하고 해당 영역만 PNG로 추출했다. 학교 로고의 권리는 한국공학대학교에 있다.
- 추출: Poppler `pdftoppm -f 1 -singlefile -r 720 -x 1150 -y 7900 -W 1150 -H 1050 -png sources/tukorea-signature.ai tukorea-raster`
- 위 PNG에서 Sharp로 `left=60, top=31, width=980, height=890` 영역을 잘라 흰 여백을 정리한 결과가 `tukorea.png`다. 실제 로고 모양은 편집하지 않았다.
- 확인일: 2026-11-11

## 2DGP

- `2dgp.png`: 내장 `image_gen`으로 새로 제작한 불투명 5:3 일러스트
- 기존 `assets/menu_v2/title.png`는 화풍과 캐릭터의 참조로만 사용했다.
- 청록색 던전 정비소, 석재·금빛 2DGP 글자, 해골 조수와 지친 수리공으로 구성했다.
- 전체 프롬프트와 참조 경로: `prompts.json`
- PNG는 게임 실행 시 직접 사용한다. 원본 크기·SHA-256은 `manifest.json`에 기록한다.

기존 타이틀·만화 에셋을 덮어쓰지 않는다. 다운로드·변환·이미지 생성 도구는 개발용이며 게임 실행에 추가 의존성이 필요하지 않다.
