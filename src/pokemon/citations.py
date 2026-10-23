"""Validate citation references and expose only sources actually cited."""
import re

CITATION = re.compile(r'\[근거\s+(\d+(?:\s*,\s*\d+)*)\]')
NOTICE = '답변에 인용된 근거가 없습니다.'


def prompt_evidence(evidence):
    # Supplementary URL lists belong to the display registry, not the model context.
    return [{k:v for k,v in entry.items() if k not in ('source_urls','chunk_index')} for entry in evidence]


def citation_numbers(answer):
    groups = re.findall(r'\[근거[^\]]*\]', answer)
    if answer.count('[근거') != len(groups) or any(CITATION.fullmatch(group) is None for group in groups):
        raise ValueError('Malformed citation')
    return sorted({int(n) for group in CITATION.findall(answer) for n in group.split(',')})


def validate_answer(result, evidence):
    if set(result) != {'answer', 'status'} or result['status'] not in ('answered', 'insufficient'):
        raise ValueError('Invalid answer contract')
    if not isinstance(result['answer'], str) or not result['answer'].strip():
        raise ValueError('Empty answer')
    if re.search(r'https?://', result['answer']):
        raise ValueError('Source URLs must come from the evidence registry')
    numbers = citation_numbers(result['answer'])
    if any(n < 1 or n > len(evidence) for n in numbers):
        raise ValueError('Unknown citation number')
    if result['status'] == 'answered' and not numbers:
        raise ValueError('Factual answer requires citations')


def used_sources(answer, evidence):
    numbers = citation_numbers(answer)
    if any(n < 1 or n > len(evidence) for n in numbers):
        raise ValueError('Unknown citation number')
    return [{k: v for k, v in evidence[n-1].items() if k not in ('text', 'original_text')}
            for n in numbers]
