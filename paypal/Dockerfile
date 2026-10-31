# RedLine for PayPal's server. The web app is on Vercel; this image is the API.
# Built from the repository root, because the server imports RedLine's own
# GenLayer modules from contracts/ unchanged, and the demo vendor's pages from
# examples/:
#
#   docker build -f paypal/Dockerfile -t redline-paypal .
#   docker run -p 8000:8000 -e REDLINE_OFFLINE=1 redline-paypal

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY paypal/requirements.txt paypal/requirements.txt
RUN pip install -r paypal/requirements.txt
COPY contracts/redline_core.py contracts/redline_text.py contracts/redline_prompts.py contracts/
COPY examples/*.html examples/
COPY paypal/redline_paypal paypal/redline_paypal
RUN useradd --create-home redline && chown -R redline /app
USER redline
WORKDIR /app/paypal
ENV PORT=8000
EXPOSE 8000
# One worker process: its tick runs demo covers' checks; leases in the
# database keep it and the scheduled worker from ever acting on one cover twice.
CMD ["sh", "-c", "exec uvicorn redline_paypal.web:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
