# mitmproxy-anycache

Use [mitmproxy](https://mitmproxy.org/) as a local proxy that caches responses via [anystore](https://github.com/investigativedata/anystore)

Inspired by: https://github.com/kitsuyui/python-mitmcache/

## Usage

### Docker

Start proxy server:

    docker run -p 8080:8080 ghcr.io/investigativedata/mitmproxy-anystore

Use it for requests:

    HTTPS_PROXY=http://localhost:8080 curl -k https://example.org

### cli

Clone this repository, then install python requirements:

    pip install -r requirements.txt

Start proxy server:

    mitmdump -s anycache.py

## Cache backend

The cache backend is provided by [anystore](https://github.com/investigativedata/anystore). Refer to the documentation for further details.

Configure the backend via environment variables (docker or cli):

### storage

    # redis
    ANYSTORE_URI=redis://localhost

    # sqlite
    ANYSTORE_URI=sqlite:///tmp/cache.db

    # remote s3
    ANYSTORE_URI=s3://my_bucket/cache/foo

    # local file
    ANYSTORE_URI=./tmp/cache

### ttl

    ANYSTORE_DEFAULT_TTL=3600  # in seconds
