def parse_base(digits: list[int], base: int):
    place = 1
    for digit in digits:
        yield place * digit
        place *= base

def as_base(n: int, base: int):
    if n == 0:
        yield 0
    while n > 0:
        yield n % base
        n = n // base

def lookup_string(indices: list[int], lookup: list[str]):
    return ''.join(
        lookup[index - 1]
        if index > 0 else ' '
        for index in indices
    ).strip()

def lookup_index(x: list[str], lookup: list[str]):
    assert x.strip() == x
    yield from (
        lookup.index(char) + 1
        if char != ' ' else 0
        for char in x
    )

def parse_base15(
        digits: list[int], lookup: list[str]
    ):
    lookup_base = 1 + len(lookup)
    if lookup_base == 15:
        # Base 15 used directly 
        return lookup_string(digits, lookup) 
    # Decode digits from base 15
    evaluated = sum(parse_base(
        digits, 15
    ))
    if lookup_base > 1:
        # Convert alternative base
        new_digits = as_base(
            evaluated, lookup_base
        )
        return lookup_string(new_digits, lookup)
    # Return integer
    return evaluated

def as_base15(
        x: str | int, comma: int, lookup: list[str]
    ):
    lookup_base = 1 + len(lookup)
    if lookup_base == 15:
        # Base 15 used directly
        yield from lookup_index(x, lookup)
    elif lookup_base > 1:
        # Convert alternative base
        new_x = sum(parse_base(list(
            lookup_index(x, lookup)
        ), lookup_base))
        yield from as_base(int(new_x), 15)
    else:
        # Encode digits directly to base 15
        yield from as_base(int(x), 15)
    # Signal end of encoded value
    yield comma

def read_base15(file, lookup=None):
    def read_nibbles():
        with open(file, "rb") as f:
            while (byte := f.read(1)):
                val = int.from_bytes(byte, 'big')
                yield from (val >> 4, val & 15)
    digits = []
    comma = int('1111', 2)
    for nibble in read_nibbles():
        if nibble != comma:
            digits.append(nibble)
            continue
        yield parse_base15(digits, lookup or [])
        digits = []
    # Value may or may not exist after final comma
    if len(digits) != 0:
        yield parse_base15(digits, lookup or [])

def write_base15(file, array, lookup=None):
    comma = int('1111', 2)
    digits = [
        digit for value in array
        for digit in as_base15(value, comma, lookup or [])
    ]
    # Value may or may not exist after final comma
    base15_bytes = bytes([
        (digit1 << 4) + digit2 for digit1,digit2
        in zip(digits[:-1:2], digits[1::2])
    ])
    with open(file, 'wb') as f:
        f.write(base15_bytes)
