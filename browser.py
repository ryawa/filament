from dataclasses import dataclass
from pathlib import Path

import datetime
import gzip
import io
import socket
import ssl

BASE_DIR = Path(__file__).parent.resolve()
CACHE_DIR = BASE_DIR / ".cache/"

@dataclass
class Response:
    raw: str
    status: int
    headers: dict[str, str]
    content: str


class URL:
    sockets = {}

    def __init__(self, url, redirect_count=0):
        self.redirect_count = redirect_count

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
                "Accept-Encoding": "gzip",
                "Connection": "keep-alive",
                "User-Agent": "filament",
            }

        match self.scheme:
            case "data":
                content = self.data
            case "file":
                with open(self.path, "r") as f:
                    content = f.read()
            case "http" | "https":
                cached_path = CACHE_DIR / self.host / self.path.lstrip("/")
                if cached_path.is_file():
                    cached_response = URL._parse_http(
                        io.BytesIO(cached_path.read_bytes())
                    )

                    cache_directives = cached_response.headers["cache-control"].split(", ")
                    max_age = None
                    for directive in cache_directives:
                        if directive.startswith("max-age="):
                            max_age = int(directive.removeprefix("max-age="))
                    assert max_age is not None, "Expected max-age value in the headers of a previously cached response"

                    # TODO: make checking staleness compliant with RFC 9111
                    response_time = cached_path.stat().st_mtime
                    if datetime.datetime.now().timestamp() - response_time > max_age:
                        content = self._request_http(request_headers)
                    else:
                        content = cached_response.content
                else:
                    content = self._request_http(request_headers)

        if self.view_source:
            content = content.replace("<", "&lt;")
            content = content.replace(">", "&gt;")

        return content

    def _request_http(self, request_headers):
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

        response_file = s.makefile("rb", newline="\r\n")
        response = URL._parse_http(response_file)

        # 304 => get from cache, other 3xx => redirect, other => return and
        # optionally cache
        if response.status == 304:
            cached_path = CACHE_DIR / self.host / self.path.lstrip("/")
            cached_response = URL._parse_http(
                io.BytesIO(cached_path.read_bytes())
            )
            return cached_response.content
        elif 300 <= response.status <= 399:
            assert self.redirect_count < 20, "Too many consecutive redirects"
            location = response.headers["location"]
            if location.startswith("/"):
                location = f"{self.scheme}://{self.host}{location}"
            return URL(location, self.redirect_count + 1).request()
        else:
            cache_control = response.headers.get("cache-control", None)
            if (response.status == 200 and cache_control is not None and
                    "max-age" in cache_control and "no-store" not in cache_control):
                cache_path = CACHE_DIR / self.host / self.path.lstrip("/")
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(response.raw)
            return response.content


    @staticmethod
    def _parse_http(response_file):
        encoding = "utf8"

        statusline = response_file.readline().decode(encoding)
        raw = statusline
        version, status, explanation = statusline.split(" ", 2)
        status = int(status)

        headers = {}
        while True:
            line = response_file.readline().decode(encoding)
            raw += line
            if line == "\r\n":
                break
            header, value = line.split(":", 1)
            headers[header.casefold()] = value.strip()

        if headers.get("transfer-encoding") == "chunked":
            content = b""
            while True:
                line = response_file.readline().decode(encoding)
                size = int(line.rstrip("\r\n"), 16)
                content += response_file.read(size)
                newline = response_file.readline().decode(encoding)
                assert newline == "\r\n"
                if size == 0:
                    break
        else:
            content = response_file.read(
                int(headers["content-length"])
            )
        if headers.get("content-encoding") == "gzip":
            content = gzip.decompress(content)
        content = content.decode(encoding)
        raw += content

        return Response(raw, status, headers, content)


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
            test_page = Path.cwd() / "test.html"
            load(URL(f"file:///{test_page}"))
    finally:
        URL.close_sockets()
