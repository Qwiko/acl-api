from typing import List
import math

ALPHABET_SIZE = 26


def get_rank_between(first_rank: str, second_rank: str) -> str:
    assert first_rank < second_rank, (
        f"First position must be lower than second. " f"Got firstRank {first_rank} and secondRank {second_rank}"
    )

    # Make positions equal in length
    while len(first_rank) != len(second_rank):
        if len(first_rank) > len(second_rank):
            second_rank += "a"
        else:
            first_rank += "a"

    first_position_codes: List[int] = list(map(ord, first_rank))
    second_position_codes: List[int] = list(map(ord, second_rank))

    difference = 0

    for index in range(len(first_position_codes) - 1, -1, -1):
        first_code = first_position_codes[index]
        second_code = second_position_codes[index]

        if second_code < first_code:
            second_code += ALPHABET_SIZE
            second_position_codes[index - 1] -= 1

        pow_res = int(math.pow(ALPHABET_SIZE, len(first_rank) - index - 1))
        difference += (second_code - first_code) * pow_res

    new_element = ""

    if difference <= 1:
        new_element = first_rank + chr(ord("a") + ALPHABET_SIZE // 2)
    else:
        difference //= 2
        offset = 0
        new_chars = []

        for index in range(len(first_rank)):
            diff_in_symbols = (difference // int(math.pow(ALPHABET_SIZE, index))) % ALPHABET_SIZE
            new_element_code = ord(first_rank[len(second_rank) - index - 1]) + diff_in_symbols + offset
            offset = 0

            if new_element_code > ord("z"):
                offset += 1
                new_element_code -= ALPHABET_SIZE

            new_chars.append(chr(new_element_code))

        new_element = "".join(reversed(new_chars))

    return new_element
