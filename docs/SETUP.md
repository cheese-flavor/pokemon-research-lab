# 설치·데이터 준비

- 명령 실행 위치: 저장소 루트
- 기준: Python 3.11 이상, SSAFY GMS 사용 권한

## 빠른 시작

Python 3.11 이상과 GMS 사용 권한이 필요합니다. Windows PowerShell 기준이며 프로젝트 루트에서 실행합니다.

```powershell
git clone https://github.com/cheese-flavor/pokemon-research-lab.git
cd pokemon-research-lab
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-pokemon-rag.txt
```

빈 `.env.example`을 참고해 **로컬 `streamlit_lab/.env`** 파일을 만들고 `GMS_KEY`를 직접 설정합니다. 기존 키 파일이 있다면 덮어쓰지 않습니다. 키를 Git에 올리지 않습니다.

```dotenv
GMS_KEY=
```

데이터는 공개 저장소에 포함하지 않으며 아래 순서로 준비합니다. 번역·임베딩·답변 생성은 GMS 호출이 발생할 수 있습니다.

```powershell
.venv/Scripts/python.exe scripts/collect_pokemon_bulk.py
.venv/Scripts/python.exe scripts/translate_pokemon_descriptions.py
.venv/Scripts/python.exe scripts/index_pokemon_metadata.py
.venv/Scripts/python.exe scripts/collect_pokemon_artwork.py
.venv/Scripts/python.exe -m streamlit run streamlit_lab/app.py
```

이미 준비된 데이터·보완본·색인은 재생성할 필요가 없습니다. 첫 질문의 설명 자료는 질문에 맞춰 증분 준비됩니다. 실행 후 [로컬 페이지](http://127.0.0.1:8501)를 열고, 종료할 때는 실행 터미널에서 Ctrl+C를 누릅니다.

한국어 번역의 검수·용어 보정 재현 절차는 [TRANSLATION.md](../docs/rag/pokemon/TRANSLATION.md)와 [KOREAN_TERMS.md](../docs/rag/pokemon/KOREAN_TERMS.md)를 확인하세요. 새 설치에서 번역 한 번만 실행한 결과를 기존 검수 완료본과 동일하다고 가정하지 않습니다.
