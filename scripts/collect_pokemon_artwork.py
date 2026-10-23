"""Cache species-matched PokéAPI artwork locally; never add images to Git."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pokemon.embeddings import write_json

PNG = b'\x89PNG\r\n\x1a\n'
HEADERS = {'User-Agent': 'PokemonResearchLab/1.0 (educational image cache)'}
_gate = threading.Lock()
_next = 0.0


def fetch(url):
    global _next
    for attempt in range(3):
        with _gate:
            wait = max(0, _next - time.monotonic())
            _next = time.monotonic() + wait + .25
        if wait:
            time.sleep(wait)
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=30) as response:
                return response.read(5_000_001)
        except HTTPError as error:
            if error.code == 404:
                return None
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            value = error.headers.get('Retry-After', '')
            time.sleep(min(float(value), 60) if value.isdigit() else 2 ** (attempt + 1))
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--items', nargs='*', type=int)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    directory = ROOT / 'dataset/pokemon/artwork'
    path = directory / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'images': {}}
    if 'revision' not in manifest:
        if args.offline:
            raise FileNotFoundError('Artwork manifest missing')
        response = fetch('https://api.github.com/repos/PokeAPI/sprites/commits/master')
        manifest['revision'] = json.loads(response)['sha']
    revision = manifest['revision']
    if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
        raise ValueError('Invalid source revision')
    items = json.loads((ROOT / 'dataset/pokemon/items.json').read_text(encoding='utf-8'))
    if args.items:
        wanted = set(args.items)
        items = [i for i in items if i['species_id'] in wanted]
        if len(items) != len(wanted):
            raise ValueError('Unknown species requested')

    def collect(item):
        identity = str(item['species_id'])
        previous = manifest['images'].get(identity)
        target = directory / revision / (identity + '.png')
        if previous and previous.get('status') == 'available' and target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != previous['sha256']:
                raise ValueError('Artwork cache integrity mismatch')
            return identity, previous, False
        if previous and previous.get('status') == 'not_found':
            return identity, previous, False
        if args.offline:
            raise FileNotFoundError('Artwork missing offline')
        for folder in ('other/official-artwork/', ''):
            url = f'https://raw.githubusercontent.com/PokeAPI/sprites/{revision}/sprites/pokemon/{folder}{item["pokemon_id"]}.png'
            raw = fetch(url)
            if raw is None:
                continue
            if not raw.startswith(PNG) or len(raw) > 5_000_000:
                raise ValueError('Invalid artwork image')
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix('.png.tmp')
            temporary.write_bytes(raw)
            temporary.replace(target)
            return identity, {'status': 'available', 'species_id': item['species_id'],
                              'pokemon_id': item['pokemon_id'], 'source_url': url,
                              'path': str(target.relative_to(ROOT)).replace('\\', '/'),
                              'sha256': hashlib.sha256(raw).hexdigest(),
                              'fetched_at': datetime.now(timezone.utc).isoformat(),
                              'kind': 'official-artwork' if folder else 'sprite'}, True
        return identity, {'status': 'not_found', 'species_id': item['species_id'],
                          'pokemon_id': item['pokemon_id']}, True

    errors = 0
    fetched = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [(item, pool.submit(collect, item)) for item in items]
        for index, (item, future) in enumerate(futures, 1):
            try:
                identity, entry, fresh = future.result()
                fetched += fresh
                if fresh:
                    manifest['images'][identity] = entry
                    # Windows can briefly lock an open manifest while the UI reads it.
                    for attempt in range(3):
                        try:
                            write_json(path, manifest)
                            break
                        except PermissionError:
                            if attempt == 2:
                                raise
                            time.sleep(.05 * (attempt + 1))
            except Exception as error:
                errors += 1
                print(f'Artwork #{item["species_id"]}: {type(error).__name__}', flush=True)
            if index % 100 == 0:
                print(f'Checked {index}/{len(items)}', flush=True)
    summary = {'checked': len(items), 'available': sum(e['status'] == 'available' for e in manifest['images'].values()),
               'not_found': sum(e['status'] == 'not_found' for e in manifest['images'].values()),
               'new_entries': fetched, 'errors': errors, 'revision': revision, 'offline': args.offline}
    write_json(ROOT / 'outputs/pokemon/design/artwork-summary.json', summary)
    print(json.dumps(summary))
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Artwork collection failed ({type(error).__name__}).', file=sys.stderr)
        sys.exit(1)
