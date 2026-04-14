# 빌드
docker build -t bid-sync .

# 실행
docker run -d \
    --name bid-sync \
    -p 8001:8000 \
    --env-file .env \
    bid-sync