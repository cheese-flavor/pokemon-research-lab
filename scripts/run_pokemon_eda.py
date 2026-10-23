"""Descriptive statistics only; no API, model calls, embeddings or data mutation."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, ticker
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'dataset/pokemon'
OUTPUT = ROOT / 'outputs/pokemon/eda'
REPORT = ROOT / 'docs/rag/pokemon/EDA.md'
FIGURES = REPORT.parent / 'eda_figures'
STATS = ['hp', 'attack', 'defense', 'special-attack', 'special-defense', 'speed']
LABELS = {'hp': 'HP', 'attack': '공격', 'defense': '방어', 'special-attack': '특수공격',
          'special-defense': '특수방어', 'speed': '스피드', 'height_m': '키 (m)',
          'weight_kg': '몸무게 (kg)', 'bst': '종족값 합계'}
KINDS = {'species_description': '도감 설명', 'ability_description': '특성 설명', 'evolution_chain': '진화 체인'}
GENERATIONS = ['generation-i', 'generation-ii', 'generation-iii', 'generation-iv', 'generation-v',
               'generation-vi', 'generation-vii', 'generation-viii', 'generation-ix']


def read(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_stats(frame):
    result = pd.DataFrame({'건수': frame.count(), '평균': frame.mean(), '표준편차': frame.std(ddof=0),
                           '최솟값': frame.min(), 'Q1': frame.quantile(.25), '중앙값': frame.median(),
                           'Q3': frame.quantile(.75), '최댓값': frame.max()})
    q1, q3 = frame.quantile(.25), frame.quantile(.75)
    result['IQR 밖 건수'] = ((frame < q1 - 1.5 * (q3 - q1)) | (frame > q3 + 1.5 * (q3 - q1))).sum()
    return result


def markdown(frame, index=True):
    table = frame.copy()
    if index:
        table = table.reset_index()
    def cell(value):
        if pd.isna(value):
            return '—'
        if isinstance(value, (float, np.floating)):
            return f'{value:,.2f}'
        if isinstance(value, (int, np.integer)):
            return f'{value:,}'
        return str(value).replace('|', '/')
    lines = ['| ' + ' | '.join(map(str, table.columns)) + ' |', '| ' + ' | '.join(['---'] * len(table.columns)) + ' |']
    lines += ['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in table.itertuples(index=False, name=None)]
    return '\n'.join(lines)


def save_table(name, table):
    table.to_csv(OUTPUT / (name + '.csv'), encoding='utf-8-sig')


def figure(name, fig):
    fig.savefig(FIGURES / name, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    paths = [DATA / n for n in ('items.json', 'documents.json', 'documents_ko_enriched.json')]
    before = {p.name: digest(p) for p in paths}
    items, original, docs = read('items.json'), read('documents.json'), read('documents_ko_enriched.json')
    if docs[:len(original)] != original:
        raise ValueError('Original corpus is not preserved')
    metadata = pd.DataFrame([{**{k: i[k] for k in ('item_id', 'species_id', 'generation', 'height_m', 'weight_kg', 'is_legendary', 'is_mythical')},
                              **i['stats'], 'type_count': len(i['types']), 'ability_count': len(i['abilities']),
                              'missing_ability_names': sum(not a['name_ko'] for a in i['abilities'])} for i in items])
    metadata['bst'] = metadata[STATS].sum(axis=1)
    metadata['분류'] = np.select([metadata.is_legendary & metadata.is_mythical, metadata.is_legendary, metadata.is_mythical],
                                ['전설·환상 중복', '전설', '환상'], default='일반')
    documents = pd.DataFrame([{'doc_id': d['doc_id'], 'item_id': d['item_id'], 'kind': d['kind'],
                               'language': d['language'], 'version': d.get('version', ''),
                               'generated': d.get('is_machine_translation', False), 'length': len(d['content']),
                               'source_url': d['source_url'], 'content_hash': hashlib.sha256(d['content'].encode()).hexdigest()}
                              for d in docs])
    generation = metadata.groupby('generation').agg(종수=('item_id', 'size'), 전설=('is_legendary', 'sum'), 환상=('is_mythical', 'sum'),
                                                    종족값평균=('bst', 'mean'), 종족값중앙값=('bst', 'median')).reindex(GENERATIONS)
    generation.insert(1, '전체대비비율(%)', generation['종수'] / len(items) * 100)
    generation.index = [f'{i}세대' for i in range(1, 10)]
    generation.index.name = '세대'
    type_rows = pd.DataFrame([{'타입': t, 'item_id': i['item_id']} for i in items for t in i['types']])
    type_counts = type_rows.groupby('타입').size().sort_values(ascending=False).to_frame('보유 종수')
    type_counts['전체 종 대비(%)'] = type_counts['보유 종수'] / len(items) * 100
    numeric = frame_stats(metadata[STATS + ['bst', 'height_m', 'weight_kg']]).rename(index=LABELS)
    numeric.index.name = '항목'
    group_bst = metadata.groupby('분류')['bst'].agg(종수='size', 평균='mean', 중앙값='median', 최솟값='min', 최댓값='max')
    pearson = metadata[STATS].corr(method='pearson').rename(index=LABELS, columns=LABELS)
    spearman = metadata[STATS].corr(method='spearman').rename(index=LABELS, columns=LABELS)
    pearson.index.name = spearman.index.name = '능력치'
    missing = pd.Series({field: sum(i.get(field) in (None, '', []) for i in items)
                         for field in ('item_id', 'name', 'name_ko', 'genus_ko', 'generation', 'types', 'abilities', 'index_text')}, name='결측 항목 수').to_frame()
    missing.index.name = '필드'
    doc_lengths = frame_stats(documents.pivot(columns='kind', values='length')).rename(index=KINDS)
    doc_lengths.index.name = '문서 종류'
    doc_counts = pd.crosstab(documents.kind, documents.language).rename(index=KINDS)
    doc_counts.index.name = '문서 종류'
    doc_per_item = documents.groupby('item_id').size().rename('문서 수')
    per_item_stats = frame_stats(doc_per_item.to_frame())
    per_item_stats.index.name = '항목'
    duplicates = []
    for kind, frame in documents.groupby('kind'):
        unique_content = frame.drop_duplicates(['language', 'content_hash']).shape[0]
        within_item = frame.duplicated(['item_id', 'language', 'content_hash']).sum()
        duplicates.append({'문서 종류': KINDS[kind], '레코드 수': len(frame), '언어별 고유 본문 수': unique_content,
                           '반복 레코드 수': len(frame) - unique_content,
                           '반복 비율(%)': (len(frame) - unique_content) / len(frame) * 100,
                           '동일 종 내부 반복 수': int(within_item)})
    duplicate_table = pd.DataFrame(duplicates).set_index('문서 종류')
    coverage_rows = []
    original_ko = set(documents.loc[(documents.kind == 'species_description') & (documents.language == 'ko') & ~documents.generated, 'item_id'])
    translated_ko = set(documents.loc[(documents.kind == 'species_description') & documents.generated, 'item_id'])
    for generation_id, group in metadata.groupby('generation', sort=False):
        ids = set(group.item_id)
        coverage_rows.append({'세대': f'{GENERATIONS.index(generation_id)+1}세대', '종수': len(ids),
                              '원본 한국어 종수': len(ids & original_ko), '생성 번역 보완 종수': len(ids & translated_ko),
                              '최종 결측 종수': len(ids - original_ko - translated_ko)})
    coverage = pd.DataFrame(coverage_rows).set_index('세대')
    if not (generation['종수'].sum() == len(items) == group_bst['종수'].sum()
            and metadata.type_count.isin([1, 2]).all()
            and len(type_rows) == metadata.type_count.sum()
            and doc_counts.to_numpy().sum() == len(docs)
            and (duplicate_table['언어별 고유 본문 수'] + duplicate_table['반복 레코드 수']).sum() == len(docs)
            and coverage['종수'].sum() == len(items)):
        raise ValueError('Aggregate reconciliation failed')
    summaries = {'generation': generation, 'types': type_counts, 'numeric': numeric, 'group_bst': group_bst,
                 'correlation_pearson': pearson, 'correlation_spearman': spearman, 'missing': missing,
                 'document_lengths': doc_lengths, 'document_languages': doc_counts,
                 'documents_per_species': per_item_stats, 'document_repetition': duplicate_table, 'korean_coverage': coverage}
    for name, table in summaries.items():
        save_table(name, table)

    fonts = {f.name for f in font_manager.fontManager.ttflist}
    selected_font = next((f for f in ('Malgun Gothic', 'AppleGothic', 'NanumGothic', 'Noto Sans CJK KR') if f in fonts), None)
    if selected_font:
        plt.rcParams['font.family'] = selected_font
    plt.rcParams.update({'axes.unicode_minus': False, 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    blue, orange = '#276DAD', '#CB6C25'
    fig, axes = plt.subplots(1, 2, figsize=(14, 8), layout='constrained')
    for axis, table, column, title in [(axes[0], generation, '종수', '세대별 종 수'), (axes[1], type_counts, '보유 종수', '타입 보유 종 수 (복합 타입 각각 집계)')]:
        values = table[column]
        axis.barh(table.index, values, color=blue)
        axis.invert_yaxis()
        for index, value in enumerate(values):
            axis.text(value + 1, index, f'{value} ({value/len(items):.1%})', va='center', fontsize=9)
        axis.set_xlim(0, values.max() * 1.3)
        axis.set_title(title)
        axis.set_xlabel('종 수 (종)')
    fig.suptitle('포켓몬 1,025종: 세대·타입 분포', fontsize=15)
    figure('01_population.png', fig)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), layout='constrained')
    for axis, field in [(axes[0, 0], 'height_m'), (axes[1, 0], 'bst')]:
        axis.hist(metadata[field], bins='fd', color=blue, edgecolor='white')
        axis.axvline(metadata[field].median(), color=orange, label=f'중앙값 {metadata[field].median():g}')
        axis.set(title=LABELS[field] + ' 분포', xlabel=LABELS[field], ylabel='종 수 (종)')
        axis.legend(frameon=False)
    positive_weights = metadata.loc[metadata.weight_kg > 0, 'weight_kg']
    axes[0, 1].hist(positive_weights, bins=np.geomspace(positive_weights.min(), positive_weights.max(), 25), color=blue, edgecolor='white')
    axes[0, 1].set_xscale('log')
    axes[0, 1].xaxis.set_major_formatter(ticker.FuncFormatter(lambda value, _: f'{value:g}'))
    axes[0, 1].set(title='몸무게 분포 (가로축 로그 척도)', xlabel='몸무게 (kg, 로그 척도)', ylabel='종 수 (종)')
    axes[1, 1].boxplot([metadata[s] for s in STATS], tick_labels=[LABELS[s] for s in STATS], showfliers=False)
    axes[1, 1].set(title='능력치별 사분위 분포 (이상치 점 생략)', ylabel='종족값 (포인트)')
    fig.suptitle('기본 형태의 수치 분포 · 값 삭제 없음', fontsize=15)
    figure('02_numeric.png', fig)

    fig, axis = plt.subplots(figsize=(8, 7), layout='constrained')
    image = axis.imshow(pearson, vmin=-1, vmax=1, cmap='RdBu_r')
    axis.set_xticks(range(6), pearson.columns)
    axis.set_yticks(range(6), pearson.index)
    for row in range(6):
        for column in range(6):
            value = pearson.iloc[row, column]
            axis.text(column, row, f'{value:.2f}', ha='center', va='center', color='white' if abs(value) > .65 else 'black')
    fig.colorbar(image, ax=axis, label='Pearson 상관계수 r')
    axis.set_title('6개 능력치의 Pearson 상관 · 1,025종')
    figure('03_correlations.png', fig)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), layout='constrained')
    categories = list(KINDS)
    axes[0, 0].boxplot([documents.loc[documents.kind == k, 'length'] for k in categories], tick_labels=[KINDS[k] for k in categories], showfliers=False)
    axes[0, 0].set(title='문서 종류별 길이 (이상치 점 생략)', ylabel='문자 수 (Unicode code point)')
    cohorts = [((documents.language == 'en'), '영어 원문', blue),
               ((documents.language == 'ko') & ~documents.generated, '기존 한국어', '#4D8C60'),
               (documents.generated, '생성 한국어', orange), ((documents.language == 'und'), '구조화 조건', '#777777')]
    bottom = np.zeros(len(categories))
    for mask, label, color in cohorts:
        values = documents.loc[mask].groupby('kind').size().reindex(categories, fill_value=0).to_numpy()
        axes[0, 1].bar([KINDS[k] for k in categories], values, bottom=bottom, label=label, color=color)
        bottom += values
    axes[0, 1].set(title='문서 종류별 언어·번역 구성', ylabel='문서 레코드 수 (건)')
    axes[0, 1].legend(frameon=False)
    axes[1, 0].hist(doc_per_item, bins='fd', color=blue, edgecolor='white')
    axes[1, 0].set(title='포켓몬 한 종에 연결된 문서 수', xlabel='문서 레코드 수 (건/종)', ylabel='종 수 (종)')
    x = np.arange(len(duplicate_table))
    axes[1, 1].bar(x-.18, duplicate_table['레코드 수'], width=.36, label='전체 레코드', color=blue)
    axes[1, 1].bar(x+.18, duplicate_table['언어별 고유 본문 수'], width=.36, label='언어별 고유 본문', color=orange)
    axes[1, 1].set_xticks(x, duplicate_table.index)
    axes[1, 1].set(title='문서 레코드와 고유 본문 수', ylabel='건수 (건)')
    axes[1, 1].legend(frameon=False)
    fig.suptitle('최종 문서 64,264건: 길이·구성·반복', fontsize=15)
    figure('04_documents.png', fig)

    unique_lang_content = documents.drop_duplicates(['language', 'content_hash']).shape[0]
    quality = {'species': len(items), 'documents': len(docs), 'unique_item_ids': metadata.item_id.nunique(),
               'unique_document_ids': documents.doc_id.nunique(), 'unlinked_documents': int((~documents.item_id.isin(metadata.item_id)).sum()),
               'empty_documents': int((documents.length == 0).sum()), 'numeric_missing_values': int(metadata[STATS + ['height_m', 'weight_kg']].isna().sum().sum()),
               'nonpositive_heights': int((metadata.height_m <= 0).sum()), 'nonpositive_weights': int((metadata.weight_kg <= 0).sum()),
               'single_type_species': int((metadata.type_count == 1).sum()), 'dual_type_species': int((metadata.type_count == 2).sum()),
               'type_assignments': len(type_rows), 'type_combination_count': len({tuple(sorted(i['types'])) for i in items}),
               'legendary_mythical_overlap': int((metadata.is_legendary & metadata.is_mythical).sum()),
               'missing_korean_ability_names': int(metadata.missing_ability_names.sum()),
               'unique_language_contents': unique_lang_content, 'repeated_records': len(documents) - unique_lang_content,
               'repeated_record_rate_pct': (len(documents)-unique_lang_content)/len(documents)*100,
               'source_url_count': documents.source_url.nunique(),
               'generated_korean_documents': int(documents.generated.sum()),
               'generated_share_of_all_documents_pct': documents.generated.mean()*100,
               'generated_share_of_korean_documents_pct': documents.loc[documents.language == 'ko', 'generated'].mean()*100,
               'weight_height_pearson': metadata[['height_m', 'weight_kg']].corr().iloc[0, 1],
               'weight_height_spearman': metadata[['height_m', 'weight_kg']].corr(method='spearman').iloc[0, 1],
               'input_sha256': before, 'runtime': {'pandas': pd.__version__, 'numpy': np.__version__, 'matplotlib': matplotlib.__version__}}
    after = {p.name: digest(p) for p in paths}
    if before != after:
        raise ValueError('EDA mutated the source inputs')
    if len(items) != 1025 or len(docs) != 64264 or quality['unlinked_documents'] or quality['empty_documents']:
        raise ValueError('Unexpected final corpus coverage')
    quality['input_files_unchanged'] = True
    (OUTPUT / 'summary.json').write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding='utf-8')
    off_diagonal = [(pearson.iloc[i,j], pearson.index[i], pearson.columns[j]) for i in range(6) for j in range(i+1,6)]
    top = sorted(off_diagonal, key=lambda row: abs(row[0]), reverse=True)[:3]
    lines = ['# 최종 포켓몬 데이터 통계 EDA', '', '분석일: 2026-10-22. 기술통계만 수행했다. 외부 API·GMS·임베딩·모델 학습·검색 품질 실험은 실행하지 않았다.', '',
             '## 분석 단위와 조건', '',
             '- 종 단위: 전국도감 1~1,025번의 기본 개체. 리전폼·메가진화 등 형태별 개체 1,351개를 별도 종으로 세지 않는다.',
             '- 수치·타입·특성은 고정 원본 스냅샷의 기본 형태 기준이다. 세대별 표의 세대는 최초 등장 세대이며, 각 세대 당시의 과거 능력치를 뜻하지 않는다.',
             '- 문서 단위: 원본 64,017건 + 생성 한국어 247건 = 64,264건. 같은 설명이 항목·버전에 따라 반복 연결된다.',
             '- 표준편차는 모집단 기준(ddof=0). 분위수는 선형 보간. IQR 밖 값은 Q1−1.5×IQR 미만 또는 Q3+1.5×IQR 초과이며 삭제하지 않았다.',
             '- 포켓몬 설정 전체 목록에 대한 관측 요약이다. 무작위 표본이 아니므로 p값·신뢰구간·인과관계를 제시하지 않는다.', '',
             '## 1. 기본 품질·구조', '',
             f'- 고유 종 ID {quality["unique_item_ids"]:,} / 고유 문서 ID {quality["unique_document_ids"]:,}. 연결 없는 문서 {quality["unlinked_documents"]} / 빈 본문 {quality["empty_documents"]}.',
             f'- 8개 핵심 수치의 결측 {quality["numeric_missing_values"]} / 0 이하 키 {quality["nonpositive_heights"]} / 0 이하 몸무게 {quality["nonpositive_weights"]}.',
             f'- 중첩 특성 한국어 이름 결측 {quality["missing_korean_ability_names"]}개 항목 연결. 특성 자체가 없다는 뜻과 구별한다.',
             f'- 원본 입력 파일 SHA-256 실행 전후 일치. 원본·최종 보완본 모두 수정하지 않았다.', '', markdown(missing), '',
             '## 2. 세대·타입·분류 분포', '', markdown(generation), '',
             f'단일 타입 {quality["single_type_species"]}종({quality["single_type_species"]/len(items):.2%}), 복합 타입 {quality["dual_type_species"]}종({quality["dual_type_species"]/len(items):.2%}). 타입 조합은 순서를 구분하지 않으면 {quality["type_combination_count"]}종류다.', '',
             f'타입 표는 복합 타입을 각각 집계하여 총 {quality["type_assignments"]:,}회다. 비율의 분모는 고유 1,025종으로, 비율 합계는 100%를 넘는다.', '', markdown(type_counts), '',
             '![세대별·타입별 종 분포](eda_figures/01_population.png)', '',
             '## 3. 능력치·키·몸무게 기술통계', '', markdown(numeric), '',
             f'몸무게 평균 {metadata.weight_kg.mean():.2f}kg, 중앙값 {metadata.weight_kg.median():.2f}kg으로 큰 값 쪽의 영향을 받는다. 키의 평균은 {metadata.height_m.mean():.2f}m, 중앙값은 {metadata.height_m.median():.2f}m다.', '',
             '종족값 합계는 HP·공격·방어·특수공격·특수방어·스피드의 단순 합이다. 대전 성능이나 사용률을 측정한 값이 아니다.', '', markdown(group_bst), '',
             '![수치 분포와 능력치 사분위](eda_figures/02_numeric.png)', '',
             '몸무게 히스토그램은 양의 값의 로그 가로축이며 로그값의 평균을 표에 쓴 것은 아니다. 박스플롯에서만 이상치 점을 생략했고 모든 수치를 통계에 포함했다.', '',
             '## 4. 상관관계', '', markdown(pearson.round(3)), '',
             '절댓값이 큰 비대각 Pearson 상관 3쌍: ' + ', '.join(f'{a}–{b} r={value:.3f}' for value,a,b in top) + '.', '',
             f'키–몸무게 상관은 Pearson r={quality["weight_height_pearson"]:.3f}, Spearman ρ={quality["weight_height_spearman"]:.3f}. 관측된 연관성이고 인과관계는 아니다.', '',
             '종족값 합계와 각 구성 능력치의 상관은 합계 정의에 영향을 받으므로 위 6개 능력치 상관 표에 합계를 포함하지 않았다. Spearman 전체 표는 로컬 집계 파일에 저장했다.', '',
             '![능력치 Pearson 상관](eda_figures/03_correlations.png)', '',
             '## 5. 문서 구성·길이·반복', '', markdown(doc_counts), '', markdown(doc_lengths), '',
             '길이 단위는 Python 문자열의 문자 수(Unicode code point)다. 토큰 수가 아니며, 언어별 같은 문자 수가 같은 정보량·토큰 수라는 뜻도 아니다. 진화 체인은 구조화 JSON 문자열을 포함한다.', '',
             '한 종에 연결된 문서 수의 기술통계:', '', markdown(per_item_stats), '', markdown(duplicate_table), '',
             f'전체 언어별 고유 본문은 {unique_lang_content:,}개, 반복 레코드는 {quality["repeated_records"]:,}건({quality["repeated_record_rate_pct"]:.2f}%)이다. 동일 언어·본문 해시 기준이며 게임 버전과 항목 ID는 구별하지 않은 수치다.', '',
             '반복 비율이 높다는 사실만으로 잘못된 중복이라고 판단하지 않는다. 특성·진화 체인이 여러 항목에 연결되거나 동일 문구가 다른 버전에 수록된 경우를 포함한다. 본문이 같은 문서라도 출처·연결 항목·버전이 다를 수 있다. 이번 분석에서 삭제·병합하지 않았다.', '',
             f'문서의 직접 source_url은 {quality["source_url_count"]}종이다. 이는 설명 CSV의 원문 URL 수이며, 64,264건의 독립된 외부 출처를 뜻하지 않는다. 보조 related_source_urls와 메타데이터 출처를 합친 전체 수집 파일 수와도 구별한다.', '',
             '![문서 구성과 길이·반복](eda_figures/04_documents.png)', '',
             '## 6. 원본 한국어·생성 번역 비중', '', markdown(coverage), '',
             f'생성 한국어 247건은 전체 문서의 {quality["generated_share_of_all_documents_pct"]:.2f}%, 한국어 문서의 {quality["generated_share_of_korean_documents_pct"]:.2f}%다. 종 기준으로는 127/1,025={127/1025:.2%}이며 문서 기준 비율과 다르다.', '',
             '원본 한국어 설명 보유 898종과 생성 번역으로 보완한 127종을 합쳐 1,025종이다. 생성 번역 보완은 사실 정확성·공식 번역 일치·검색 품질을 통계적으로 검증한 결과가 아니다.', '',
             '## 재현·산출물', '', '```powershell', 'python -m pip install -r requirements-pokemon-eda.txt', 'python scripts/run_pokemon_eda.py', '```', '',
             '- 이 문서와 그림은 집계 결과만 포함한다. 포켓몬 개별 행·본문·키·원본 데이터는 Git에 추가하지 않는다.',
             '- 상세 집계 CSV 12개와 검증 JSON은 로컬 `outputs/pokemon/eda/`에 저장한다. Git 제외 경로다.',
             f'- 실행 환경: pandas {pd.__version__}, NumPy {np.__version__}, Matplotlib {matplotlib.__version__}.',
             '- 이번 작업은 기술통계 EDA로 종료한다. 이후 별도 작업에서 요구사항과 RAG 설계를 진행한다.', '']
    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(quality, ensure_ascii=False, indent=2))
    print('Report:', REPORT)


if __name__ == '__main__':
    main()
