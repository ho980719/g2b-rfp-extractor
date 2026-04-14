# 빌드
```bash 
    docker build -t hwp-converter .
```

# 실행
```bash
    docker run -d -p 8000:8000 -v /data001/convert:/tmp --name hwp-converter hwp-converter
```