"""Local Chroma persistence; embeddings must always be supplied explicitly."""
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def indexing_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open('x')
    except FileExistsError:
        raise RuntimeError('Indexing lock exists; check no process is active before removing it') from None
    try:
        with handle:
            yield
    finally:
        path.unlink()


def open_collection(path, name, signature):
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(name=name, embedding_function=None,
        metadata={'index_signature': signature}, configuration={'hnsw': {'space': 'cosine'}})
    if collection.metadata.get('index_signature') != signature:
        raise ValueError('Index configuration or input changed; use a new collection name')
    return collection


def read_collection(path, name, signature):
    """Read an existing index; never create an empty collection on retrieval."""
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    collection = client.get_collection(name=name, embedding_function=None)
    if collection.metadata.get('index_signature') != signature:
        raise ValueError('Existing index signature mismatch')
    return collection
