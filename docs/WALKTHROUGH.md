# 엘리베이터 접근 이동 데모

공개 웹: https://jino-222.github.io/Accessible_Wayfinding/

`01 실행 영상`에서 정상 이동, 영상 상실·복구, 엘리베이터 접근 중단을 선택합니다. 전체 과정은 세 실행의 일부를 편집한 60초 요약입니다. 나머지 세 영상은 각 실행을 처음부터 끝까지 재생합니다. 웹에서는 저장된 영상과 추정 기록을 재생하며, 이 탭에서는 브라우저 카메라로 위치를 찾지 않습니다. 별도의 `00 직접 이동` 탭에서 3D 이동과 모의 관측에 의한 안내 동작을 조작할 수 있습니다.

## 구현과 근거

NAVER LABS 강남역 B2 지도용 촬영 동선 중 관측지점 A에서 엘리베이터 앞 관측지점까지의 이동 축(22.06 m)을 사용합니다. 원본 XY에서 시작점을 빼고 진행 방향과 수직 방향으로 회전합니다. 높이와 복도 폭 6.8 m, 천장 높이 3.3 m, 문·기둥·안내판·포스터는 합성 설정입니다. 현재 강남역의 공간을 측량하거나 정확히 복원한 모델이 아닙니다.

자체 제작한 가상 장면의 지도용 RGB·깊이 이미지 108장으로 특징 지도를 구성합니다. 지도 촬영 높이는 1.5 m, 이동 카메라는 1.2 m입니다. 위치 추정 요청은 RGB, 카메라 보정값, 시각, 등록된 카메라 높이만 받습니다. 정답 위치·방향·층을 요청에 넣으면 거부합니다. RootSIFT 대응과 PnP로 계산한 위치·방향에 연속성·동선 이탈 검사를 적용합니다.

서로 다른 관측 3개를 확인한 후 화살표를 표시하고, 가림·응답 상실·접근 중단에는 안내를 숨깁니다. 자동 이동은 등록 경로를 따라가는 가상 사용자 동작이며, 자율주행 시험이 아닙니다. 실험의 카메라 정답 좌표는 별도 기록에서 오차 채점에만 사용합니다.

## Windows에서 다시 실행

검증 환경: Unity 6000.3.28f1, AR Foundation 6.3.5, Python 3.11. Unity Editor와 활성 라이선스가 필요합니다. XR Simulation은 Editor에서 실행하며 웹 영상 재생에는 Unity가 필요하지 않습니다.

```powershell
python -m venv .venv-walk
./.venv-walk/Scripts/python.exe -m pip install -r research/requirements-gangnam-walk.txt
```

Unity Hub의 설치 경로를 `-EditorRoot`에 지정합니다. 기본값은 이 프로젝트의 별도 설치 경로이며 다른 PC에서는 반드시 변경합니다.

```powershell
./scripts/run_gangnam_walk.ps1 -Mode Map -VisionPython './.venv-walk/Scripts/python.exe' -EditorRoot 'C:/Program Files/Unity/Hub/Editor/6000.3.28f1/Editor'
./scripts/run_gangnam_walk.ps1 -Mode Batch -RunId 'my-first-run' -VisionPython './.venv-walk/Scripts/python.exe' -EditorRoot 'C:/Program Files/Unity/Hub/Editor/6000.3.28f1/Editor'
```

`Map`은 기존 지도를 덮어쓰지 않습니다. 기본 데이터 위치는 `%LOCALAPPDATA%/AccessibleWayfinding/research/gangnam-walk`입니다. 변경 실험 전 기존 `map`과 `mapping`, 해당 실행 기록을 보관하고 새 지도를 만듭니다. `RunId`도 기존 실행과 겹치면 중단합니다.

Batch는 장면 3개 실행 → 원본 프레임·추정 기록 저장 → 정답과 비교 → MP4·웹 기록 생성을 수행합니다. `web/gangnam/assets/walk`가 결과입니다. 위치 추정 서버는 127.0.0.1:8768에서만 열립니다. 코드를 바꿨다면 기존 서버를 종료하고 다시 실행해야 합니다.

## 직접 이동

```powershell
./scripts/run_gangnam_walk.ps1 -Mode Editor -RunId 'manual-check' -VisionPython './.venv-walk/Scripts/python.exe' -EditorRoot 'C:/Program Files/Unity/Hub/Editor/6000.3.28f1/Editor'
```

Unity에서 Play를 누른 뒤 Game 화면의 `직접 이동 시작`을 선택합니다. 마우스 오른쪽과 WASD로 이동·회전하거나 `앞으로 0.5 m` 버튼을 사용합니다. `영상 가림 시험` → `영상 복구`, `엘리베이터 접근 중단` → `접근 재개`를 조작할 수 있습니다. 경로를 벗어나면 안내가 보류될 수 있습니다. 이 조작은 합성 환경에서만 검증합니다.

## 계산 기준과 제한

- 위치 오차: 추정 카메라 중심과 렌더링 정답 위치의 3차원 거리.
- 방향 오차: 추정·정답 회전의 상대 회전각.
- 정확한 출력 비율: 위치 0.5 m 및 방향 5° 이내인 관측 / 모든 입력 관측. 출력 실패도 분모에 포함.
- 안내 중 기준 초과: 화살표가 표시된 관측 중 위 오차 기준을 초과한 수. 기준은 연구용이며 안전 인증 기준이 아님.
- 영상 재생 15 fps와 추정 요청 간격 약 0.533초는 실험 시계. 요청 처리시간은 별도로 측정한 벽시계 시간. 모바일 실시간 성능을 나타내지 않음.

지도와 시험은 같은 합성 장면을 공유합니다. 서로 다른 시점·높이에서 촬영했지만 고유 포스터와 안내판이 특징 매칭을 쉽게 합니다. 이 결과를 실제 강남역 450장 평가의 정확도와 합치거나 실제 이용자의 안전·통행성을 입증하는 값으로 사용하지 않습니다.

공개 원본 사진은 출처·라이선스와 함께 제공합니다. Unity 공간·표지·포스터는 자체 제작 합성 자산이며 NAVER 원본 사진을 텍스처로 사용하지 않았습니다.
