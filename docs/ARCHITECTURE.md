# 구조

| 위치 | 기능 |
| --- | --- |
| `web/gangnam/` | 설치 없이 실행하는 정적 웹 데모 |
| `research/` | Python 특징 지도·영상 위치 추정·평가 |
| `unity/AccessibleStation/` | AR Foundation·XR Simulation 기반 합성 영상 생성과 이동 실험 |
| `tests/`, `research/tests/` | 경로·안내 상태·기하·위치 추정 검사 |
| `docs/evidence/` | 최종 실행의 설정·예측·평가·브라우저 검수 근거 |
| `portfolio/` | 최종 9쪽 PDF, Overleaf 소스, 미리보기, 지표 설명 |

## 서로 다른 위치 입력

- **공개 이미지:** 지도용 RGB·깊이로 특징 지도를 구성하고 질의 이미지로 위치·방향 추정. 예측 저장 후 정답을 읽어 채점.
- **합성 RGB:** Unity 렌더링 → `gangnam_walk_service.py`의 RootSIFT/PnP → 안내 상태. 정답 위치는 별도 평가 기록에 저장.
- **웹 직접 이동:** `explorer-engine.mjs`의 모의 관측 → 안내 상태 → `explorer-scene.mjs`의 Three.js 장면. RGB 위치 인식 미연결.

## 화면과 데이터

`engine.mjs`는 유향 경로·층 전환·위치 상태, `corridor-engine.mjs`는 관측 동선 투영과 접근 범위를 처리합니다. `app.mjs`와 `corridor.mjs`가 화면과 관측 재생을 담당합니다.

`walk.mjs`는 `assets/walk/`의 영상·추정 기록·안내 상태를 동기화합니다. `explorer.mjs`는 키보드·터치 조작과 관측 중단·복구·시설 접근 중단을 연결합니다.

`web/gangnam/data/`는 출입 동선 도식, 관측 동선의 미터 좌표, 추정 관측, 실험 요약, 출처를 분리합니다. 도식과 현재 실제 시설의 좌표 정합은 미검증입니다.

## 재현

- 공개 이미지: [REPRODUCE.md](REPRODUCE.md)
- Unity 합성 RGB·직접 조작: [WALKTHROUGH.md](WALKTHROUGH.md)
- 검증 항목·지표·한계: [VALIDATION.md](VALIDATION.md)
