FROM mitmproxy/mitmproxy:latest

LABEL org.opencontainers.image.title="mitmproxy-anycache"
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.source=https://github.com/investigativedata/mitmproxy-anycache

RUN apt update
RUN apt install git -y
RUN apt clean

COPY requirements.txt /home/mitmproxy/requirements_anystore.txt
RUN pip install --no-cache-dir -r /home/mitmproxy/requirements_anystore.txt

# FIMXE
RUN pip install --no-cache-dir fakeredis

COPY anycache.py /home/mitmproxy/anycache.py

ENV ANYSTORE_DEFAULT_TTL=86400
ENV REDIS_DEBUG=0

ENTRYPOINT ["mitmdump", "-s /home/mitmproxy/anycache.py"]
