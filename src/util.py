import re
import unicodedata

_chunk = re.compile(r"([0-9]+)")
_sub1 = re.compile(r"[^\w\s-]")
_sub2 = re.compile(r"[-\s]+")


# Based on Ned Batchelder's simplification of Dave Koelle's alphanum algorithm,
# but I'm not sure if this is 100% correct.
# isdigit is faster than branching off handling a ValueError.
def alphanum_key(s: str):
    return [int(chunk) if chunk.isdigit() else chunk for chunk in _chunk.split(s)]


# Adapted from Django.
def slugify(value: str, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    return _sub2.sub("-", _sub1.sub("", value.lower())).strip("-_")
