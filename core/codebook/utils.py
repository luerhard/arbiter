def normalize_content(content: str | None) -> str:
    """Normalize line endings and surrounding whitespace for comparisons.

    Browsers submit textarea content with \\r\\n line endings while the
    git-backed codebook stores \\n; comparing raw strings would flag every
    untouched submission as a change.
    """
    return "\n".join((content or "").splitlines()).strip()
