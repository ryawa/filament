from url import URL
from pathlib import Path

import tkinter

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
        self.text = lex(body)
        self.layout(self.text)
        self.draw()

    def layout(self, text):
        self.display_list = []
        cursor_x, cursor_y = self.HSTEP, self.VSTEP
        for c in text:
            if c == "\n":
                cursor_x = self.HSTEP
                cursor_y += self.VSTEP
                continue
            self.display_list.append((cursor_x, cursor_y, c))
            cursor_x += self.HSTEP
            if cursor_x >= self.WIDTH - self.HSTEP:
                cursor_x = self.HSTEP
                cursor_y += self.VSTEP
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
        for x, y, c in self.display_list:
            if y > self.scroll + self.HEIGHT: continue
            if y + self.VSTEP < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=c)
    
    def scroll_page(self, delta):
        self.scroll -= delta
        self.scroll = max(0, min(self.max_y - self.HEIGHT, self.scroll))
        self.draw()

    def resize(self, e):
        self.WIDTH = e.width
        self.HEIGHT = e.height
        self.layout(self.text)
        self.draw()

if __name__ == "__main__":
    import sys

    b = Browser()
    try:
        if len(sys.argv) == 2:
            b.load(sys.argv[1])
        else:
            test_page = Path.cwd() / "test.html"
            b.load(f"file:///{test_page}")
        tkinter.mainloop()
    finally:
        URL.close_sockets()
