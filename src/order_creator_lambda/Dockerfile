FROM python:3.11-slim

WORKDIR /var/task

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/shared ./shared
COPY src/order_creator_lambda/app.py ./app.py

CMD ["python", "-c", "import app; print('OrderCreator Lambda image ready')"]
