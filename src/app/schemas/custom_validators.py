from pydantic import AfterValidator


def require_unique(v):
    """
    Check that the list is unique."""
    if v != set(v):
        raise ValueError("not unique")
    return v


EnsureListUnique = AfterValidator(require_unique)
