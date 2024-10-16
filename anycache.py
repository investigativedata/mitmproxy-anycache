"""
https://docs.mitmproxy.org/stable/addons-overview/

https://github.com/investigativedata/anystore/

Use mitmproxy as a cache with various backends and ttl

Inspired by: https://github.com/kitsuyui/python-mitmcache/
"""

from functools import cached_property
from io import BytesIO
import logging
from urllib.parse import urlparse

from anystore.exceptions import DoesNotExist
from anystore.store import BaseStore, get_store
from anystore.util import make_data_checksum

from mitmproxy import ctx
from mitmproxy.addonmanager import Loader
from mitmproxy.http import HTTPFlow
from mitmproxy.io import FlowReader, FlowWriter
from pantomime import normalize_mimetype
from pantomime.types import DEFAULT, JSON


log = logging.getLogger(__name__)


def serialize(flow: HTTPFlow) -> bytes:
    with BytesIO() as f:
        writer = FlowWriter(f)
        writer.add(flow)
        return f.getvalue()


def deserialize(value: bytes) -> HTTPFlow | None:
    with BytesIO(value) as f:
        reader = FlowReader(f)
        for flow in reader.stream():
            return flow


class Cache:
    store: BaseStore

    @cached_property
    def cache_key_name(self) -> str:
        return str(ctx.options.cache_key_name).lower()  # http2

    @cached_property
    def cache_hit_key_name(self) -> str:
        return str(ctx.options.cache_hit_key_name).lower()  # http2

    @cached_property
    def cache_mimetypes(self) -> set[str]:
        mimes = set()
        for opt in str(ctx.options.cache_mimetypes).lower().split(","):
            if opt in GROUPS:
                mimes.update(GROUPS[opt])
            else:
                mtype = normalize_mimetype(opt)
                if mtype != DEFAULT:
                    mimes.add(mtype)
        return mimes

    def load(self, loader: Loader) -> None:
        loader.add_option(
            name="cache_key_name",
            typespec=str,
            default="x-anycache-key",
            help="Header key used to determine the cache key.",
        )
        loader.add_option(
            name="cache_hit_key_name",
            typespec=str,
            default="x-anycache",
            help="Header key used to determine if request was cached.",
        )
        loader.add_option(
            name="cache_mimetypes",
            typespec=str,
            default="web,images,assets,json",
            help="Mimetypes or groups that should be cached",
        )
        self.store = get_store(
            serialization_func=serialize, deserialization_func=deserialize
        )
        log.info(f"Cache: `{self.store.uri}`")
        log.info(f"Cache mimetypes: `{','.join(self.cache_mimetypes)}`")
        log.info(f"Header key: `{self.cache_key_name}`")
        log.info(f"Header hit key: `{self.cache_hit_key_name}`")

    def request(self, flow: HTTPFlow) -> None:
        """request

        1. If the request has a cache key and already exists in the cache,
          set the response to the cached response.
        2. If the request has a cache key but doesn't exist in the cache,
          request to the origin server without cache key header.
        3. If the request doesn't have a cache key,
          generate a cache key and set it to the response headers.
        """
        # Get cache key or create it from request headers
        key = self.get_cache_key_from_flow(flow)
        if key is not None:
            flow.metadata[self.cache_key_name] = key

            try:
                res: HTTPFlow = self.store.get(key)
                assert res.response is not None
                log.info(f"Cache hit: {key}")
                flow.response = res.response
                flow.response.headers[self.cache_key_name] = key
                flow.response.headers[self.cache_hit_key_name] = "HIT"
                flow.metadata["cache-hit"] = True
                return
            except (DoesNotExist, AssertionError):
                pass
        flow.request.headers.pop(self.cache_key_name, None)
        flow.metadata["cache-hit"] = False

    def response(self, flow: HTTPFlow) -> None:
        """response

        1. If the response was a cache hit, do nothing
        2. If the response wasn't a cache hit, store it (if we get a key and
           mimetype matches)
        """

        # Check if the response has a cache key
        key = self.get_cache_key_from_flow(flow)
        if key and not flow.metadata.get("cache-hit", False):
            mtype = flow.response.headers.get("content-type", "")
            mtype = normalize_mimetype(mtype.split(";")[0].lower())
            if mtype in self.cache_mimetypes:
                self.store.put(key, flow)

    def get_cache_key_from_flow(self, flow: HTTPFlow) -> str | None:
        if not self.should_cache(flow):
            return
        # 1. Try from flow metadata
        cache_key = flow.metadata.get(self.cache_key_name)
        if cache_key:
            return str(cache_key)
        # 2. Try from request headers
        cache_key = flow.request.headers.get(self.cache_key_name)
        if cache_key:
            return str(cache_key)
        # 3. Try from response headers
        if flow.response is not None:
            cache_key = flow.response.headers.get(self.cache_key_name)
            if cache_key:
                return str(cache_key)
        # 4. Create from url
        host = urlparse(flow.request.url).netloc
        prefix = f"{flow.request.scheme}#{flow.request.method}"
        return f"{host}/{prefix}/{make_data_checksum(flow.request.url)}"

    def should_cache(self, flow: HTTPFlow) -> bool:
        return flow.request.method.upper() in ("GET", "OPTIONS", "HEAD")


addons = [Cache()]

# MIME GROUPS
# https://github.com/alephdata/memorious/blob/main/memorious/logic/mime.py
WEB = [
    "text/html",
    "text/plain",
    "text/xml",
    "application/xml",
]

IMAGES = [
    "image/jpeg",
    "image/bmp",
    "image/png",
    "image/tiff",
    "image/gif",
    "application/postscript",
    "image/vnd.dxf",
    "image/svg+xml",
    "image/x-pict",
    "image/x-ms-bmp",
]

MEDIA = [
    "audio/mpeg",
    "video/x-flv",
    "video/mp4",
    "video/mp2t",
    "video/3gpp",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-ms-wmv",
]

DOCUMENTS = [
    "application/vnd.ms-excel",
    "application/msword",
    "application/pdf",
    ".pdf",  # seen in the wild (TM)
    "application/vnd.ms-powerpoint",
    "text/richtext",
    "application/vnd.oasis.opendocument.text",
    "application/rtf",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/x-rtf",
    "application/vnd.oasis.opendocument.graphics",
    "application/vnd.oasis.opendocument.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # noqa
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # noqa
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # noqa
]

ARCHIVES = [
    "application/zip",
    "application/x-rar-compressed",
    "application/x-tar",
    "application/x-gzip",
    "application/x-7z-compressed",
]

ASSETS = [
    "text/css",
    "application/javascript",
    "application/json",
    "image/x-icon",
    "application/rss+xml",
    "application/atom+xml",
    "application/opensearchdescription+xml",
]

GROUPS = {
    "web": WEB,
    "images": IMAGES,
    "media": MEDIA,
    "documents": DOCUMENTS,
    "archives": ARCHIVES,
    "assets": ASSETS,
    "json": [JSON],
}
