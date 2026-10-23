# 포켓몬 이미지 준비와 표시

2026-10-23 사용자 요청으로 종별 그림을 조사·수집했다. 텍스트 RAG의 근거 자료와 화면용 이미지 수집은 별개다.

## 출처와 재현

[PokéAPI Sprites 저장소](https://github.com/PokeAPI/sprites)는 Pokémon 이미지를 별도로 제공한다. 확인한 [README](https://github.com/PokeAPI/sprites/blob/master/README.md)의 official-artwork 경로를 우선 사용하고, 없는 경우 기본 sprite 경로를 확인한다. 웹 이미지 검색 결과의 임의 그림을 무단으로 복제하거나 다른 종의 파일명만 바꾸는 방식을 사용하지 않는다.

수집 리비전: `97a7832d307311c0e1c6ea9035308bf80cc94f81`. 원본 종 메타의 species_id와 기본 개체 pokemon_id를 연결한다. 모든 요청은 고정 리비전 URL이고, 실제 URL·수집 UTC 시각·PNG SHA-256·상태를 로컬 dataset/pokemon/artwork/manifest.json에 보존한다. 4개 작업자가 공유하는 요청 간격은 최소 0.25초이며 429/일시 서버 오류 재시도는 최대 3회다. 404만 원본 부재로 구분하고 일반 네트워크 실패를 부재로 저장하지 않는다.

```powershell
python scripts/collect_pokemon_artwork.py
python scripts/collect_pokemon_artwork.py --items 1 4 7 25 81 133
python scripts/collect_pokemon_artwork.py --offline
```

| 실제 점검 | 결과 |
|---|---:|
| 대상 종 | 1,025 |
| 확보한 이미지 | 1,025 |
| 원본 부재 | 0 |
| 최초 수집 오류 | 0 |
| 최종 오프라인 해시 점검 오류 | 0 |
| 최종 오프라인 신규 항목 | 0 |

첫 오프라인 검증에서 UI가 manifest를 읽는 순간 불필요한 파일 교체를 시도해 Windows PermissionError 2건이 발생했다. 캐시 적중 시 manifest를 쓰지 않도록 수정하고 새 항목 저장의 일시 잠금에 제한 재시도를 추가했다. 이후 오프라인 검증은 1,025건·오류 0으로 완료했다.

## 화면 정책

- 피카츄와 코일은 사용자가 선택한 수채화풍 생성 에셋을 우선 표시한다. 공식 이미지가 아님을 명시한다.
- 다른 종은 수집한 해당 종의 기본 개체 이미지를 표시하고 실제 이미지 출처를 연결한다. 원본 그림체를 수채화라고 부르지 않는다.
- 이미지가 없으면 공통 피카츄 그림의 회색 실루엣과 물음표를 표시한다. 해당 종의 실제 형태가 아닌 공통 자리표시임을 텍스트와 대체 설명에 명시한다. 현재 확보본에서는 원본 부재 0건이므로, 이 상태는 누락 시의 예외 동작이다.
- 화면용 이미지를 답변의 지식 근거로 사용하지 않는다. 생성 그림의 모양·색·배경은 포켓몬 사실 검증 결과가 아니다.
- 모든 다운로드 원본과 manifest는 dataset 아래에서 Git 제외다. 공개본에는 수집 코드·집계·출처 안내 및 앱용 생성 에셋만 포함한다.

## 권리와 아이콘

PokéAPI 공개나 이미지 다운로드 가능성을 원작 캐릭터·그림·상표에 대한 자유 재배포 허가로 간주하지 않는다. 이 서비스는 비공식 학습 프로젝트이며 원본 이미지 파일을 GitLab/GitHub에 재배포하지 않는다.

화면의 몬스터볼 모양 아이콘은 Tabler Icons의 [pokeball.svg](https://github.com/tabler/tabler-icons/blob/main/icons/outline/pokeball.svg)를 사용한다. MIT 라이선스 사본은 streamlit_lab/assets/pokemon/TABLER-LICENSE.txt에 보존한다. 이 아이콘 라이선스는 포켓몬 원작 그림의 라이선스와 별개다.
