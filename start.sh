#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

IMAGE_LOCAL="intelligent-sharepoint-parsing_worker:latest"
IMAGE_REGISTRY="localhost:5000/intelligent-sharepoint-parsing_worker:version1.0"
DEPLOYMENT="k8s/deployment.yaml"
STORAGE="k8s/storage.yaml"
SECRET_NAME="parsing-worker-env"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

step() {
  printf '\n==> %s\n' "$*"
}

compose_container_id() {
  docker compose ps -q "$1"
}

step "Checking prerequisites"

for command_name in docker kubectl; do
  command -v "$command_name" >/dev/null 2>&1 \
    || fail "$command_name is not installed"
done

docker info >/dev/null 2>&1 \
  || fail "Docker Desktop is not running"

docker compose version >/dev/null 2>&1 \
  || fail "Docker Compose is unavailable"

kubectl cluster-info >/dev/null 2>&1 \
  || fail "Kubernetes is unavailable"

[[ "$(kubectl config current-context)" == "docker-desktop" ]] \
  || fail "Kubernetes context must be docker-desktop"

for file in .env "$DEPLOYMENT" "$STORAGE"; do
  [[ -f "$file" ]] || fail "Missing $file"
done

docker network inspect kind >/dev/null 2>&1 \
  || fail "Docker Desktop kind network not found"

mkdir -p data/bronze data/silver

step "Starting registry and NFS"

docker compose up -d registry nfs

step "Checking NFS container"

nfs_ready=0

for _ in $(seq 1 30); do
  nfs_id="$(compose_container_id nfs)"

  if [[ -n "$nfs_id" ]] &&
     [[ "$(docker inspect -f '{{.State.Running}}' "$nfs_id" 2>/dev/null || true)" == "true" ]]; then
    nfs_ready=1
    break
  fi

  sleep 2
done

if [[ "$nfs_ready" != 1 ]]; then
  docker compose logs --tail=100 nfs
  fail "NFS container is not running"
fi

step "Building and pushing parsing worker"

docker compose build parsing_worker

docker image inspect "$IMAGE_LOCAL" >/dev/null 2>&1 \
  || fail "Worker image not found"

docker tag "$IMAGE_LOCAL" "$IMAGE_REGISTRY"
docker push "$IMAGE_REGISTRY"

step "Starting Docker Compose services"

docker compose up -d --build \
  db \
  admin \
  redis \
  doc_manager_api \
  parsing_api \
  web_app

step "Waiting for Redis"

redis_id="$(compose_container_id redis)"

[[ -n "$redis_id" ]] \
  || fail "Redis container not found"

redis_ready=0

for _ in $(seq 1 60); do
  if [[ "$(docker inspect -f '{{.State.Health.Status}}' "$redis_id" 2>/dev/null || true)" == "healthy" ]]; then
    redis_ready=1
    break
  fi

  sleep 2
done

[[ "$redis_ready" == 1 ]] \
  || fail "Redis did not become healthy"

step "Creating/updating Kubernetes Secret"

kubectl create secret generic "$SECRET_NAME" \
  --from-env-file=.env \
  --dry-run=client \
  -o yaml | kubectl apply -f -

step "Configuring shared storage"

kubectl apply -f "$STORAGE"

kubectl wait \
  --for=jsonpath='{.status.phase}'=Bound \
  pvc/parsing-worker-data \
  --timeout=60s

step "Deploying parsing workers"

kubectl apply -f "$DEPLOYMENT"

# Refresh the pods only when the image or Secret changes.
# The image tag is fixed, so compare its image ID with the
# last successfully deployed image.
image_id="$(docker image inspect "$IMAGE_REGISTRY" --format '{{.Id}}')"

previous_image_id="$(
  kubectl get deployment parsing-worker \
    -o jsonpath='{.metadata.annotations.docspace\.local/image-id}' \
    2>/dev/null || true
)"

if [[ "$image_id" != "$previous_image_id" ]]; then
  kubectl annotate deployment parsing-worker \
    "docspace.local/image-id=$image_id" \
    --overwrite
fi

# A change to the Secret also needs to reach the running pods.
# This checksum is stored on the pod template to trigger a rollout.
secret_checksum="$(
  kubectl get secret "$SECRET_NAME" -o jsonpath='{.data}' |
    sha256sum |
    awk '{print $1}'
)"

kubectl patch deployment parsing-worker --type=merge \
  -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"docspace.local/secret-checksum\":\"$secret_checksum\",\"docspace.local/image-id\":\"$image_id\"}}}}}"

if ! kubectl rollout status deployment/parsing-worker --timeout=10m; then
  kubectl get pods -l app=parsing-worker -o wide
  kubectl describe pods -l app=parsing-worker
  fail "Worker rollout failed; check NFS mount events above"
fi

step "Starting document manager worker"

docker compose up -d --build doc_manager_worker

step "Checking status"

docker compose ps
kubectl get pods -l app=parsing-worker -o wide

printf '\nDocspace started successfully.\n'