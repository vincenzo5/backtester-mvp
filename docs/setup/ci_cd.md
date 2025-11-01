# CI/CD Overview

## Workflow Summary

GitHub Actions workflow: `.github/workflows/deploy.yml`

- test (Ubuntu): unit, integration, system, e2e (non-data)
- build (Ubuntu): build/push Docker image to GHCR
- deploy (Self-hosted Windows): pull latest and `docker-compose up -d scheduler`

## Self-Hosted Runner

Windows machine (`ibuypower-windows`). Setup steps are in `docs/deployment-setup.md`:
- Install Docker Desktop
- Install/configure GitHub runner as a service
- Set PowerShell execution policy

## Images

- Pushed to `ghcr.io/<owner>/backtester-mvp:latest` and SHA-tagged

## Manual Triggers

- Workflow supports `workflow_dispatch` for manual runs

## Deployment Location

- Runner operates in `C:\Users\vfnoc\Documents\backtester\deployment`
- Uses `deployment/docker-compose.yml`

## Useful Commands

On the self-hosted machine (PowerShell):

```powershell
cd C:\Users\vfnoc\Documents\backtester\deployment
docker-compose pull
docker-compose up -d scheduler
docker-compose ps
```

