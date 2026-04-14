# 빌드
```bash
  docker build -t bid-sync .
 ```

# 실행
```bash
    docker run -d \
        --name bid-sync \
        -p 8000:8000 \
        --env-file .env \
        bid-sync
```