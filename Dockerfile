FROM debian:buster
FROM python:3.7-buster

RUN echo 'deb http://deb.debian.org/debian buster main contrib non-free' >> /etc/apt/sources.list && cat /etc/apt/sources.list
RUN apt-get update -qq \
    && apt-get install -y -q --no-install-recommends \
           apt-utils \
           bzip2 \
           ca-certificates \
           curl \
           locales \
           unzip \
           git \
           cmake \
    && apt-get clean

ENV ANTSPATH="/opt/ants" \
    PATH="/opt/ants:$PATH" \
    CMAKE_INSTALL_PREFIX=$ANTSPATH

RUN echo "Cloning ANTs repo..." \
    && mkdir ~/code \
    && cd ~/code \
    && git clone --branch v2.3.1 https://github.com/ANTsX/ANTs.git

RUN echo "Building ANTs..." \
    && mkdir -p ~/bin/antsBuild \
    && cd ~/bin/antsBuild \
    && cmake ~/code/ANTs
RUN cd ~/bin/antsBuild/ \
    && make
RUN cd ~/bin/antsBuild/ANTS-build \
    && make install

RUN apt-get install -y fsl

COPY ./requirements.txt /pytarsier/requirements.txt
WORKDIR /pytarsier
RUN pip install -r requirements.txt --src /usr/local/src
COPY . /pytarsier

ENTRYPOINT ["python", "/pytarsier/vistarsier.py"]
CMD []
