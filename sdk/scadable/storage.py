"""
Storage base classes.

Docs: https://docs.scadable.com/docs/edge/storage
"""
from .constants import MB_512, MB_256


class FileStorage:
    """
    File-based local storage for blobs (images, binary data).

    Data is stored as files on disk. Partitions keep data isolated.
    Oldest files are evicted when max_size is reached.

    Example:
        class CameraImages(FileStorage):
            id = "camera-images"
            path = "/var/data/images"
            max_size = GB_1
            warn_at = 80
    """

    id: str = None
    path: str = None
    max_size: int = MB_512
    warn_at: int = 80

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ in ("FileStorage", "SQLiteStorage"):
            return
        errors = []
        if not cls.id:
            errors.append(f"Storage '{cls.__name__}' must define 'id'")
        if not cls.path:
            errors.append(f"Storage '{cls.__name__}' must define 'path'")
        if not isinstance(cls.warn_at, int) or not (1 <= cls.warn_at <= 100):
            errors.append(f"Storage '{cls.__name__}' - warn_at must be 1-100")
        if errors:
            raise TypeError("\n".join(errors))

    def __repr__(self):
        return f"<FileStorage id={self.id!r} path={self.path!r}>"


class SQLiteStorage:
    """
    SQLite-based local storage for structured data (tables, rows, queries).

    Data is stored in a SQLite database with WAL mode. Oldest rows are
    evicted when max_size is reached.

    Example:
        class DeviceHistory(SQLiteStorage):
            id = "device-history"
            path = "/var/data/cache.db"
            max_size = MB_256
            warn_at = 80
    """

    id: str = None
    path: str = None
    max_size: int = MB_256
    warn_at: int = 80

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ in ("FileStorage", "SQLiteStorage"):
            return
        errors = []
        if not cls.id:
            errors.append(f"Storage '{cls.__name__}' must define 'id'")
        if not cls.path:
            errors.append(f"Storage '{cls.__name__}' must define 'path'")
        if not isinstance(cls.warn_at, int) or not (1 <= cls.warn_at <= 100):
            errors.append(f"Storage '{cls.__name__}' - warn_at must be 1-100")
        if errors:
            raise TypeError("\n".join(errors))

    def __repr__(self):
        return f"<SQLiteStorage id={self.id!r} path={self.path!r}>"
