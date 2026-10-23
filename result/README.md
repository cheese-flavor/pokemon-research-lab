# 기능별 실행 화면

2026-10-23 KST, 실제 로컬 Streamlit 화면. 키·데이터 파일은 포함하지 않는다. 전체 캡처는 현재 PC에서 실행한 상태이며 인터넷 배포 화면이 아니다.

| 파일 | 확인 내용 |
|---|---|
| 01_catalogue.png | 영어 브랜드와 아이콘 전체 도감 |
| 02_global_chat_sources.png | 피카츄 도감에서 파이리 질문·문서 출처 |
| 03_condition_search.png | 1세대 전기 타입·10kg 이하, 25/81번 일치 |
| 04_evolution_conditions.png | 진화 카드·조건 행·범위·원문 링크 |
| 05_empty_search.png | 객관 조건 결과 0종 안내 |
| 06_unsupported_question.png | 미수집 기술 습득 질문·인용 없음 안내 |
| 07_response_status.png | 실제 답변 생성 중 진행 상태 |
| 08_multi_species_chat.png | 두 종별 답변과 전체 인용 번호 분리 |
| 09_missing_key.png | 별도 결함 주입 화면의 키 누락 안내 |
| 10_missing_index.png | 별도 결함 주입 화면의 색인 누락 안내 |
| 11_safe_error.png | 오류 상세를 숨긴 복구 안내와 확인 번호 |
| 12_metadata_source.png | 메타데이터 출처 구분 |
| 13_catalogue_selection.png | 목록에서 파이리 선택 후 이전 전체 대화 유지 |

09~11은 실제 설정·키·색인 파일을 지우지 않고 테스트 프로세스에서 결함을 주입한 화면이다. 08 캡처 뒤에는 종별 답변에서 불필요한 비교 불가 안내를 줄이도록 프롬프트 문구를 다듬었다. 해당 문구 변경의 브라우저 재촬영은 재개 후 가능하다.

[검증 집계](VALIDATION.md), [전체 작업 인계](../docs/rag/pokemon/HANDOFF.md). 원본 및 점검용 엑셀은 Git에서 제외한다.
