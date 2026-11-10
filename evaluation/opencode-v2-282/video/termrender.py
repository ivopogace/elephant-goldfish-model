"""Replay an asciinema recording into images: pyte keeps the screen, Pillow draws it."""

import json

from PIL import Image, ImageDraw, ImageFont
import pyte

FONT_DIR = '/usr/share/fonts/truetype/jetbrains-mono/'
NAMED = {
    'black': '15161e', 'red': 'f7768e', 'green': '9ece6a', 'brown': 'e0af68', 'blue': '7aa2f7',
    'magenta': 'bb9af7', 'cyan': '7dcfff', 'white': 'c0caf5',
    'brightblack': '565f89', 'brightred': 'ff7a93', 'brightgreen': 'b9f27c', 'brightbrown': 'ff9e64',
    'brightblue': '7da6ff', 'brightmagenta': 'c7a9ff', 'brightcyan': '0db9d7', 'brightwhite': 'ffffff',
}
DEFAULT_FG, DEFAULT_BG = 'd6d9e6', '0d0f17'


def rgb(value: str, default: str):
    value = NAMED.get(value, value)
    if value == 'default' or len(value) != 6:
        value = default
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return tuple(int(default[i:i + 2], 16) for i in (0, 2, 4))


def load(path: str):
    """Returns (columns, rows, [(time, text), ...])."""
    with open(path) as cast:
        header = json.loads(cast.readline())
        events = [json.loads(line) for line in cast if line.strip()]
    return header['width'], header['height'], [(e[0], e[2]) for e in events if e[1] == 'o']


class Terminal:
    def __init__(self, columns: int, rows: int, font_size: int = 24, line_height: int = 30):
        self.columns, self.rows = columns, rows
        self.screen = pyte.Screen(columns, rows)
        self.stream = pyte.Stream(self.screen)
        self.regular = ImageFont.truetype(FONT_DIR + 'JetBrainsMono-Regular.ttf', font_size)
        self.bold = ImageFont.truetype(FONT_DIR + 'JetBrainsMono-Bold.ttf', font_size)
        self.fallback = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', font_size - 2)
        self.missing = self.regular.getmask('\U0010ffff').getbbox()
        self.known = {}
        self.cell_w = self.regular.getlength('M')
        self.cell_h = line_height
        self.width, self.height = round(self.cell_w * columns), line_height * rows
        self.version = 0

    def has_glyph(self, glyph: str) -> bool:
        if glyph not in self.known:
            # A glyph the font lacks renders as the same "missing" box as an unassigned code point.
            mask = self.regular.getmask(glyph)
            self.known[glyph] = ord(glyph[0]) < 0x250 or bytes(mask) != bytes(self.regular.getmask('\U0010ffff'))
        return self.known[glyph]

    def feed(self, text: str):
        self.stream.feed(text)
        self.version += 1

    def image(self) -> Image.Image:
        image = Image.new('RGB', (self.width, self.height), rgb('default', DEFAULT_BG))
        draw = ImageDraw.Draw(image)
        for y in range(self.rows):
            line = self.screen.buffer[y]
            top = y * self.cell_h
            x = 0
            while x < self.columns:
                char = line[x]
                fg, bg = rgb(char.fg, DEFAULT_FG), rgb(char.bg, DEFAULT_BG)
                if char.reverse:
                    fg, bg = bg, fg
                # Group cells that share a style so text keeps its kerning-free monospace grid.
                end = x + 1
                while end < self.columns:
                    other = line[end]
                    if (other.fg, other.bg, other.bold, other.reverse) != (char.fg, char.bg, char.bold, char.reverse):
                        break
                    end += 1
                left, right = round(x * self.cell_w), round(end * self.cell_w)
                if bg != rgb('default', DEFAULT_BG):
                    draw.rectangle([left, top, right - 1, top + self.cell_h - 1], fill=bg)
                font = self.bold if char.bold else self.regular
                for column in range(x, end):
                    glyph = line[column].data
                    if glyph in ('', ' '):
                        continue
                    cx = round(column * self.cell_w)
                    cw = round((column + 1) * self.cell_w) - cx
                    # Block and heavy line characters are drawn as shapes so they join across rows.
                    if glyph == '█':
                        draw.rectangle([cx, top, cx + cw - 1, top + self.cell_h - 1], fill=fg)
                    elif glyph == '▀':
                        draw.rectangle([cx, top, cx + cw - 1, top + self.cell_h // 2 - 1], fill=fg)
                    elif glyph == '▄':
                        draw.rectangle([cx, top + self.cell_h // 2, cx + cw - 1, top + self.cell_h - 1], fill=fg)
                    elif glyph in '┃│':
                        w = 3 if glyph == '┃' else 1
                        draw.rectangle([cx + cw // 2 - w // 2, top, cx + cw // 2 - w // 2 + w - 1, top + self.cell_h - 1], fill=fg)
                    elif glyph == '╹':
                        draw.rectangle([cx + cw // 2 - 1, top, cx + cw // 2 + 1, top + self.cell_h // 2 - 1], fill=fg)
                    elif glyph in '─━':
                        w = 3 if glyph == '━' else 1
                        draw.rectangle([cx, top + self.cell_h // 2 - w // 2, cx + cw - 1, top + self.cell_h // 2 - w // 2 + w - 1], fill=fg)
                    elif 0x2800 <= ord(glyph[0]) <= 0x28FF:
                        # Braille spinner frames: the monospace font has no Braille, so draw the dots.
                        bits, radius = ord(glyph[0]) - 0x2800, max(1.4, cw / 9)
                        for bit, (col, row) in enumerate([(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3)]):
                            if bits >> bit & 1:
                                px, py = cx + cw * (0.3 + 0.4 * col), top + self.cell_h * (0.26 + 0.16 * row)
                                draw.ellipse([px - radius, py - radius, px + radius, py + radius], fill=fg)
                    elif glyph in '■⬝▪▫□':
                        half = cw * (0.36 if glyph in '■□' else 0.16)
                        mx, my = cx + cw / 2, top + self.cell_h / 2
                        draw.rectangle([mx - half, my - half, mx + half, my + half],
                                       fill=None if glyph in '□▫' else fg, outline=fg)
                    elif not self.has_glyph(glyph):
                        draw.text((cx, top + 1), glyph, font=self.fallback, fill=fg)
                    else:
                        draw.text((cx, top + 1), glyph, font=font, fill=fg)
                x = end
        return image


if __name__ == '__main__':
    import sys
    columns, rows, events = load(sys.argv[1])
    terminal = Terminal(columns, rows)
    for _, text in events:
        terminal.feed(text)
    terminal.image().save(sys.argv[2])
    print(terminal.width, terminal.height, len(events), events[-1][0])
