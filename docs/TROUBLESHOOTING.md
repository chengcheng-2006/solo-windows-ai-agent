# Troubleshooting Guide

## Common Issues

### Gateway fails to start

**Symptoms**: `.\scripts\start.ps1` exits with error; port 18789 not listening

**Possible causes**:
1. Port already in use → `netstat -ano | findstr :18789`
2. Missing API keys → Check `.env` file
3. Node.js version too old → `node --version` (need 18+)

### Docker services don't start

**Symptoms**: `docker compose up` fails

**Checklist**:
1. Docker Desktop is running
2. WSL2 is enabled
3. Ports are free (5432, 4222, 7233, etc.)
4. Environment variables are set (PAIOS_POSTGRES_PASSWORD, etc.)

### CDP browser connection fails

**Symptoms**: Browser worker can't connect to Chrome

**Solutions**:
1. Make sure Chrome is installed
2. Enable Chrome remote debugging:
   - Close all Chrome windows
   - Run: `"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222`
3. Check if port 9222 is free

### Windows UIA automation fails

**Symptoms**: Windows worker can't interact with UI elements

**Solutions**:
1. Run PowerShell as administrator
2. Some applications require elevated privileges for UIA access
3. Try OCR fallback if UIA returns empty results

### WeChat not responding

**Symptoms**: WeChat gateway shows as not connected

**Solutions**:
1. Restart the WeChat process
2. Check pairing status
3. Verify ownerAllowFrom is configured correctly
4. Ensure WeChat account is logged in

### Model API errors

**Symptoms**: Agent responses fail with API errors

**Checklist**:
1. API key is valid and has credits
2. Network connectivity: `curl https://api.deepseek.com`
3. Proxy configuration (if behind corporate proxy)
4. Rate limits not exceeded

## Diagnostic Commands

```powershell
# Check gateway health
curl http://127.0.0.1:18789/health

# Check all running processes
Get-Process | Where-Object { $_.ProcessName -like "*openclaw*" -or $_.ProcessName -like "*node*" }

# Check port usage
netstat -ano | findstr :18789
netstat -ano | findstr :8810

# Check Docker status
docker ps
docker compose -f infra/docker-compose.yml ps

# Check logs
Get-ChildItem D:\Solo\logs\ -Recurse | Select-Object Name, Length
```

## Log Locations

| Component | Log Location |
|-----------|-------------|
| Gateway | `state\watchdog\` |
| Workers | `logs\` |
| Docker | `docker logs <container_name>` |
| Watchdog | `state\watchdog\alerts\` |

## How to Completely Stop Solo

```powershell
# Stop all Solo processes
.\scripts\stop.ps1

# Stop Docker services
cd infra
docker compose down

# Kill any remaining processes
Get-Process | Where-Object { $_.ProcessName -like "*paios*" -or $_.ProcessName -like "*openclaw*" } | Stop-Process -Force
```
