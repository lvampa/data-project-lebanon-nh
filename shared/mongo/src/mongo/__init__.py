from .client import MongoDB
from .init import init_indexes

db = MongoDB()

__all__ = ["db", "init_indexes", "MongoDB"]
