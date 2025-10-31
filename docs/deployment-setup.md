# Deployment Setup Guide

This guide walks you through the one-time manual setup required to enable automated deployments from GitHub Actions to your Windows 11 iBuyPower production machine.

## Prerequisites

- Windows 11 machine (iBuyPower) at IP: `192.168.4.177`
- Docker Desktop installed on iBuyPower
- Mac Studio for development
- GitHub repository access

## Step 1: Enable OpenSSH Server on Windows 11 (iBuyPower Machine)

Run these commands **as Administrator** on your iBuyPower machine:

```powershell
# Open PowerShell as Administrator, then run:

# Install OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# Start SSH service
Start-Service sshd

# Set SSH service to start automatically
Set-Service -Name sshd -StartupType 'Automatic'

# Configure firewall rule
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

**Verify SSH is running:**
```powershell
Get-Service sshd
```
Status should show "Running".

## Step 2: Generate SSH Key Pair (Mac Studio)

On your Mac Studio, run:

```bash
# Generate SSH key pair (ed25519)
ssh-keygen -t ed25519 -f ~/.ssh/backtester_deploy -N ""

# Display the public key (you'll need this in the next step)
cat ~/.ssh/backtester_deploy.pub
```

**Copy the entire output** - it should look like:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... your_email@example.com
```

## Step 3: Add Public Key to Windows Machine (iBuyPower)

You have two options:

### Option A: Automated (if you can already SSH to Windows)

From your Mac Studio:

```bash
# Copy public key to Windows (replace with your actual key if different)
cat ~/.ssh/backtester_deploy.pub | ssh vfnoc@192.168.4.177 "mkdir -p .ssh && cat >> .ssh/authorized_keys"
```

### Option B: Manual (if SSH isn't working yet)

1. **On Windows iBuyPower machine:**
   - Open File Explorer
   - Navigate to `C:\Users\vfnoc\.ssh` (create folder if it doesn't exist)
   - Create or edit `authorized_keys` file
   - Paste the public key (from Step 2) into this file
   - Save the file

2. **Set permissions** (run in PowerShell as Administrator):
   ```powershell
   icacls "C:\Users\vfnoc\.ssh\authorized_keys" /inheritance:r
   icacls "C:\Users\vfnoc\.ssh\authorized_keys" /grant "vfnoc:(R)"
   ```

## Step 4: Test SSH Connection (Mac Studio)

On your Mac Studio, test the connection:

```bash
ssh -i ~/.ssh/backtester_deploy vfnoc@192.168.4.177
```

You should be able to connect **without entering a password**. If it works, type `exit` to disconnect.

**Expected output:**
```
Welcome to Windows...
```

## Step 5: Get Private Key for GitHub Secrets (Mac Studio)

On your Mac Studio:

```bash
cat ~/.ssh/backtester_deploy
```

**Copy the entire output**, including:
- `-----BEGIN OPENSSH PRIVATE KEY-----`
- All the lines in between
- `-----END OPENSSH PRIVATE KEY-----`

You'll need this in Step 6.

## Step 6: Add GitHub Secrets

Go to your GitHub repository settings:
**URL:** `https://github.com/vincenzo5/backtester-mvp/settings/secrets/actions`

Click **"New repository secret"** for each of the following:

### Secret 1: PRODUCTION_HOST
- **Name:** `PRODUCTION_HOST`
- **Value:** `192.168.4.177`

### Secret 2: PRODUCTION_USER
- **Name:** `PRODUCTION_USER`
- **Value:** `vfnoc`

### Secret 3: PRODUCTION_SSH_KEY
- **Name:** `PRODUCTION_SSH_KEY`
- **Value:** (paste the **entire private key** from Step 5, including BEGIN/END lines)

### Secret 4: PRODUCTION_PATH
- **Name:** `PRODUCTION_PATH`
- **Value:** `C:\Users\vfnoc\Documents\backtester`

## Step 7: Install Docker Desktop (iBuyPower Machine)

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

## Step 8: Clone Repository (iBuyPower Machine)

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

## Step 9: Initial Docker Setup Verification (iBuyPower Machine)

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

1. **Commit and push the deployment files** to GitHub:
   ```bash
   git add .github/workflows/deploy.yml deployment/docker-compose.yml docs/deployment-setup.md
   git commit -m "Add automated deployment pipeline"
   git push origin main
   ```

2. **Watch GitHub Actions:**
   - Go to: `https://github.com/vincenzo5/backtester-mvp/actions`
   - You should see a workflow run called "Build, Test, and Deploy"
   - Click on it to watch progress

3. **Verify deployment on iBuyPower:**
   ```powershell
   cd C:\Users\vfnoc\Documents\backtester\deployment
   docker-compose ps
   ```
   
   You should see the `data-scheduler` container running.

## Troubleshooting

### SSH Connection Fails

**Problem:** Can't connect via SSH from Mac Studio to iBuyPower.

**Solutions:**
1. **Verify SSH service is running:**
   ```powershell
   Get-Service sshd
   ```
   If not running, start it: `Start-Service sshd`

2. **Check firewall:**
   - Open Windows Defender Firewall → Advanced Settings
   - Look for "OpenSSH Server (sshd)" inbound rule
   - Ensure it's enabled and allows port 22

3. **Verify IP address:**
   ```powershell
   ipconfig
   ```
   Confirm the machine is at `192.168.4.177`

4. **Check SSH service listening:**
   ```powershell
   netstat -an | findstr :22
   ```
   Should show port 22 listening

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

**Problem:** GitHub Actions can't deploy to iBuyPower.

**Solutions:**
1. **Check Actions logs:**
   - Go to Actions tab → Click failed workflow → Check error messages

2. **Verify all secrets are set:**
   - Repository → Settings → Secrets and variables → Actions
   - Ensure all 4 secrets exist with correct values

3. **Test SSH manually first:**
   - Complete Step 4 to ensure SSH works from your Mac Studio

4. **Check Docker on iBuyPower:**
   - Verify Docker Desktop is running
   - Test `docker ps` and `docker-compose` commands work

5. **Verify repository path:**
   - Ensure repository exists at `C:\Users\vfnoc\Documents\backtester`
   - Path in `PRODUCTION_PATH` secret must match exactly

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

