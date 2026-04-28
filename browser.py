import socket
import ssl

class URL:
    sockets = {}

    def __init__(self, url):
        if url.startswith("view-source:"):
            self.view_source = True
            url = url.removeprefix("view-source:")
        else:
            self.view_source = False
        self.scheme, url = url.split(":", 1)
        assert self.scheme in ["http", "https", "file", "data"], "URL scheme unsupported"

        if self.scheme == "http":
            self.port = 80
        elif self.scheme == "https":
            self.port = 443

        if self.scheme == "data":
            url, self.data = url.split(",", 1)
            self.base64 = url.endswith(";base64")
            assert not self.base64
            self.mediatype = url.removesuffix(";base64")
            assert self.mediatype == "text/html"
            return

        assert url.startswith("//"), "Expected host/authority in URL"
        url = url.removeprefix("//")

        if "/" not in url:
            url += "/"
        self.host, url = url.split("/", 1)
        self.path = "/" + url
        if self.scheme == "file":
            assert self.host == "", "Only local files are supported"

        if ":" in self.host:
            self.host, port = self.host.split(":", 1)
            self.port = int(port)

    def request(self, request_headers=None):
        if request_headers is None:
            request_headers = {
                "Connection": "keep-alive",
                "User-Agent": "filament",
            }
        if self.scheme == "data":
            content = self.data
        elif self.scheme == "file":
            with open(self.path, "r") as f:
                content = f.read()
        elif self.scheme in ["http", "https"]:
            if (self.host, self.port) not in self.sockets:
                s = socket.socket(
                        family=socket.AF_INET,
                        type=socket.SOCK_STREAM,
                        proto=socket.IPPROTO_TCP,
                )
                s.connect((self.host, self.port))
                if self.scheme == "https":
                    ctx = ssl.create_default_context()
                    s = ctx.wrap_socket(s, server_hostname=self.host)
                self.sockets[(self.host, self.port)] = s
            else:
                s = self.sockets[(self.host, self.port)]

            request = f"GET {self.path} HTTP/1.1\r\n"
            request += f"Host: {self.host}\r\n"
            for header, value in request_headers.items():
                request += f"{header}: {value}\r\n"
            request += "\r\n"
            s.send(request.encode("utf8"))

            encoding = "utf8"
            response = s.makefile("rb", newline="\r\n")
            statusline = response.readline().decode(encoding)
            version, status, explanation = statusline.split(" ", 2)
            response_headers = {}
            while True:
                line = response.readline().decode(encoding)
                if line == "\r\n":
                    break
                header, value = line.split(":", 1)
                response_headers[header.casefold()] = value.strip()
            assert "transfer-encoding" not in response_headers
            assert "content-encoding" not in response_headers
            content = response.read(
                    int(response_headers["content-length"])
            ).decode(encoding)

        if self.view_source:
            content = content.replace("<", "&lt;")
            content = content.replace(">", "&gt;")
        
        return content

    @classmethod
    def close_sockets(cls):
        for s in cls.sockets.values():
            s.close()
        cls.sockets = {}

entities = {
    "lt": "<",
    "gt": ">",
}

def show(body):
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
            print(entities.get(entity, f"&{entity};"), end="")
            in_entity = False
        elif not in_tag and not in_entity:
            print(c, end="")
        elif in_entity:
            entity += c

def load(url):
    body = url.request()
    show(body)

if __name__ == "__main__":
    import sys

    try:
        if len(sys.argv) == 2:
            load(URL(sys.argv[1]))
        else:
            load(URL("file:///Users/ryan/code/filament/test.html"))
    finally:
        URL.close_sockets()
