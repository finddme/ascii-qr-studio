# 구현과 자료

Pillow 13.0.0 / NumPy 2.5.5 / Segno 1.6.6 / ZXing-cpp 3.1.1을 Docker에 설치합니다.

1. EXIF 방향과 투명도를 처리하고 선택한 영역을 배치합니다.
2. 고정폭 글자의 실제 마스크를 렌더링해 셀의 명암과 형태를 비교합니다.
3. tonal 방식은 셀 평균색을 보존하도록 글자색·바탕색을 계산합니다. JSON만으로 같은 픽셀을 재구성하는 테스트를 제공합니다.
4. QR 기능 모듈은 보존하고 데이터 모듈 중심만 보정합니다. adaptive는 어두운 채널을 80 이하, 밝은 채널을 175 이상으로 제한합니다.
5. 저장한 PNG를 독립 디코더로 다시 읽고 URL과 정확히 비교합니다.

오류정정 H는 임의의 면적을 30% 가려도 된다는 의미가 아닙니다. 실제 파일을 검사하며, 디지털 검사 통과를 시각 품질이나 실제 출력 인식의 보장으로 사용하지 않습니다.

## 공식 자료와 비교 후보

- [Pillow ImageOps](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html): 방향·이미지 배치 처리.
- [Segno](https://segno.readthedocs.io/en/latest/api.html): verbose matrix로 기능 모듈을 구분. 실험적 API를 사용하므로 버전을 고정하고 여러 QR 버전에서 테스트합니다.
- [ZXing-cpp Python](https://github.com/zxing-cpp/zxing-cpp/blob/master/wrappers/python/README.md): 독립 디코딩.
- [DENSO 오류정정](https://www.qrcode.com/en/about/error_correction.html), [여백](https://www.qrcode.com/en/howto/code.html/index.html).
- [ASCII Magic](https://github.com/LeandroBarone/python-ascii_magic): 범용 Python 변환 후보.
- [ascii-image-converter](https://github.com/TheZoraiz/ascii-image-converter): Go CLI 후보.
- [dwooods/asciify](https://github.com/dwooods/asciify): 문자 형태 비교 방식 참고.
- [Asciify Engine](https://github.com/ayangabryl/asciify-engine): 실시간 GPU 렌더링 후보. 본 프로젝트 의존성은 아닙니다.

생성형 이미지 API와 외부 플러그인을 사용하지 않습니다. 원격 서비스 없이 변환과 디코딩이 가능합니다. 의존성의 라이선스는 각 공식 프로젝트를 따릅니다: Pillow HPND, NumPy BSD, Segno BSD, ZXing-cpp Apache-2.0, DejaVu 폰트 자체 라이선스. 설치된 패키지 및 Debian 폰트 패키지에 원문이 포함됩니다.
