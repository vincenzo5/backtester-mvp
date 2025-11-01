# Deployment Setup Guide

This guide walks you through the one-time manual setup required to enable automated deployments from GitHub Actions to your Windows 11 iBuyPower production machine using a self-hosted runner.

## Prerequisites

- Windows 11 machine (iBuyPower)
- Docker Desktop installed on iBuyPower
- GitHub repository access
- Administrator access on Windows machine

## Step 1: Install Docker Desktop (iBuyPower Machine)

If Docker Desktop is **not already installed**:

1. Download Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Install Docker Desktop
3. Start Docker Desktop (check system tray)
4. Verify it's running

**Test Docker:**
```powershell
docker --version
docker-compose --version
```

Both commands should show version numbers.

## Step 2: Clone Repository (iBuyPower Machine)

On your iBuyPower machine:

```powershell
# Navigate to Documents folder
cd C:\Users\vfnoc\Documents

# Clone the repository
git clone https://github.com/vincenzo5/backtester-mvp.git backtester
```

If the repository already exists at this location, you can skip this step or pull the latest changes:
```powershell
cd C:\Users\vfnoc\Documents\backtester
git pull
```

## Step 3: Setup Self-Hosted GitHub Runner

### 3a. Create Runner on GitHub

1. Navigate to repository settings:
   - URL: `https://github.com/vincenzo5/backtester-mvp/settings/actions/runners`
2. Click **"New self-hosted runner"**
3. Select **"Windows"** as the operating system
4. GitHub will display setup instructions - **keep this page open**

### 3b. Install Runner on iBuyPower Machine

**Run these commands in PowerShell on iBuyPower:**

```powershell
# Create a folder for the runner
mkdir C:\actions-runner
cd C:\actions-runner

# Download the runner (GitHub provides the exact download URL)
# Replace the URL below with the one from GitHub's instructions
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-win-x64-2.311.0.zip -OutFile actions-runner-win-x64-2.311.0.zip

# Extract the runner
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory("$PWD/actions-runner-win-x64-2.311.0.zip", "$PWD")

# Configure the runner (use the token from GitHub's page)
./config.cmd --url https://github.com/vincenzo5/backtester-mvp --token <YOUR_TOKEN>

# When prompted:
# - Runner name: "ibuypower-windows"
# - Runner group: "Default" (press Enter)
# - Labels: leave default (press Enter)
# - Work folder: leave default (press Enter)
```

### 3c. Install Runner as Windows Service

```powershell
# Run PowerShell as Administrator for this step
# Install the runner as a service
./svc.cmd install

# Start the service
./svc.cmd start

# Check status
./svc.cmd status
```

### 3d. Verify Runner is Online

1. Go back to GitHub: `https://github.com/vincenzo5/backtester-mvp/settings/actions/runners`
2. You should see **"ibuypower-windows"** runner with green **"Idle"** status
3. If it shows offline, check service status on Windows and runner logs

## Step 4: Initial Docker Setup Verification

On your iBuyPower machine:

```powershell
# Navigate to the repository
cd C:\Users\vfnoc\Documents\backtester

# Verify Docker is running
docker ps

# Test docker-compose
cd deployment
docker-compose --version
```

If all commands work, you're ready for automated deployments!

## After Setup: Verify Deployment Works

1. **Trigger a deployment:**
   - Push to `main` branch OR
   - Go to Actions tab and manually trigger workflow
   - URL: `https://github.com/vincenzo5/backtester-mvp/actions`

2. **Watch GitHub Actions:**
   - You should see a workflow run called "Build, Test, and Deploy"
   - Build job runs on `ubuntu-latest` (cloud)
   - Deploy job runs on `self-hosted` (your iBuyPower)
   - Click on it to watch progress

3. **Verify deployment on iBuyPower:**
   ```powershell
   cd C:\Users\vfnoc\Documents\backtester\deployment
   docker-compose ps
   ```
   
   You should see the `data-scheduler` container running.

## Troubleshooting

### GitHub Runner Offline

**Problem:** Runner shows as "Offline" in GitHub settings.

**Solutions:**
1. **Check runner service status:**
   ```powershell
   cd C:\actions-runner
   ./svc.cmd status
   ```

2. **If service is stopped, start it:**
   ```powershell
   ./svc.cmd start
   ```

3. **Check runner logs:**
   ```powershell
   Get-Content -Path _diag\Runner_*.log -Tail 50
   ```

4. **Restart runner service:**
   ```powershell
   ./svc.cmd stop
   ./svc.cmd start
   ```

5. **If issues persist, reinstall service:**
   ```powershell
   ./svc.cmd uninstall
   ./svc.cmd install
   ./svc.cmd start
   ```

### Docker Commands Fail on Windows

**Problem:** `docker` or `docker-compose` commands don't work.

**Solutions:**
1. **Ensure Docker Desktop is running:**
   - Check system tray for Docker icon
   - Open Docker Desktop if paused

2. **Restart Docker Desktop:**
   - Right-click Docker tray icon → Restart

3. **Check WSL 2 integration** (if using WSL):
   - Docker Desktop → Settings → Resources → WSL Integration
   - Enable integration for your distro

### GitHub Actions Deployment Fails

**Problem:** Deploy job fails in GitHub Actions.

**Solutions:**
1. **Check Actions logs:**
   - Go to Actions tab → Click failed workflow → Check error messages
   - Look at deploy job logs specifically

2. **Verify runner is online:**
   - Go to Settings > Actions > Runners
   - Ensure "ibuypower-windows" shows green "Idle" status

3. **Check Docker on iBuyPower:**
   - Verify Docker Desktop is running
   - Test `docker ps` and `docker-compose` commands work

4. **Verify repository path:**
   - Ensure repository exists at `C:\Users\vfnoc\Documents\backtester`
   - Check deploy job logs for path-related errors

5. **Check runner can access Docker:**
   ```powershell
   cd C:\actions-runner
   docker ps
   docker-compose --version
   ```
   All commands should work when run manually on the machine

### Container Won't Start

**Problem:** Scheduler container fails to start after deployment.

**Solutions:**
1. **Check container logs:**
   ```powershell
   docker-compose logs scheduler
   ```

2. **Verify volumes:**
   - Ensure `data/`, `config/`, and `artifacts/` directories exist
   - Check permissions on these directories

3. **Check image pull:**
   ```powershell
   docker pull ghcr.io/vincenzo5/backtester-mvp:latest
   ```
   Should pull successfully

## Next Steps

Once deployment is working:

- **Automatic deployments:** Every push to `main` branch will automatically deploy
- **Manual trigger:** You can also manually trigger from GitHub Actions UI
- **Monitor deployments:** Check the Actions tab to see deployment history
- **Container management:** Use `docker-compose logs` and `docker-compose ps` to monitor

## Support

If you encounter issues not covered here:
1. Check GitHub Actions logs for detailed error messages
2. Review Docker logs: `docker-compose logs scheduler`
3. Verify all setup steps were completed correctly
4. Ensure Docker Desktop is running and up-to-date

