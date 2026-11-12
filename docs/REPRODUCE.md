# Python 위치 인식 재현

웹 체험은 저장된 결과를 읽으므로 아래 환경이 없어도 실행됩니다. 아래 절차는 원본 자료를 받아 추론을 다시 수행하는 선택 절차입니다. 전체 데이터와 특징 지도에 수십 GB의 여유 공간을 두세요.

## 1. 환경과 데이터

실험 환경은 Python 3.11, CPU PyTorch, OpenCV입니다. 버전은 `research/requirements-learned.txt`와 그 파일이 포함하는 `requirements.txt`에 고정했습니다. 운영체제별 wheel 제공 여부는 다를 수 있습니다.

```sh
python -m venv .venv-vision
# Windows: .venv-vision/Scripts/activate
# macOS/Linux: source .venv-vision/bin/activate
python -m pip install -r research/requirements-learned.txt
python -m scripts.acquire_gangnam --metadata-only
```

다운로드된 라이선스를 확인한 후:

```sh
python -m scripts.acquire_gangnam --parts mapping validation test
python -m research.gangnam
python -m research.build_rgbd_map --study gangnam
```

`WAYFINDING_RESEARCH_DATA` 환경변수로 대용량 저장 위치를 지정할 수 있습니다. 기본값은 Windows의 로컬 앱 데이터 또는 다른 OS의 사용자 캐시 아래 `AccessibleWayfinding/research`입니다. 다운로드 도구는 공식 SHA256과 압축 내부 경로를 검사합니다.

## 2. 정답이 있는 비교

```sh
python -m research.learned_matching --split development --limit 12
python -m research.learned_matching --split evaluation
```

지도용 4,518장 중 센서별 4번째 촬영 간격으로 1,134장을 사용합니다. 검증 916장은 촬영 세션 단위로 development 466장, evaluation 450장으로 나눕니다. 이 evaluation은 기존 실험에서 확인한 자료이므로, 후속 비교에서 독립적인 새 시험이라고 주장하지 않습니다.

양 방식은 동일한 검색 후보 3장·SIFT 특징·깊이·PnP를 사용합니다. LightGlue만 사전학습 매칭을 적용합니다. 예측 JSONL 저장을 마친 뒤 평가 정답을 읽습니다. 검색·후보 선정에는 평가 정답이 들어가지 않습니다. 점수 계산 실패와 출력 실패도 전체 분모에 남깁니다.

## 3. 엘리베이터 접근 체험

```sh
python -m research.gangnam_demo_map
python -m research.gangnam_demo_inference docs/gangnam-test-demo-queries.json
python -m research.gangnam_demo_inference docs/gangnam-test-elevator-queries.json
python -m scripts.export_gangnam_corridor
python -m scripts.finalize_gangnam_assets
node scripts/audit_gangnam_release.mjs
```

test의 다른 촬영 세션·카메라에서 연속 구간 41장과 26장을 선택했습니다. 영상으로 관측 범위를 검토한 뒤 고른 **체험 사례**이며 무작위 성능 표본이 아닙니다. test 정답은 공개되지 않아 정확도는 null로 남깁니다.

지도 체크포인트는 mapping 사진 3장과 촬영 위치에서 등록했습니다. 해당 영상의 엘리베이터 문과 B1/B2 표지를 확인했지만, 현재 시설 일련번호·문턱 실측·출구 동선과의 정합은 미완료입니다. 경로 길이는 XY 촬영 동선을 따라 계산한 길이입니다.

## 4. 검사

```sh
python -m pytest research/tests -q
node --test tests/gangnam-demo.test.mjs tests/gangnam-corridor.test.mjs tests/gangnam-walk.test.mjs tests/gangnam-explorer.test.mjs
```

저장소에는 좌표변환·깊이 역투영·PnP·후보 순위·합성 이동 API 관련 Python 검사 24개와 웹 로직 검사 30개를 포함합니다. 입력 영상과 지도 캐시의 크기 때문에 전체 추론을 CI에서 다시 돌리지는 않습니다.

결과 파일은 `docs/evidence`와 `web/gangnam/data`에 있습니다. 실행 시간은 하드웨어에 따라 달라지며 웹 재생 속도는 추론 성능 측정값이 아닙니다. 데모는 카메라를 열거나 서버에서 새 추론을 하지 않습니다.
