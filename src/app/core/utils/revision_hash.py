import hashlib


def revision_hash(revision_config: str) -> str:
    return hashlib.blake2b(revision_config.encode(), digest_size=16).hexdigest()