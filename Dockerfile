FROM python:3.12-alpine as builder

RUN apk add --no-cache --virtual .build-deps \
    git

RUN python -m pip install --upgrade --no-cache-dir pip

COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY groq_chat /app/groq_chat
COPY translate /app/translate

COPY *.py /app/

WORKDIR /app


FROM python:3.12-alpine

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

COPY --from=builder /usr/local/bin /usr/local/bin

COPY --from=builder /app/groq_chat /app/groq_chat
COPY --from=builder /app/translate /app/translate
COPY --from=builder /app/*.py /app/

RUN mkdir /app/data

CMD ["python", "main.py"]
