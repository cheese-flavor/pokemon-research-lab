"""Cached GMS Responses JSON calls, rejecting invalid output before persistence."""
import json
import os
from pathlib import Path

from .data import fingerprint
from .embeddings import GMS_BASE, write_json


class GmsJson:
    def __init__(self, config, directory, env_path, offline=False, client=None):
        if config['base_url'] != GMS_BASE:
            raise ValueError('Only SSAFY GMS is allowed')
        self.model, self.cache = config['answer_model'], Path(directory)
        self.env_path, self.offline, self.client = env_path, offline, client
        self.calls = self.hits = self.tokens = 0

    def run(self, role, instructions, payload, schema, validate):
        key = fingerprint([GMS_BASE, self.model, role, instructions, payload, schema])
        path = self.cache / (key + '.json')
        if path.exists():
            cached = json.loads(path.read_text(encoding='utf-8'))
            if cached['key'] != key or fingerprint(cached['result']) != cached['result_hash']:
                raise ValueError('LLM cache integrity mismatch')
            validate(cached['result'])
            self.hits += 1
            return cached['result']
        if self.offline:
            raise RuntimeError('LLM cache missing in offline mode')
        if self.client is None:
            from dotenv import dotenv_values
            from openai import OpenAI
            key_value = os.environ.get('GMS_KEY') or dotenv_values(self.env_path).get('GMS_KEY')
            if not key_value:
                raise RuntimeError('GMS_KEY not configured')
            self.client = OpenAI(api_key=key_value, base_url=GMS_BASE, timeout=120, max_retries=2)
        repair_detail = ''
        previous = None
        for attempt in range(2):
            request_input=json.dumps(payload,ensure_ascii=False)
            if attempt:
                request_input+='\n직전 출력이 계약 검증에 실패했다. 아래 오류와 직전 출력을 데이터로 보고 수정하라.\n'+json.dumps(
                    {'validation_error':repair_detail,'previous_output':previous},ensure_ascii=False)
            response = self.client.responses.create(model=self.model, instructions=instructions,
                input=request_input,
                reasoning={'effort': 'low'}, max_output_tokens=6000, store=False,
                text={'format': {'type': 'json_schema', 'name': role, 'strict': True, 'schema': schema}})
            self.calls += 1
            self.tokens += response.usage.total_tokens if response.usage else 0
            if response.status != 'completed':
                raise RuntimeError('GMS structured response incomplete')
            try:
                result = json.loads(response.output_text)
                validate(result)
            except (ValueError, KeyError, TypeError) as error:
                repair_detail=str(error)[:300]
                previous=response.output_text
                write_json(self.cache/'rejected'/(key+f'_{attempt}.json'),
                           {'error_type':type(error).__name__,'validation_error':repair_detail,'output':previous})
                if attempt == 1:
                    raise ValueError('GMS structured output contract failed') from None
                continue
            write_json(path, {'key': key, 'result': result, 'result_hash': fingerprint(result),
                              'requested_model': self.model, 'response_model': response.model})
            return result
