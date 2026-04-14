FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libreoffice \
    default-jre \
    curl \
    # 한글 폰트 추가
    fonts-nanum \
    fonts-nanum-extra \
    && apt-get clean \
    && fc-cache -fv

# H2Orestart 다운로드
RUN curl -L -o /tmp/H2Orestart.oxt \
    https://github.com/ebandal/H2Orestart/releases/latest/download/H2Orestart.oxt

# hwpx 파일 지원 라이브러리 설치
RUN unopkg add --shared /tmp/H2Orestart.oxt

RUN pip install fastapi uvicorn python-multipart httpx

WORKDIR /app
COPY main.py .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]