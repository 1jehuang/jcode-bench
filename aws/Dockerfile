FROM archlinux:base

RUN pacman -Syu --noconfirm --needed \
      aws-cli \
      base-devel \
      ca-certificates \
      git \
      jq \
      python \
      valgrind \
    && pacman -Scc --noconfirm

COPY jcode /usr/local/bin/jcode
COPY bench.tar.gz /tmp/bench.tar.gz
COPY runner.py /opt/jcode-bench-aws-runner.py

RUN chmod 0755 /usr/local/bin/jcode /opt/jcode-bench-aws-runner.py \
    && mkdir -p /opt/jcode-bench \
    && tar -xzf /tmp/bench.tar.gz -C /opt/jcode-bench \
    && rm /tmp/bench.tar.gz

ENTRYPOINT ["python3", "/opt/jcode-bench-aws-runner.py"]
