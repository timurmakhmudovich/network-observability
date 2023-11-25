FROM python:3.9.10-alpine3.14

ENV PYTHONUNBUFFERED=1

WORKDIR .
COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python", "-u", "ipam-collector.py"]
