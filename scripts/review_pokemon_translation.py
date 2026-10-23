"""Validate the generated Korean overlay and write a local, human-readable comparison."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.collect_pokemon import ROOT, save
from scripts.translate_pokemon_descriptions import MODEL, select_targets, validate_response
from scripts.pokemon_korean_terms import RULES, RULES_VERSION


def audit(items, originals, enriched, translations):
    original_ko, missing, targets = select_targets(items, originals)
    expected = {d['doc_id']: d for d in targets}
    if len(translations) != len(expected) or {t['original_doc_id'] for t in translations} != set(expected):
        raise ValueError('Translation source coverage differs')
    if enriched[:len(originals)] != originals or enriched[len(originals):] != translations:
        raise ValueError('Original corpus altered or enrichment contents differ')
    if len({d['doc_id'] for d in enriched}) != len(enriched):
        raise ValueError('Duplicate enriched document IDs')
    for translated in translations:
        source = expected[translated['original_doc_id']]
        if any(translated[k] != source[k] for k in ('item_id', 'version', 'source_url', 'source_revision')):
            raise ValueError('Translation source metadata mismatch')
        if translated['original_content'] != source['content'] or translated['language'] != 'ko' or not translated['is_machine_translation'] or translated['source_type'] != 'machine_translation':
            raise ValueError('Translation source text/language/label mismatch')
        if translated['translation_model'] != MODEL or translated['translation_response_model'] != MODEL:
            raise ValueError('Translation model does not match the selected GMS model')
        validate_response([{'source_doc_id': source['doc_id'], 'english': source['content']}],
                          {'entries': [{'source_doc_id': source['doc_id'], 'translation': translated['content']}]})
    ko_after = {d['item_id'] for d in enriched if d['kind'] == 'species_description' and d['language'] == 'ko'}
    if ko_after != {i['item_id'] for i in items}:
        raise ValueError('Missing Korean coverage after enrichment')
    return {'total_species': len(items), 'original_korean_species': len(original_ko),
            'original_missing_species': len(missing), 'translated_species': len({t['item_id'] for t in translations}),
            'translated_entries': len(translations), 'enriched_korean_species': len(ko_after), 'remaining_missing_species': 0,
            'original_documents_preserved': True, 'original_documents': len(originals), 'enriched_documents': len(enriched),
            'translated_versions': dict(Counter(t['version'] for t in translations)),
            'entries_with_model_review_notes': sum(bool(t['review_notes']) for t in translations),
            'entries_with_verified_term_corrections': sum(bool(t['verified_terminology_corrections']) for t in translations),
            'entries_with_fidelity_corrections': sum(bool(t['fidelity_corrections']) for t in translations),
            'human_reviewed_entries': sum(t['human_reviewed'] for t in translations)}


def main():
    directory = ROOT / 'dataset/pokemon'
    def load(name):
        return json.loads((directory / name).read_text(encoding='utf-8'))
    items, originals = load('items.json'), load('documents.json')
    translations = load('translations/korean_descriptions.json')
    summary = audit(items, originals, load('documents_ko_enriched.json'), translations)
    by_id = {i['item_id']: i for i in items}
    # Compare related older species / same broad theme, never imply equal settings.
    pairs = [(899, 234, 'legends-arceus', 'sword'), (900, 123, 'legends-arceus', 'sword'),
             (906, 1, 'scarlet', 'sword'), (909, 4, 'scarlet', 'sword')]
    comparisons = []
    for new_id, old_id, new_version, old_version in pairs:
        new = next(d for d in translations if d['item_id'] == f'pokemon-species:{new_id}' and d['version'] == new_version)
        candidates = [d for d in originals if d['item_id'] == f'pokemon-species:{old_id}' and d['kind'] == 'species_description' and d['language'] == 'ko']
        old = next((d for d in candidates if d['version'] == old_version), candidates[-1])
        comparisons.append({'new_name': by_id[new['item_id']]['name_ko'], 'new_version': new['version'],
                            'english': new['original_content'], 'generated_korean': new['content'],
                            'old_name': by_id[old['item_id']]['name_ko'], 'old_version': old['version'], 'original_korean': old['content']})
    output = ROOT / 'outputs/pokemon'
    output.mkdir(parents=True, exist_ok=True)
    save(output / 'translation_audit.json', summary)
    save(output / 'translation_comparisons.json', comparisons)
    lines = ['# 생성 한국어 번역과 기존 세대 설명 비교', '',
             '생성 번역은 공식 한국어 도감 문구가 아닙니다. 원문 의미 보존을 위한 모델 번역·별도 모델 검수를 거쳤으며 사람의 전수 검수는 하지 않았습니다.', '',
             f'기존 한국어 {summary["original_korean_species"]}종 + 번역 보완 {summary["translated_species"]}종 = {summary["enriched_korean_species"]}종.', '']
    for pair in comparisons:
        lines += [f'## {pair["new_name"]} ↔ {pair["old_name"]}', '',
                  f'**보완 대상: {pair["new_name"]} / {pair["new_version"]}**', '',
                  f'- 영어 원문: {pair["english"]}', f'- 생성 한국어 번역: {pair["generated_korean"]}', '',
                  f'**기존 수록: {pair["old_name"]} / {pair["old_version"]}**', '', pair['original_korean'], '']
    lines += ['# 전체 247건: 영어 원문·생성 번역', '']
    for translated in translations:
        name = by_id[translated['item_id']]['name_ko']
        lines += [f'## {name} / {translated["version"]}', '', f'- 원문: {translated["original_content"]}',
                  f'- 생성 번역: {translated["content"]}', f'- 모델 검수 메모: {"; ".join(translated["review_notes"]) or "수정 메모 없음"}', '']
        for correction in translated['verified_terminology_corrections']:
            lines += [f'- 모델 검수 이후 공식 용어 교정: {correction["english"]} → {correction["korean"]} ({correction["source_url"]})', '']
        if translated['fidelity_corrections']:
            lines += ['- 모델 검수 이후 의미 보정: 원문의 대명사가 가리키는 대상을 얼굴로 한정하지 않도록 수정.', '']
    (output / 'TRANSLATION_REVIEW.md').write_text('\n'.join(lines), encoding='utf-8')
    baseline_path = directory / 'translations/korean_descriptions_before_localization.json'
    if baseline_path.exists():
        baseline = {d['doc_id']: d for d in json.loads(baseline_path.read_text(encoding='utf-8'))}
        changed = [d for d in translations if d['doc_id'] in baseline and baseline[d['doc_id']]['content'] != d['content']]
        term_summary = {'verified_rules': len(RULES), 'rules_version': RULES_VERSION,
                        'changed_entries': len(changed), 'changed_species': len({d['item_id'] for d in changed}),
                        'new_model_calls_for_localization': 0, 'original_documents_preserved': True}
        save(output / 'korean_terms_audit.json', term_summary)
        term_lines = ['# 한국어 명칭·용어 보완 전후', '',
                      '포켓몬 공식 한국어 자료에서 확인한 용어만 적용했습니다. 문장 전체를 공식 번역으로 교체한 것은 아닙니다.', '',
                      f'확인 용어 {len(RULES)}개 / 이번 수정 {len(changed)}건 / 원본과 게임 버전 보존 / 신규 모델 호출 0회', '',
                      '## 확인한 용어', '']
        for rule in RULES:
            term_lines += [f'- {rule["english"]} → **{rule["korean"]}**: {rule["source_url"]}']
        for translated in changed:
            term_lines += ['', f'## {by_id[translated["item_id"]]["name_ko"]} / {translated["version"]}', '',
                           f'- 영어 원문: {translated["original_content"]}',
                           f'- 보완 전: {baseline[translated["doc_id"]]["content"]}', f'- 보완 후: {translated["content"]}']
        (output / 'KOREAN_TERMS_REVIEW.md').write_text('\n'.join(term_lines), encoding='utf-8')
        print(json.dumps(term_summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(comparisons, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
