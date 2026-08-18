#!/usr/bin/env python3
"""Report terminal display-cell widths for diagram lines."""

from __future__ import annotations

import sys
import unicodedata


def is_variation_selector(character: str) -> bool:
    code_point = ord(character)
    return 0xFE00 <= code_point <= 0xFE0F or 0xE0100 <= code_point <= 0xE01EF


def cell_width(character: str) -> tuple[int, bool]:
    """Return the expected cell width and whether rendering may be unstable."""
    category = unicodedata.category(character)
    if is_variation_selector(character) or character == "\u200d":
        return 0, True
    if unicodedata.combining(character):
        return 0, False
    if category in {"Cc", "Cf", "Cs", "Me"}:
        return 0, True

    east_asian_width = unicodedata.east_asian_width(character)
    if east_asian_width in {"W", "F"}:
        return 2, False
    unstable = east_asian_width == "A" or category == "So"
    return 1, unstable


def main() -> int:
    for line_number, raw_line in enumerate(sys.stdin, start=1):
        line = raw_line.rstrip("\r\n")
        widths = [cell_width(character) for character in line]
        unstable = [
            character
            for character, (_, unsafe) in zip(line, widths, strict=True)
            if unsafe
        ]
        suffix = f" unstable={unstable!r}" if unstable else ""
        print(f"{line_number:>3}: {sum(width for width, _ in widths):>3}{suffix} | {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
