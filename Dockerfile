FROM python:3.12-slim

WORKDIR /app

COPY . .

# Everything the image is worth running. The lint alone needs no extras at
# all — that is its point — but an image exists to serve the API, and the
# API is only interesting with the renderer and the prose tools behind it.
RUN pip install --no-cache-dir ".[all,api,mcp]"

EXPOSE 8000

# Serve what the image was built for. A CMD of `--help` would be a container
# that starts, prints and exits — which looks like it works and does nothing.
# Override with any of the commands:
#
#   docker run --rm -v "$PWD:/work" IMAGE make-site lint /work/docs
CMD ["uvicorn", "sprezzature_publish.api:app", "--host", "0.0.0.0", "--port", "8000"]
