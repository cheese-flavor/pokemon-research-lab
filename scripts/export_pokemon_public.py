"""Export an allowlisted Pokemon-only tree, without Git history or local data."""
import argparse
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXED = ['README.md', '.gitignore', '.env.example', '.streamlit/config.toml', 'design-qa.md',
         'requirements-pokemon.txt', 'requirements-pokemon-rag.txt', 'requirements-pokemon-eda.txt',
         'config/pokemon_rag.toml', 'src/__init__.py', 'scripts/__init__.py', 'streamlit_lab/app.py',
         'streamlit_lab/assets/pokemon.css', 'streamlit_lab/assets/pokemon/pokeball.svg',
         'streamlit_lab/assets/pokemon/TABLER-LICENSE.txt']
PATTERNS = ['src/pokemon/*.py', 'scripts/*pokemon*.py', 'tests/test_pokemon*.py',
            'docs/rag/pokemon/**/*.md', 'docs/rag/pokemon/assets/*', 'docs/rag/pokemon/eda_figures/*.png',
            'streamlit_lab/assets/pokemon/pikachu-watercolor.png',
            'streamlit_lab/assets/pokemon/magnemite-watercolor.png']
ALLOWED = {'.py', '.md', '.toml', '.txt', '.css', '.png', '.svg', '.example'}


def public_files(root):
    root = Path(root)
    files = {root/name for name in FIXED if (root/name).is_file()}
    for pattern in PATTERNS:
        files.update(p for p in root.glob(pattern) if p.is_file())
    # Aggregate EDA charts are documentation, not downloaded records.
    files.update(p for p in root.glob('docs/rag/pokemon/*.png') if p.is_file())
    for path in sorted(files):
        relative = path.relative_to(root)
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('External path in export')
        if path.name != '.gitignore' and path.suffix.lower() not in ALLOWED:
            raise ValueError('Disallowed export extension: '+str(relative))
        if any(part in {'data','dataset','outputs','.git','.venv','private','ml'} for part in relative.parts):
            raise ValueError('Private or unrelated path in export')
        if path.suffix.lower() not in {'.png'}:
            text = path.read_text(encoding='utf-8')
            if re.search(r'\bsk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9_-]{30,}', text):
                raise ValueError('Possible credential in '+str(relative))
        yield path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',required=True)
    args=parser.parse_args()
    target=Path(args.destination).resolve()
    # A new directory only; never overwrite or delete an existing repository.
    if target.exists():
        raise FileExistsError('Destination must be new')
    files=list(public_files(ROOT))
    from dotenv import dotenv_values
    key=dotenv_values(ROOT/'streamlit_lab/.env').get('GMS_KEY')
    if key:
        for path in files:
            if path.suffix.lower() != '.png' and key in path.read_text(encoding='utf-8'):
                raise ValueError('Private key detected in export candidate')
    for path in files:
        output=target/path.relative_to(ROOT)
        output.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,output)
    print(f'Exported {len(files)} allowlisted files; no original Git history, datasets, PDFs or workbooks.')


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print(f'Public export failed ({type(error).__name__}).',file=sys.stderr)
        sys.exit(1)
