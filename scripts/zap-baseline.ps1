# OWASP ZAP baseline against a local gateway. Laptop only — not CI.
# The gateway must already be listening. Default target matches the spec.
param(
    [string]$Target = "http://host.docker.internal:8000"
)

docker run --rm -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py -t $Target
