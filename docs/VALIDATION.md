# 검증과 공개 범위

- 기존 검증 기록 재정리; 이번 문서 개편에서 외부 API 호출·전체 모델 평가 재실행 없음

## 검증과 알려진 한계

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_pokemon*.py" -q
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe scripts/collect_pokemon_artwork.py --offline
```

- 관련 테스트 **63개 통과**. 일부 화면 검사는 로컬 데이터·색인이 있어야 실행됩니다.
- 1,025종 메타, 원본 64,017문서, 한국어 보완본 64,264문서입니다. 127종의 247개 생성 번역은 공식 한국어 문구 또는 독립된 사람의 전수 검수 결과가 아닙니다.
- 이미지 1,025종을 확보하고 로컬 캐시를 검증했습니다. 이미지 수집은 텍스트 RAG 근거 수집과 별개입니다.
- 두 새 질문에서 최초 처리 약 44초, 캐시 반복 약 1.7초를 측정했습니다. 전체 서비스의 평균·p95·운영 성능 보장은 아닙니다.
- 고정 PokéAPI 자료를 검색하며 실시간 웹 전체를 검색하지 않습니다. 모든 게임·리전폼·진화 예외·기술 습득표·출현 위치·대전 순위를 포괄하지 않습니다.
- 대화 기록은 현재 브라우저 세션용입니다. 인용 번호 검증은 사실 정확성을 자동 보장하지 않습니다.
- 전체 종의 답변 정확도 평가와 실제 사람의 상호 점검은 완료되지 않았습니다. [후속 검증](../docs/rag/pokemon/FINAL_REVIEW.md)을 참고하세요.


## 공개 범위와 출처

공개본은 포켓몬 프로젝트 파일만 추려 만든 별도 Git 이력입니다. 기존 ML 프로젝트와 비공개 파일의 이력은 가져오지 않습니다.

**PDF 요구사항 문서·체크리스트 Excel·실제 데이터·원본 이미지 캐시·API 캐시·임베딩·벡터 DB·키는 포함하지 않습니다.** `.gitignore`와 공개 파일 허용 목록을 함께 검사합니다.

- 텍스트/수치: [PokéAPI 데이터](https://github.com/PokeAPI/pokeapi/tree/2bf639e5572812a67d2b94903fdcb9d095f5aeb2/data/v2/csv)
- 원본 이미지: [PokéAPI Sprites](https://github.com/PokeAPI/sprites), 실제 다운로드 리비전과 해시는 로컬 manifest에 보존
- 화면 아이콘: [Tabler Icons](https://github.com/tabler/tabler-icons), MIT 라이선스 사본 포함
- 수채화 일러스트: 이 프로젝트의 화면용 생성 이미지. 공식 포켓몬 이미지가 아님

본 프로젝트는 비공식 학습 프로젝트입니다. 저장소 코드의 공개와 포켓몬 문구·캐릭터·이미지·상표의 권리는 별개이며, 수집 자료를 자유 이용·재배포 가능한 데이터로 간주하지 않습니다. 상세 내용은 [데이터 이용 범위](../docs/rag/pokemon/DATA.md)를 참고하세요.
