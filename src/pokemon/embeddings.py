"""Explicit GMS-only embeddings with validated, content-addressed local cache."""
import json
import math
import os
from pathlib import Path

from .data import fingerprint

GMS_BASE = 'https://gms.ssafy.io/gmsapi/api.openai.com/v1/'


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def validate_vectors(vectors, count, dimensions):
    if len(vectors) != count:
        raise ValueError('Embedding response count mismatch')
    for vector in vectors:
        if len(vector) != dimensions or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                            or not math.isfinite(v) for v in vector):
            raise ValueError('Invalid embedding shape or values')
        if sum(v * v for v in vector) == 0:
            raise ValueError('Zero embedding vector')


class GmsEmbeddings:
    def __init__(self, config, cache_path, env_path, offline=False, client=None):
        if config['base_url'] != GMS_BASE:
            raise ValueError('Only the configured SSAFY GMS endpoint is allowed')
        self.model = config['embedding_model']
        self.dimensions = config['embedding_dimensions']
        self.batch_size = config['batch_size']
        if not (1 <= self.batch_size <= 128 and self.dimensions > 0):
            raise ValueError('Invalid embedding configuration')
        self.cache = Path(cache_path)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.env_path, self.offline, self.client = env_path, offline, client
        self.calls = self.hits = self.tokens = 0

    def embed(self, texts):
        import tiktoken
        encoder = tiktoken.get_encoding('cl100k_base')
        for text in texts:
            if not text.strip() or len(encoder.encode(text)) > 8000:
                raise ValueError('Empty input or embedding token limit exceeded')
        keys = [fingerprint([GMS_BASE, self.model, self.dimensions, text]) for text in texts]
        result, missing = {}, {}
        for key, text in zip(keys, texts):
            path = self.cache / (key + '.json')
            if path.exists():
                cached = json.loads(path.read_text(encoding='utf-8'))
                if cached['key'] != key or cached['vector_hash'] != fingerprint(cached['vector']):
                    raise ValueError('Embedding cache integrity mismatch')
                validate_vectors([cached['vector']], 1, self.dimensions)
                result[key] = cached['vector']
                self.hits += 1
            else:
                missing[key] = text
        if missing and self.offline:
            raise RuntimeError('Embedding cache missing in offline mode; no network call made')
        if missing and self.client is None:
            from dotenv import dotenv_values
            from openai import OpenAI
            key = os.environ.get('GMS_KEY') or dotenv_values(self.env_path).get('GMS_KEY')
            if not key:
                raise RuntimeError('GMS_KEY is not configured')
            self.client = OpenAI(api_key=key, base_url=GMS_BASE, timeout=60, max_retries=2)
        pairs = list(missing.items())
        for start in range(0, len(pairs), self.batch_size):
            batch = pairs[start:start + self.batch_size]
            response = self.client.embeddings.create(model=self.model, input=[t for _, t in batch],
                                                     dimensions=self.dimensions, encoding_format='float')
            self.calls += 1
            if response.model != self.model or sorted(e.index for e in response.data) != list(range(len(batch))):
                raise ValueError('Embedding response model or indexes mismatch')
            vectors = [e.embedding for e in sorted(response.data, key=lambda e: e.index)]
            validate_vectors(vectors, len(batch), self.dimensions)
            self.tokens += response.usage.total_tokens if response.usage else 0
            for (key, _), vector in zip(batch, vectors):
                write_json(self.cache / (key + '.json'), {'key': key, 'vector': vector,
                                                         'vector_hash': fingerprint(vector)})
                result[key] = vector
        return [result[key] for key in keys]
