import re

_ws = re.compile(r"\s+")

def norm(s: str) -> str:
    # trim + collapse whitespace + lowercase
    return _ws.sub(" ", s.strip()).lower()
