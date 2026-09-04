# AI 추론 카오스 랩 (Phase 1: 서비스 배포)

GPU 없이도 GPU 추론 워크로드의 특성(콜드스타트, 큐잉, 메모리 풋프린트, 지연 민감성)을
재현하는 테스트 서비스입니다. 이후 Chaos Mesh 실험 대상이 됩니다.

## 1. 이미지 빌드 & 푸시 (로컬 머신 또는 master-01에서)

```bash
cd app
docker build -t <DOCKERHUB_USERNAME>/ai-inference:v1 .
docker login
docker push <DOCKERHUB_USERNAME>/ai-inference:v1
```

`k8s/01-deployment.yaml`의 `image:` 필드를 실제 이미지로 교체하세요.

## 2. 매니페스트 배포

ArgoCD를 이미 운영 중이므로, `k8s/` 디렉토리를 git repo에 올리고
`08-argocd-application.yaml`의 `repoURL`을 교체한 뒤 아래처럼 적용하는 걸 권장합니다.

```bash
kubectl apply -f k8s/08-argocd-application.yaml
```

수동으로 바로 확인하고 싶다면:

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/
```

## 3. 사전 체크리스트

- [ ] Docker Hub 이미지 push 완료, `01-deployment.yaml`의 image 교체
- [ ] `05-ingress.yaml`의 도메인을 실제 보유 도메인으로 교체, DNS A레코드를 fw-01 외부 IP로 지정
- [ ] `06-servicemonitor.yaml`의 `release:` 라벨이 실제 kube-prometheus-stack 릴리스명과 일치하는지 확인
      (`helm list -n monitoring` 으로 확인)
- [ ] `07-networkpolicy.yaml`의 네임스페이스 라벨이 실제 클러스터와 일치하는지 확인
      (`kubectl get ns --show-labels`)
- [ ] Gatekeeper 정책(runAsNonRoot, no hostPath 등)을 이 Deployment가 통과하는지 확인
      (`kubectl apply` 시 위반되면 admission 단계에서 즉시 거부됨 — 이 자체도 정책이 실제로
      작동한다는 증거로 스크린샷 남기기 좋음)

## 4. 동작 확인

```bash
kubectl -n ai-inference get pods -w
kubectl -n ai-inference port-forward svc/inference-service 8000:80

curl http://localhost:8000/readyz
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "I love Kubernetes chaos engineering"}'

curl http://localhost:8000/metrics | head -30
```

## 5. Grafana에서 확인할 지표

- `model_load_time_seconds` : 콜드스타트(모델 로딩) 시간
- `inference_latency_seconds_bucket` : p50/p95/p99 지연
- `inference_queue_depth` : 현재 큐 깊이
- `inference_requests_total{status=...}` : success / queue_full / model_not_ready / error 비율

배포와 관측이 안정적으로 확인되면, 다음 단계로 Chaos Mesh 실험 YAML을 붙여
pod-kill / network-delay / memory-stress / node-down 시나리오를 실행합니다.
