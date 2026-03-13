FROM python:3.11-slim

WORKDIR /var/task

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/shared ./shared
COPY src/order_processor_lambda/app.py ./app.py

CMD ["python", "-c", "import app; print('OrderProcessor Lambda image ready')"]
