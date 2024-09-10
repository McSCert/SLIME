FROM uptane-base
RUN cd uptane \
    && git apply /nonce_fix.patch \
    && /Python-3.6.9/python demo/start_servers.py --image-creation
