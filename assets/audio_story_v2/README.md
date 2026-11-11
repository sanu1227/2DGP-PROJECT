# 만화·슬랩스틱 효과음 v2

기존 파형 합성 효과음 대신 공개된 악기·충돌·발소리·목소리 소스를 편집하고 겹쳐 만든 게임 전용 효과음이다. 원본 v1은 `assets/audio_story_v1/`에 보존한다. 새로 사인파·노이즈를 만들어 소리의 본체로 사용하는 방식은 사용하지 않았다.

- `hero_arrival.wav`: 상승하는 짧은 색소폰 팡파르와 오케스트라 타격음
- `dungeon_collapse.wav`: 나무·금속·유리의 와장창, 냄비 울림, 연속 잔해 충돌과 마지막 코믹한 튕김
- `boss_bark.wav`: 짧고 신경질적인 크리처 호통에 작은 충격을 겹친 소리. 실제 대사 낭독은 아니다.
- `step_left.wav`, `step_right.wav`: 콘크리트 발 디딤·옷 스침·작은 만화 바운스. 좌우 발은 다른 소스와 음높이를 사용한다.
- `worker_sigh.wav`: 실제 사람의 한숨에 작게 처지는 색소폰 반응음을 겹친 소리

모두 44,100Hz·스테레오·16비트 PCM이다. 각 클립의 길이·피크·RMS·SHA-256·레이어별 소스·시작 시간·게인·재생 속도는 `manifest.json`에 기록한다. 게임은 기존 이벤트 시간과 음량 78/128을 사용한다. 마왕 음원은 두 호통 사이에 끝나며 한숨도 다음 컷 전에 끝난다.

## 출처와 라이선스

이 소스는 프로젝트가 직접 녹음한 자료가 아니다. 아래 제작자의 소스를 편집한 것이며 저작권과 표시는 원 저작자에게 따른다.

| 제작자 | 원본 | 라이선스 | 사용·변경 |
| --- | --- | --- | --- |
| Kenney | [Music Jingles](https://kenney.nl/assets/music-jingles) | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) | SAX00·SAX10·HIT00의 여백 제거, 재생 속도·음량 변경, 겹치기 |
| Kenney | [Impact Sounds](https://kenney.nl/assets/impact-sounds) | CC0 1.0 | 콘크리트 발소리와 나무·금속·유리·깡통 충돌을 발췌·배치·합성 |
| Kenney | [RPG Audio](https://kenney.nl/assets/rpg-audio) | CC0 1.0 | 냄비와 옷 스침의 여백·길이·음량 편집 |
| wjtaylor | [sigh](https://freesound.org/people/wjtaylor/sounds/265249/) | CC0 1.0 | 공개 고음질 미리듣기에서 PCM 변환, 여백·음량 편집, 악기음과 겹치기 |
| qubodup | [Small Evil Creature Attack Shout 1](https://freesound.org/people/qubodup/sounds/744792/) | CC0 1.0 | 공개 고음질 미리듣기에서 PCM 변환, 재생 속도·음량 변경, 충격음과 겹치기 |
| Blender Foundation | [Funny Comic Cartoon Bounce Sound — Yo Frankie!](https://opengameart.org/content/funny-comic-cartoon-bounce-sound) (Lamoot 게시) | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) | 원본 FLAC을 PCM 변환, 여백·속도·음량 변경 후 발걸음·붕괴음에 혼합 |

Blender Foundation의 바운스 원본 및 이를 포함한 `step_left.wav`, `step_right.wav`, `dungeon_collapse.wav`를 이용·재배포할 때 위 저작자·출처·라이선스·변경 표시를 함께 유지해야 한다. 프로젝트 전체의 라이선스가 해당 원본의 표시 의무를 없애지 않는다. 원 저작자가 이 게임을 보증한다는 의미는 아니다.

Kenney의 패키지 라이선스 원문은 `licenses/`에 보존했다. 원본은 `sources/raw/`, 변환한 PCM은 `sources/pcm/`, 각 소스의 페이지·라이선스·해시는 `sources.json`에 기록한다. Mixkit 음원은 사용하지 않았다. Runway 생성이나 유료 결제도 사용하지 않았다.

## 재현

1. pico2d가 있는 Python에서 `python tools/audio/decode-cartoon-sources.py`로 원본을 PCM으로 변환한다. SDL 오디오를 dummy로 지정하며 창을 열거나 소리를 재생하지 않는다.
2. NumPy·SciPy가 있는 개발용 Python에서 `python tools/audio/build-cartoon-sounds.py`를 실행한다. 다상 필터 리샘플링, 짧은 양끝 감쇠, 작은 소프트 압축으로 편집한다. 결과 WAV와 manifest를 함께 만든다.
3. `python -m tests.smoke_menu_media`로 실제 SDL 믹서의 로딩·재생·정지·재개·컷 이동을 dummy 드라이버에서 검사한다.

게임 실행에는 기존 pico2d 외에 추가 패키지가 필요하지 않다. 원본과 v1 미리듣기는 보존하고 현재 결과는 `docs/audio/cartoon-v2/`에 기록한다.
