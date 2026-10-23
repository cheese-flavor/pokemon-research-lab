"""Escaped presentation helpers; never generate facts or substitute species art."""
import base64
import json
from functools import lru_cache
from html import escape
from pathlib import Path
from io import BytesIO

ART = {25: 'pikachu-watercolor.png', 81: 'magnemite-watercolor.png'}
TYPE_COLORS = {
    '노말': '#e7e7df', '불꽃': '#ffd7bd', '물': '#d4e8ff', '전기': '#ffe16a',
    '풀': '#d9edbd', '얼음': '#d4f0ed', '격투': '#f5ccc4', '독': '#e8d5ed',
    '땅': '#eedebf', '비행': '#dfdff8', '에스퍼': '#ffd2e0', '벌레': '#e0e8bb',
    '바위': '#e6dec4', '고스트': '#ded7ed', '드래곤': '#dcd3fc', '악': '#ddd6d1',
    '강철': '#dfe5ed', '페어리': '#f8d9ed',
}


@lru_cache(maxsize=16)
def image_uri(path, modified):
    return 'data:image/png;base64,' + base64.b64encode(Path(path).read_bytes()).decode('ascii')


@lru_cache(maxsize=4)
def artwork_manifest(path, modified):
    return json.loads(Path(path).read_text(encoding='utf-8'))


@lru_cache(maxsize=1100)
def thumbnail(path, modified, missing=False):
    from PIL import Image, ImageEnhance, ImageDraw
    with Image.open(path) as original:
        image=original.convert('RGBA')
        image.thumbnail((44,44))
        if missing:
            image=ImageEnhance.Color(image).enhance(0)
            image=ImageEnhance.Brightness(image).enhance(.4)
            ImageDraw.Draw(image).text((16,12),'?',fill='white')
        buffer=BytesIO()
        image.save(buffer,format='PNG',optimize=True)
    return 'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii')


def catalogue_rows(root, items):
    root=Path(root)
    manifest=root/'dataset/pokemon/artwork/manifest.json'
    entries=artwork_manifest(str(manifest),manifest.stat().st_mtime_ns).get('images',{}) if manifest.exists() else {}
    result=[]
    for item in items:
        entry=entries.get(str(item['species_id']),{})
        path=(root/entry.get('path','dataset/pokemon/artwork/absent.png')).resolve()
        valid=(entry.get('status')=='available' and path.is_relative_to((root/'dataset/pokemon/artwork').resolve()) and path.is_file())
        if not valid:
            path=root/'streamlit_lab/assets/pokemon/pikachu-watercolor.png'
        result.append({'아이콘':thumbnail(str(path),path.stat().st_mtime_ns,not valid),
                       '포켓몬':f"#{item['species_id']:04d} {item['name_ko']}"})
    return result


def brand(root):
    path = Path(root) / 'streamlit_lab/assets/pokemon/pokeball.svg'
    uri = 'data:image/svg+xml;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
    return f'<div class="pk-brand"><img src="{uri}" alt=""><div><strong>Pokémon Research Lab</strong><p>포켓몬 정보 검색 · 도감 · 진화 조건</p></div></div>'


def artwork(root, species_id):
    root = Path(root)
    directory = Path(root) / 'streamlit_lab/assets/pokemon'
    path = directory / ART.get(species_id, 'missing.png')
    if species_id in ART and path.exists():
        return image_uri(str(path), path.stat().st_mtime_ns), 'generated', ''
    manifest = root / 'dataset/pokemon/artwork/manifest.json'
    if manifest.exists():
        entry = artwork_manifest(str(manifest),manifest.stat().st_mtime_ns).get('images', {}).get(str(species_id), {})
        candidate = (root / entry.get('path', 'dataset/pokemon/artwork/absent.png')).resolve()
        if (entry.get('status') == 'available'
                and str(entry.get('source_url','')).startswith('https://raw.githubusercontent.com/PokeAPI/sprites/')
                and candidate.is_relative_to((root / 'dataset/pokemon/artwork').resolve()) and candidate.is_file()):
            return image_uri(str(candidate), candidate.stat().st_mtime_ns), 'source', entry['source_url']
    path = directory / 'pikachu-watercolor.png'
    return (image_uri(str(path), path.stat().st_mtime_ns) if path.exists() else ''), 'missing', ''


def art_markup(root, species_id, name, hero=False):
    uri, kind, url = artwork(root, species_id)
    missing = kind == 'missing'
    alt = '이미지 준비 중: 공통 실루엣' if missing else name + ' 일러스트'
    cls = 'pk-hero-art' if hero else ''
    image = f'<img class="{cls}" src="{uri}" alt="{escape(alt)}">' if uri else ''
    marker = '<span class="pk-missing-mark" aria-hidden="true">?</span>' if missing else ''
    notes = {'generated': '수채화 생성 일러스트 · 공식 이미지가 아닙니다.',
             'source': 'PokéAPI 원본 이미지 · 수채화 생성 그림과 구분됩니다.',
             'missing': '이미지 준비 중 · 공통 실루엣이며 해당 종의 실제 모습이 아닙니다.'}
    link = f' <a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">이미지 출처</a>' if url else ''
    return f'<div class="pk-image {"pk-missing" if missing else ""}">{image}{marker}</div><p class="pk-art-note">{notes[kind]}{link}</p>'


def badges(types):
    return ''.join(f'<span class="pk-type" style="background:{TYPE_COLORS.get(t, "#e7e7df")}">{escape(t)}</span>'
                   for t in types)


def profile(root, item, compact=False):
    image = art_markup(root, item['species_id'], item['name_ko'], hero=True)
    total = sum(item['stats'].values())
    return f'''<section class="pk-profile{' pk-profile-compact' if compact else ''}">
<div class="pk-profile-copy"><p class="pk-eyebrow">POKÉMON RESEARCH LAB · NATIONAL POKÉDEX</p>
<h1>#{item['species_id']:04d} {escape(item['name_ko'])}</h1>
<p class="pk-english">{escape(item['name'])}</p><div class="pk-types">{badges(item['types'])}</div>
<p class="pk-genus">{escape(item.get('genus_ko') or '포켓몬')} · 기본 형태 정보</p>
<dl class="pk-measures"><div><dt>키</dt><dd>{item['height_m']:g}<small> m</small></dd></div>
<div><dt>몸무게</dt><dd>{item['weight_kg']:g}<small> kg</small></dd></div>
<div><dt>종족값 합계</dt><dd>{total}</dd></div></dl></div>
<div class="pk-art-wrap">{image}</div></section>'''


def result_card(root, item):
    image = art_markup(root, item['species_id'], item['name_ko'])
    return f'''<div class="pk-result"><div class="pk-result-art">{image}</div>
<p class="pk-eyebrow">NO. {item['species_id']:04d}</p><h3>{escape(item['name_ko'])}</h3>
<p class="pk-english">{escape(item['name'])}</p><div class="pk-types">{badges(item['types'])}</div>
<p class="pk-result-values">키 {item['height_m']:g}m <span>몸무게 {item['weight_kg']:g}kg</span></p></div>'''
