from dataclasses import dataclass
from url import URL
from pathlib import Path

import tkinter
import tkinter.font

@dataclass
class Text:
    text: str

class Tag:
    tag: str

entities = {
    "lt": "<",
    "gt": ">",
}

def lex(body):
    out = []

    buffer = ""
    entity = ""
    in_tag = False
    in_entity = False

    for c in body:
        if c == "<":
            in_tag = True
            if buffer: out.append(Text(buffer))
            buffer = ""
        elif c == ">":
            in_tag = False
            if buffer: out.append(Tag(buffer))
            buffer = ""
        elif c == "&" and not in_tag:
            in_entity = True
            entity = ""
        elif c == ";" and in_entity:
            in_entity = False
            buffer += entities.get(entity, f"&{entity};")
        elif not in_tag and not in_entity:
            buffer += c
        elif in_entity:
            entity += c

    if not in_tag and buffer:
        out.append(Text(buffer))

    return out

class Browser:
    WIDTH, HEIGHT = 800, 600
    HSTEP, VSTEP = 13, 18
    SCROLL_STEP = 100
    SCROLLBAR_WIDTH = 10

    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=self.WIDTH,
            height=self.HEIGHT,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        self.window.bind("<Configure>", self.resize)
        self.scroll = 0
        self.window.bind("j", lambda e: self.scroll_page(-self.SCROLL_STEP))
        self.window.bind("k", lambda e: self.scroll_page(self.SCROLL_STEP))
        self.window.bind("<MouseWheel>", lambda e: self.scroll_page(e.delta))

    def load(self, url):
        try:
            url = URL(url)
        except Exception as e:
            url = URL("about:blank")
        body = url.request()
        self.tokens = lex(body)
        self.layout()
        self.draw()

    def layout(self):
        self.display_list = []
        cursor_x, cursor_y = self.HSTEP, self.VSTEP

        weight = "normal"
        style = "roman"
        for tok in self.tokens:
            if isinstance(tok, Text):
                for word in tok.text.split():
                    font = tkinter.font.Font(
                        size=16,
                        weight=weight,
                        slant=style
                    )
                    w = font.measure(word)
                    if cursor_x + w > self.WIDTH - self.HSTEP:
                        cursor_y += font.metrics("linespace") * 1.25
                        cursor_x = self.HSTEP

                    self.display_list.append((cursor_x, cursor_y, word, font))
                    cursor_x += w + font.measure(" ")
            elif tok.tag == "i":
                style = "italic"
            elif tok.tag == "/i":
                style = "roman"
            elif tok.tag == "b":
                weight = "bold"
            elif tok.tag == "/b":
                weight = "normal"

        self.max_y = self.VSTEP
        if self.display_list:
            self.max_y += self.display_list[-1][1]

    def draw(self):
        self.canvas.delete("all")
        scale = self.HEIGHT / self.max_y
        if scale < 1:
            self.canvas.create_rectangle(
                self.WIDTH - self.SCROLLBAR_WIDTH,
                self.scroll * scale,
                self.WIDTH,
                (self.scroll + self.HEIGHT) * scale,
                fill="blue",
                outline=""
            )
        for x, y, w, f in self.display_list:
            if y > self.scroll + self.HEIGHT: continue
            if y + self.VSTEP < self.scroll: continue
            self.canvas.create_text(
                x,
                y - self.scroll,
                text=w,
                anchor="nw",
                font=f,
            )
    
    def scroll_page(self, delta):
        self.scroll -= delta
        self.scroll = max(0, min(self.max_y - self.HEIGHT, self.scroll))
        self.draw()

    def resize(self, e):
        self.WIDTH = e.width
        self.HEIGHT = e.height
        self.layout()
        self.draw()

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        type=str,
        help="the URL to display",
        nargs="?",
        default=f"file:///{Path.cwd() / 'test.html'}",
    )
    args = parser.parse_args()

    b = Browser()
    try:
        b.load(args.url)
        tkinter.mainloop()
    finally:
        URL.close_sockets()
