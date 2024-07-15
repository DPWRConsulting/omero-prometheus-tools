FROM continuumio/miniconda3:24.5.0-0 as builder

USER root

COPY . /omero-prometheus-tools/
RUN cd /omero-prometheus-tools/ && \
    /opt/conda/bin/python setup.py sdist bdist_wheel

######################################################################

FROM continuumio/miniconda3:24.5.0-0
RUN /opt/conda/bin/conda create --name penv -c conda-forge python=3.10
RUN /opt/conda/bin/conda install -n penv -y -q -c conda-forge pip omero-py nomkl 
COPY --from=builder /omero-prometheus-tools/dist/*.whl .
RUN /opt/conda/bin/conda run -n penv pip install *.whl
ENTRYPOINT [ "/opt/conda/bin/conda", "run", "-n", "penv", "/opt/conda/envs/penv/bin/omero-prometheus-tools.py" ]
