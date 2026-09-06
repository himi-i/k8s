FROM python:3.11-slim

# Gatekeeper의 runAsNonRoot 정책을 통과하려면 이미지 자체도 non-root 사용자로 빌드/실행해야 함
RUN useradd -m -u 1000 appuser
WORKDIR /app

COPY requirements.txt .

# torch는 CPU 전용 wheel을 별도 index에서 설치 (이미지 용량 절감)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN chown -R appuser:appuser /home/appuser /app

USER appuser

# 모델은Longhorn PV(model-cache-pvc)를 HF_HOME으로 마운트해서 씀.
# - model-downloader Job이 최초 1회 PV에 다운로드
# - inference-service 파드는 initContainer로 준비될 때까지 대기 후 읽기 전용으로 마운트
# (이 이미지는 model-downloader Job에서도 그대로 재사용되므로 transformers/torch는 유지)

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
