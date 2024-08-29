FROM mitmproxy/mitmproxy:latest

LABEL org.opencontainers.image.title="mitmproxy-anystore"
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.source=https://github.com/investigativedata/mitmproxy-anystore

RUN apt update
RUN apt install git -y
RUN apt clean

COPY requirements.txt /home/mitmproxy/requirements_anystore.txt
RUN pip install --no-cache-dir -r /home/mitmproxy/requirements_anystore.txt
COPY anycache.py /home/mitmproxy/anycache.py

CMD ["mitmdump", "-s /home/mitmproxy/anycache.py"]
