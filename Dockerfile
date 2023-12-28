# Dockerfile created by Bendall
# If something looks like a weird hack, it is because I don't know better. I'm not a programmer and it works good enough for me.
# 
# Step by step:
#
# 1. If desired, change UID/GID in this Dockerfile (default: 1000)
#
# 2. Create docker image:
# $ docker image build -t salmon .
#
# 3. Alias docker command and replace /path/to with your desired path. (Add to .bashrc or whatever):
# alias salmon='docker run --rm -it -v /path/to/config.py:/salmon/config.py -v /path/to/accounts.json:/salmon/accounts.json -v /path/to/downloads:/downloads -v /path/to/queue:/queue -v /path/to/torrents:/torrents -p 55110:55110/tcp salmon'
#
# 4. In your config file, set
# WEB_BIND = '0.0.0.0'
#
# Done

FROM python:3.7.5-slim-buster

WORKDIR /salmon

COPY ./ /salmon

RUN apt-get update \
    && echo "----- Installing dependencies" \
    && apt-get install -y gcc sox flac mp3val git wget curl vim\
    && echo "----- Installing python requirements" \
    && pip install --trusted-host pypi.python.org -r requirements.txt \
    && echo "----- Initializing salmon" \
    && cp config.py.txt config.py \
    && python run.py migrate \
    && echo "----- Adding salmon user and group and chown" \
    && groupadd -r salmon -g 1000 \
    && useradd --no-log-init -MNr -g 1000 -u 1000 salmon \
    && chown salmon:salmon -R /salmon

USER salmon:salmon

EXPOSE 55110

VOLUME ["/downloads", "/torrents", "/queue"]

ENTRYPOINT ["python", "run.py"]
