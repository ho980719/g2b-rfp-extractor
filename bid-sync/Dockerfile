FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libreoffice \
    default-jre \
    curl \
    fonts-nanum \
    fonts-nanum-extra \
    && apt-get clean \
    && fc-cache -fv

RUN curl -L -o /tmp/H2Orestart.oxt \
    https://github.com/ebandal/H2Orestart/releases/latest/download/H2Orestart.oxt
RUN unopkg add --shared /tmp/H2Orestart.oxt

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
