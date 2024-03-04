def to_base15(n,comma=None):
    while n > 0:
        yield n % 15 
        n = n // 15 
    if comma:
        yield comma

def from_base15(base15):
    def placed():
        place = 1
        for digit in base15:
            yield place * digit
            place *= 15
    return sum(placed())

def read_base15(file):
    def read_nibbles():
        with open(file, "rb") as f:
            while (byte := f.read(1)):
                val = int.from_bytes(byte, 'big')
                yield from (val >> 4, val & 15)
    digits = []
    comma = int('1111', 2)
    for nibble in read_nibbles():
        if nibble == comma:
            yield from_base15(digits)
            digits = []
            continue
        digits.append(nibble)

def write_base15(file, array):
    comma = int('1111', 2)
    digits = [
        digit for value in array
        for digit in to_base15(value, comma)
    ]
    base15_bytes = bytes([
        (digit1 << 4) + digit2 for digit1,digit2
        in zip(digits[:-1:2], digits[1::2])
    ])
    with open(file, 'wb') as f:
        f.write(base15_bytes)
