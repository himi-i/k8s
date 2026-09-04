"""
AI 추론 테스트 서비스 (카오스 엔지니어링 실습용)

실제 GPU가 없는 환경이지만, GPU 추론 서비스의 핵심 특성을 그대로 재현합니다:
  - 콜드스타트: 모델을 메모리에 로딩하는 데 수 초가 걸림 (readiness probe로 노출)
  - 큐잉/배치 민감성: 동시 요청이 많으면 큐가 차서 429를 반환
  - 리소스 풋프린트: 모델이 메모리에 상주 (OOM 카오스 실험 대상)
  - 관측 가능성: Prometheus 메트릭(p50/p95/p99 latency, queue depth, error rate, model load time)
"""

import os
import time
import threading
import queue

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
from transformers import pipeline

MODEL_NAME = os.getenv("MODEL_NAME", "distilbert-base-uncased-finetuned-sst-2-english")
# 데모/실습 목적: 콜드스타트를 인위적으로 늘리고 싶을 때 사용 (예: chaos 실험에서 재시작 영향 비교)
ARTIFICIAL_STARTUP_DELAY = float(os.getenv("STARTUP_DELAY_SECONDS", "0"))
MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", "40"))

app = FastAPI(title="ai-inference-chaos-lab")
app.mount("/metrics", make_asgi_app())

INFERENCE_LATENCY = Histogram(
    "inference_latency_seconds", "모델 추론 소요 시간(초)"
)
QUEUE_DEPTH = Gauge(
    "inference_queue_depth", "현재 대기 중인 요청 수 (근사치)"
)
REQUESTS_TOTAL = Counter(
    "inference_requests_total", "요청 처리 결과별 카운트", ["status"]
)
MODEL_LOAD_SECONDS = Gauge(
    "model_load_time_seconds", "모델 로딩(콜드스타트)에 걸린 시간(초)"
)

model = None
ready = False
in_flight = 0
_lock = threading.Lock()


def load_model() -> None:
    global model, ready
    if ARTIFICIAL_STARTUP_DELAY > 0:
        time.sleep(ARTIFICIAL_STARTUP_DELAY)
    t0 = time.time()
    model = pipeline("sentiment-analysis", model=MODEL_NAME)
    MODEL_LOAD_SECONDS.set(time.time() - t0)
    ready = True


threading.Thread(target=load_model, daemon=True).start()


class PredictRequest(BaseModel):
    text: str


@app.get("/healthz")
def healthz():
    """liveness: 프로세스가 살아있는지만 확인"""
    return {"status": "alive"}


@app.get("/readyz")
def readyz():
    """readiness: 모델 로딩(콜드스타트) 완료 여부를 노출"""
    if not ready:
        raise HTTPException(status_code=503, detail="model is loading")
    return {"status": "ready"}


@app.post("/predict")
def predict(req: PredictRequest):
    global in_flight

    if not ready:
        REQUESTS_TOTAL.labels(status="model_not_ready").inc()
        raise HTTPException(status_code=503, detail="model not ready")

    with _lock:
        if in_flight > MAX_QUEUE_DEPTH:
            REQUESTS_TOTAL.labels(status="queue_full").inc()
            raise HTTPException(status_code=429, detail="queue full, try later")
        in_flight += 1
        QUEUE_DEPTH.set(in_flight)

    try:
        t0 = time.time()
        result = model(req.text)
        INFERENCE_LATENCY.observe(time.time() - t0)
        REQUESTS_TOTAL.labels(status="success").inc()
        return {"input": req.text, "result": result}
    except Exception as e:
        REQUESTS_TOTAL.labels(status="error").inc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        with _lock:
            in_flight -= 1
            QUEUE_DEPTH.set(in_flight)


@app.get("/")
def root():
    return {
        "service": "ai-inference-chaos-lab",
        "ready": ready,
        "model": MODEL_NAME,
    }
