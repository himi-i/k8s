FROM python:3.11-slim

# Gatekeeper의 runAsNonRoot 정책을 통과하려면 이미지 자체도 non-root 사용자로 빌드/실행해야 함
RUN useradd -m -u 1000 appuser
WORKDIR /app

COPY requirements.txt .

# torch는 CPU 전용 wheel을 별도 index에서 설치 (이미지 용량 절감)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENV HF_HOME=/home/appuser/.cache/huggingface
RUN mkdir -p "$HF_HOME" && chown -R appuser:appuser /home/appuser /app

USER appuser

# 모델을 빌드 타임에 미리 다운로드해서 이미지에 굽는다.
# -> 런타임 파드에 NetworkPolicy로 외부 egress를 막아도 정상 동작 (콜드스타트 = 로컬 로딩 시간만 반영)
RUN python -c "from transformers import pipeline; pipeline('sentiment-analysis', model='distilbert-base-uncased-finetuned-sst-2-english')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
