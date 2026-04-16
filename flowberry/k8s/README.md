# Flowberry Kubernetes (Minikube)

This folder provides a minimal Kubernetes setup to satisfy the Kubernetes requirement.
It includes Deployments, Services, ConfigMap, Secret, Ingress, and HPA.

## Assumptions

- You have Minikube installed and running.
- You have built local Docker images: `flowberry-api`, `flowberry-frontend`, `flowberry-worker-email`, `flowberry-worker-calendar`.
- You want a simple in-cluster Postgres and RabbitMQ (ephemeral storage for Postgres).

## Apply manifests

```bash
kubectl apply -f k8s/
```

## Update secrets

Edit [02-secret.yaml](../k8s/02-secret.yaml) before applying:

- `JWT_SECRET`
- `FERNET_KEY`
- `GEMINI_API_KEY`

## Ingress

The Ingress assumes `flowberry.local`. Add a hosts entry:

```
127.0.0.1 flowberry.local
```

Then enable the ingress addon in Minikube:

```bash
minikube addons enable ingress
```

## Notes

- Postgres uses `emptyDir` (non-persistent).
- For production, replace with a PersistentVolumeClaim and proper storage class.
