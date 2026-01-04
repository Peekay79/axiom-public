from qdrant_client import QdrantClient as _QdrantClient


# Simple passthrough to keep legacy imports working
class QdrantClient(_QdrantClient):
    pass
