"""Task 4 CLI: resolve an exact item and prepare source documents for a question."""
import argparse
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pokemon.ingestion import prepare_documents


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--item', required=True, help='Exact Korean/English name or national species number')
    parser.add_argument('--question', required=True)
    parser.add_argument('--config', type=Path, default=ROOT/'config/pokemon_rag.toml')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    try:
        config = tomllib.loads(args.config.read_text(encoding='utf-8'))
        print(json.dumps(prepare_documents(ROOT, config, args.item, args.question, args.offline),
                         ensure_ascii=False, indent=2))
    except Exception as error:
        print(f'Document ingestion failed ({type(error).__name__}); check key, source cache, config and input.', file=sys.stderr)
        sys.exit(1)
