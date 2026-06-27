# CadQuery needs OpenCascade, so we build on the conda-forge base image.
FROM continuumio/miniconda3:24.5.0-0

WORKDIR /app
COPY environment.yml .
RUN conda env create -f environment.yml && conda clean -afy

# Make the env's tools the default
SHELL ["conda", "run", "-n", "lee3d", "/bin/bash", "-c"]
ENV PATH=/opt/conda/envs/lee3d/bin:$PATH

COPY app ./app
EXPOSE 8000
ENV LEE3D_DATA_DIR=/data
VOLUME ["/data"]

CMD ["conda", "run", "--no-capture-output", "-n", "lee3d", \
     "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
