"""Minimal chromadb stub for Vercel - memory not used in this app."""

class Settings:
    def __init__(self, **kwargs): pass

class Collection:
    def add(self, *a, **kw): pass
    def query(self, *a, **kw): return {"documents": [], "ids": []}
    def get(self, *a, **kw): return {"documents": [], "ids": []}
    def upsert(self, *a, **kw): pass
    def delete(self, *a, **kw): pass
    def count(self): return 0

class _BaseClient:
    def __init__(self, *a, **kw): pass
    def get_or_create_collection(self, name, *a, **kw): return Collection()
    def get_collection(self, name, *a, **kw): return Collection()
    def create_collection(self, name, *a, **kw): return Collection()
    def delete_collection(self, name, *a, **kw): pass
    def list_collections(self): return []
    def reset(self): pass

class EphemeralClient(_BaseClient): pass
class PersistentClient(_BaseClient):
    def __init__(self, path="", *a, **kw): pass
class HttpClient(_BaseClient): pass
class AsyncHttpClient(_BaseClient): pass
Client = EphemeralClient

def configure(**kwargs): pass
