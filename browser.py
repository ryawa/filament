from network import URL
from pathlib import Path

import tkinter

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18

entities = {
    "lt": "<",
    "gt": ">",
}

def lex(body):
    text = ""

    in_tag = False
    in_entity = False
    entity = ""

    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif c == "&":
            in_entity = True
            entity = ""
        elif in_entity and c == ";":
            text += entities.get(entity, f"&{entity};")
            in_entity = False
        elif not in_tag and not in_entity:
            text += c
        elif in_entity:
            entity += c

    return text

def layout(text):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP
    for c in text:
        display_list.append((cursor_x, cursor_y, c))
        cursor_x += HSTEP
        if cursor_x > WIDTH - HSTEP:
            cursor_x = HSTEP
            cursor_y += VSTEP
    return display_list

class Browser:
    SCROLL_STEP = 100

    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.canvas.pack()
        self.scroll = 0
        self.window.bind("j", self.scroll_down)

    def load(self, url):
        body = url.request()
        text = lex(body)
        self.display_list = layout(text)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=c)

    def scroll_down(self, e):
        self.scroll += self.SCROLL_STEP
        self.draw()

if __name__ == "__main__":
    import sys

    b = Browser()
    try:
        if len(sys.argv) == 2:
            b.load(URL(sys.argv[1]))
        else:
            test_page = Path.cwd() / "test.html"
            b.load(URL(f"file:///{test_page}"))
        tkinter.mainloop()
    finally:
        URL.close_sockets()
