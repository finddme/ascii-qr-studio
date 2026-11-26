# ASCII QR Studio

이미지와 URL을 입력하면 **이미지 → ASCII 아트 → ASCII QR 패턴 → 정적 QR 이미지**를 만드는 로컬 도구입니다. 명암을 보존하는 문자 렌더링과 독립 QR 디코더 검증을 제공합니다.

## 시작하기

필요 환경은 Docker Engine과 Docker Compose입니다. 호스트에 Python이나 Node 패키지를 설치하지 않습니다.

```bash
git clone https://github.com/finddme/ascii-qr-studio.git
cd ascii-qr-studio
./studio.sh
```

브라우저에서 **http://localhost:8787**을 엽니다. 이미지를 선택하고 URL을 입력한 뒤, 필요하면 사진 위에서 사용할 영역을 드래그하세요. 문자 밀도와 배치를 조절하고 생성하면 컬러 QR·흑백 QR·ASCII 중간 결과를 비교하고 ZIP으로 다운로드할 수 있습니다. 작업 기록에서 재실행하거나 입력과 결과를 삭제할 수 있습니다.

UI는 호스트 루프백에만 노출됩니다. 파일과 URL을 외부 서비스에 보내지 않으며 URL 페이지의 내용이나 접속 가능 여부를 검사하지 않습니다. 요청한 주소 자체를 QR에 넣습니다. 이미지 최대 12 MB, 24 MP; 변환은 한 번에 하나씩 실행합니다.

```bash
# 종료
docker compose stop web
# 의존성 또는 코드 변경 후
docker compose build
# 전체 테스트
./test.sh
```

## 명령어

```bash
./qr.sh '/path/to/image.png' --url 'https://example.com/'
./qr.sh '/path/to/image.png' --url 'https://example.com/' \
  --columns 64 --fit cover --min-version 6 --output dev/output/my-design
./convert.sh '/path/to/image.png' --preset bold --renderer tonal
```

출력 경로는 저장소 기준 `dev/output/`입니다. 기존 폴더는 덮어쓰지 않습니다. `--crop LEFT TOP RIGHT BOTTOM`은 0–1 범위의 관심 영역이며 `fit`보다 먼저 적용합니다. 크롭은 수동 지정이고 자동 배경 제거는 아닙니다.

| 옵션 | 의미 |
| --- | --- |
| `--columns 64` | 문자 수. 적으면 굵고 단순하게, 많으면 세밀하게 |
| `--fit contain / cover` | 전체 이미지 유지 / 중앙 정사각형 채우기 |
| `--renderer tonal / classic` | 셀 명암 보존 / 단색 바탕의 기존 표현 |
| `--core-style adaptive / solid` | 필요한 범위만 명암 보정 / 순흑백 QR 점 |
| `--min-version 6` | 최소 QR 버전. 긴 URL이면 필요한 버전으로 증가 |
| `--module-pixels 24` | QR 모듈당 출력 픽셀 수; 실제 인쇄 크기는 아님 |

`tonal`은 실제 ASCII 글자 마스크와 셀별 글자색·바탕색 두 개만으로 렌더링합니다. 원본 사진을 QR 뒤에 깔지 않습니다. TXT는 색과 바탕색을 담지 않으므로 동일한 외관을 재현하려면 PNG 또는 셀 스타일 JSON을 사용하세요.

## 입력·결과 관리

**원격에 올리지 않는 모든 작업 자료는 `dev/`에 둡니다.** 폴더 전체가 `.gitignore`로 제외되고 Docker 빌드에도 들어가지 않습니다.

- `dev/input/`: 직접 관리하는 입력 파일
- `dev/output/`: CLI 결과
- `dev/jobs/<id>/`: UI 입력 PNG, 작업 설정·해시·버전, 결과와 검증 기록
- `dev/archive/`: 로컬 조사·이전 작업 자료
- `dev/qa/`: 브라우저 검사 자료

새 clone에서는 실행 스크립트가 필요한 폴더를 생성합니다. UI ZIP에는 결과·설정·검증 기록과 원본 이미지의 미리보기가 포함됩니다. 별도 입력 파일 `input.png`는 제외되지만 사진 내용과 URL은 포함되므로 공유할 때 내용을 확인하세요. 작업 기록은 자동으로 외부에 동기화하거나 만료시키지 않습니다.

## 결과와 검증

`selected-color.png`와 `selected-mono.png`는 컬러·흑백 14개 해독 검사를 모두 통과한 후보입니다. `preview.html`은 원본 배치·ASCII·QR과 강도별 결과를 비교하며, `validation.json`은 모든 검사의 실제 해독값을 기록합니다. `ascii/`에는 TXT·셀 JSON·PNG가 있습니다.

QR 기능 모듈과 4모듈 여백을 보존합니다. 중심 폭 30/40/50/60/80%를 비교하고, 원본·회색조·두 축소 크기·흐림·회전·JPEG의 7개 조건을 각각 검사합니다. 통과 후보 중 가장 적게 가리는 후보를 선택합니다. 실패하면 최종 선택 이미지를 만들지 않습니다(CLI 종료 코드 3). 입력 오류는 코드 2입니다.

디코더 검사는 시각적 품질을 평가하지 않습니다. 이미지의 형태가 보이는지 직접 검토하고, 실제 카메라와 출력 크기에서도 확인하세요. 이미지와 URL에 따라 적합한 설정이 달라집니다. 길어진 URL은 QR을 조밀하게 만듭니다.

## CI와 버전 배포

- PR / main push: Docker 이미지 빌드, 전체 테스트, 개인 자료 제외 검사.
- `v*` 태그 push: 버전 파일 일치 검사, 같은 Docker 테스트, GHCR 이미지 게시.
- 이미지: `ghcr.io/finddme/ascii-qr-studio:<version>` 및 커밋 SHA. 재현 가능한 사용에는 버전 태그를 사용하세요.
- 초기 저장소와 패키지는 비공개입니다. 다른 계정에서 이미지를 받으려면 해당 패키지에 대한 읽기 권한이 필요합니다.

```bash
# 릴리스: VERSION 수정·테스트·커밋 후
# git tag v0.1.1
# git push origin main v0.1.1
```

프로그램은 Python 코드가 실행하며 스킬은 필수가 아닙니다. 알고리즘과 의존성 설명은 [기술 문서](docs/TECHNOLOGY.md)를 참고하세요.
