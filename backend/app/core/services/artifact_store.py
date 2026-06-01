from pathlib import Path
from typing import Protocol

from app.features.core.config import get_settings


class ArtifactStore(Protocol):
    """Protocol for artifact storage backends.

    Artifacts are identified by a key following the convention
    ``{universe_slug}/{model_role}/{training_run_id}.pt``.
    """

    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...

    def list(self, prefix: str) -> list[str]: ...


class LocalArtifactStore:
    """Stores artifacts on the local filesystem under ``ARTIFACT_STORE_PATH``."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or get_settings().get_artifact_store_path()

    def _resolve(self, key: str) -> Path:
        resolved = (self._root / key).resolve()
        if not str(resolved).startswith(str(self._root.resolve())):
            raise ValueError(f"Key {key!r} escapes the artifact store root")
        return resolved

    def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(f"Artifact not found: {key}")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        path.unlink(missing_ok=True)

    def list(self, prefix: str) -> list[str]:
        root = self._resolve(prefix)
        if not root.is_dir():
            return []
        relative_root = self._root.resolve()
        return [
            str(p.resolve().relative_to(relative_root)).replace("\\", "/")
            for p in root.rglob("*")
            if p.is_file()
        ]


class S3ArtifactStore:
    """Stub for future MinIO / S3-compatible artifact storage.

    This backend will be swapped in once MinIO is provisioned.  All
    methods raise ``NotImplementedError`` until the integration is
    complete.
    """

    def put(self, key: str, data: bytes) -> None:
        raise NotImplementedError("S3ArtifactStore is not yet implemented")

    def get(self, key: str) -> bytes:
        raise NotImplementedError("S3ArtifactStore is not yet implemented")

    def exists(self, key: str) -> bool:
        raise NotImplementedError("S3ArtifactStore is not yet implemented")

    def delete(self, key: str) -> None:
        raise NotImplementedError("S3ArtifactStore is not yet implemented")

    def list(self, prefix: str) -> list[str]:
        raise NotImplementedError("S3ArtifactStore is not yet implemented")


def get_artifact_store() -> ArtifactStore:
    """Return the configured artifact store implementation.

    To swap backends (e.g. local → S3), change the return value here;
    the rest of the codebase depends only on the ``ArtifactStore``
    Protocol.
    """
    return LocalArtifactStore()
