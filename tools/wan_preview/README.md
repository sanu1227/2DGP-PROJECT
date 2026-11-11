# 수리공 Wan 2.2 영상 샘플

기존 만화의 수리공을 입력으로 사용하는 로컬 영상 생성 환경이다. 게임 실행 코드와 별개로 동작한다.

## 설치된 환경

- 위치: `C:\Users\rlato\AI\ComfyUI`
- Python 3.13 가상환경: `.venv`
- CUDA 13.0 PyTorch, RTX 4060 8GB
- 공식 Wan 2.2 TI2V 5B, UMT5 FP8 인코더, Wan 2.2 VAE
- 모델 원본 합계 약 18.1 GB. 다운로드 뒤 각 파일의 SHA-256을 확인했다.
- 설치 버전: `installation.json`, Python 패키지: `requirements-installed.txt`
- 모델 출처·고정 리비전·해시: `models.json`

ComfyUI와 대용량 모델은 게임 저장소 밖에 설치했다. 사용자 Python의 기존 패키지는 변경하지 않는다.

## 실행

프로젝트 루트의 PowerShell에서:

```powershell
./tools/wan_preview/start_server.ps1
```

서버는 `127.0.0.1:8189`만 수신한다. 브라우저나 콘솔 창을 열지 않으며 커스텀 노드를 로드하지 않는다. 로그와 실행 PID는 ComfyUI의 `preview_logs`에 기록한다. 첫 실행 시 모듈 초기화로 준비까지 시간이 걸릴 수 있다.

준비 확인:

```powershell
Invoke-RestMethod http://127.0.0.1:8189/system_stats
```

샘플 생성:

```powershell
& "$env:USERPROFILE/AI/ComfyUI/.venv/Scripts/python.exe" tools/wan_preview/make_preview.py --comfy-root "$env:USERPROFILE/AI/ComfyUI"
```

## 생성 설정

- 입력: `assets/story_overtime_v1/act_01.png`의 오른쪽 아래 수리공 컷
- 장면: 터덜터덜 걷기 → 멈추기 → 어깨를 늘어뜨리며 한숨
- 640×480, 24fps, 20 steps, CFG 5, UniPC/simple
- 8GB VRAM에 맞춰 diffusion weights를 실행 시 FP8로 변환하고, 메모리 오프로딩 및 타일 VAE 디코딩 사용
- Wan의 시간 축 규격에 맞춰 97프레임을 생성한 뒤 마지막 한 프레임을 제외한다. 최종 목표는 96프레임, 정확히 4초이다. 프레임 복제나 보간으로 채우지 않는다.
- 결과 원본은 ComfyUI의 `output/dungeon_preview`에 저장된다.
- API 워크플로와 요청·실행 기록은 `assets/worker_video_v1`에 저장된다.

영상의 시간·코덱 검사와 실제 동작의 시각 검토는 별개다. 파일 생성 성공만으로 걷기와 한숨 표현의 성공을 판단하지 않는다.

## 모델 복원

Python 표준 라이브러리만 사용하는 다운로드 도구:

```powershell
python tools/wan_preview/download_models.py --comfy-root "$env:USERPROFILE/AI/ComfyUI"
```

고정된 공식 모델을 내려받고 크기와 SHA-256을 검사한다. 중단된 `.partial` 파일은 이어받는다.

## 출처

- [ComfyUI 공식 저장소](https://github.com/Comfy-Org/ComfyUI)
- [Wan 2.2 공식 ComfyUI 안내](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [Wan 2.2 모델](https://huggingface.co/Comfy-Org/Wan-2.2)
- [Wan 2.1 텍스트 인코더](https://huggingface.co/Comfy-Org/Wan-2.1)
