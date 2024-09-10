FROM ubuntu:bionic
COPY nonce_fix.patch /nonce_fix.patch
COPY start-client.py /start-client.py
COPY start-client.sh /start-client.sh
COPY start-server.py /start-server.py
COPY start-server.sh /start-server.sh
RUN apt update \
    && apt-get -y install git python-pip python3-pip build-essential libssl-dev libffi-dev python-dev python3-dev wget systemtap-sdt-dev zlib1g-dev \
    && wget https://www.python.org/ftp/python/3.6.9/Python-3.6.9.tar.xz \
    && tar -xvf Python-3.6.9.tar.xz \
    && rm Python-3.6.9.tar.xz \
    && cd Python-3.6.9 \
    && ./configure --with-dtrace \
    && make \
    && make install \
    && wget https://bootstrap.pypa.io/pip/3.6/get-pip.py \
    && ./python get-pip.py \
    && ./python -m pip install gnureadline \
    && cd / \
    && git clone https://github.com/awwad/tuf.git \
    && cd tuf \
    && /Python-3.6.9/python setup.py install \
    && cd / \
    && git clone https://github.com/uptane/uptane \
    && cd uptane \
    && sed -i '7,8d' dev-requirements.txt \
    && /Python-3.6.9/python -m pip install -r dev-requirements.txt \
    && /Python-3.6.9/python setup.py install \
    && mv /start-client.py /uptane/start-client.py \
    && mv /start-server.py /uptane/demo/start-server.py \
    && /Python-3.6.9/python demo/start_servers.py --image-creation
