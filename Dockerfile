FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt 
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY groq_chat /app/groq_chat
COPY translate /app/translate

COPY *.py /app/

CMD ["python", "main.py"]