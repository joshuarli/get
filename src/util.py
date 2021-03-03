import re

_chunk = re.compile(r"([0-9]+)")


# Based on Ned Batchelder's simplification of Dave Koelle's alphanum algorithm,
# but I'm not sure if this is 100% correct.
# isdigit is faster than branching off handling a ValueError.
def alphanum_key(s):
    return [int(chunk) if chunk.isdigit() else chunk for chunk in _chunk.split(s)]
