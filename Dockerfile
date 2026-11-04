FROM python:3.12-slim

WORKDIR /app

COPY . .

# Everything the image is worth running. The lint alone needs no extras at
# all — that is its point — but an image exists to serve the API, and the
# API is only interesting with the renderer and the prose tools behind it.
RUN pip install --no-cache-dir "."

EXPOSE 8000

# Serve what the image was built for. A CMD of `--help` would be a container
# that starts, prints and exits — which looks like it works and does nothing.
#
# The MCP server, not bare uvicorn on the API: importing sprezzature_publish.mcp
# is what mounts /mcp on the FastAPI app, so `uvicorn sprezzature_publish.api:app`
# served /v1/... and /health with no /mcp at all. This one process serves both,
# on one port. Override with any of the commands:
#
#   docker run --rm -v "$PWD:/work" IMAGE make-site lint /work/docs
CMD ["sprezzature-publish-mcp", "--host", "0.0.0.0", "--port", "8000"]
