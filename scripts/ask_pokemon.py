"""Task 5 CLI: answer a selected Pokemon question with cited evidence."""
import argparse
from pathlib import Path
import sys
import tomllib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.pokemon.rag import answer_question


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--item',required=True)
    parser.add_argument('--question',required=True)
    parser.add_argument('--version',action='append',dest='versions')
    parser.add_argument('--kind',action='append',dest='kinds',choices=['species_description','ability_description','evolution_chain'])
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--skip-prepare',action='store_true',help='Use already indexed source documents only')
    args=parser.parse_args()
    try:
        cfg=tomllib.loads((ROOT/'config/pokemon_rag.toml').read_text(encoding='utf-8'))
        result=answer_question(ROOT,cfg,args.item,args.question,args.versions,args.kinds,args.offline,not args.skip_prepare)
        print(result['answer'])
        print(result['citation_notice'])
        for source in result['sources']:
            print(f"[근거 {source['number']}] {source['title']} / {source['evidence_type']} / {source['versions']} / {source['source_url']}")
            for url in source.get('source_urls',[]):
                if url!=source['source_url']:
                    print('  관련 원본: '+url)
    except Exception as error:
        print(f'Pokemon RAG failed ({type(error).__name__}); check source/index/configuration and key.',file=sys.stderr)
        sys.exit(1)
