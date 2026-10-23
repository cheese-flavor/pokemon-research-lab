# 공개 GitHub 배포 범위

사용자 지정 계정: cheese-flavor. 신규 공개 저장소 이름: pokemon-research-lab. 기존 GitLab 저장소와 별도 Git 이력으로 공개한다. GitHub 소스 공개는 인터넷 서비스 배포와 다르며 실행 URL은 현재 로컬 127.0.0.1:8501이다.

## 포함·제외

공개본은 scripts/export_pokemon_public.py의 허용 목록으로 만든다. 포켓몬 코드·관련 테스트·설정·빈 키 템플릿·설계/검증 문서·집계 EDA 그림·실제 UI 미리보기·화면용 생성 에셋·아이콘 라이선스를 포함한다.

PDF·XLS/XLSX/XLSM·실제 데이터·다운로드 이미지·모델 캐시·임베딩·벡터 DB·키·이전 ML 파일·원본 Git 이력은 포함하지 않는다. .gitignore는 이미 추적된 파일을 지우지 않으므로 공개용 파일 목록과 커밋 객체도 별도 검사한다. 기존 저장소의 과거 파일을 삭제하거나 강제 푸시하지 않는다.

```powershell
python scripts/export_pokemon_public.py --destination outputs/pokemon/public-release
```

대상 폴더는 새 폴더여야 하며 기존 폴더를 덮어쓰거나 삭제하지 않는다. 원본 작업 폴더에는 이번 작업의 명시한 파일만 커밋하고, 공개용 폴더는 새 Git 저장소에서 최초 커밋을 만든다. 사용자 요청에 따라 GitLab 푸시는 중단하고 GitHub만 갱신한다. 이후 공개 갱신도 과거 ML 이력을 합치는 방식이 아니라 같은 공개 파일 집합의 변경을 검토해 반영한다.

GitLab의 이전 주소는 서버가 안내한 현재 주소로 갱신했다. 변경 전에 두 주소의 대상인 main 커밋 a36ff68의 일치를 실제 확인했다. 2026-10-23 공개 업로드 완료: https://github.com/cheese-flavor/pokemon-research-lab . 공개 상태와 main 푸시를 확인했다. 최초 공개 커밋은 5eb9a2b이며 82개 허용 파일과 새 이력만 포함한다.

공개 준비 확인: 허용 목록 82파일을 내보내 같은 실행 환경에서 테스트 63개를 실행했다. 로컬 데이터가 없어서 UI 7개는 건너뛰었고 나머지 56개는 통과했다. 새 Python 환경의 의존성 설치 검증과는 구분한다.

후속 지시(2026-10-23): GitLab 최신화를 재허용했다. 위 중단 기록은 당시 상태이며, 현재는 GitLab 원본 이력과 GitHub 공개 허용 목록 이력을 각각 유지한다.
