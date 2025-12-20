# TabGraphSyn Quick Deployment Checklist

## 🚀 Get Your Site Online in 15 Minutes

### Prerequisites
- [ ] RunPod or Vast.ai account
- [ ] $10-20 in account credits
- [ ] Git repository set up

---

## Step 1: Launch GPU Instance (5 mins)

### RunPod:
1. Go to [runpod.io](https://runpod.io) → Pods → Deploy
2. Select GPU: RTX 3070/3080 (budget) or RTX 4090 (performance)
3. Template: "RunPod PyTorch" or "CUDA 11.8"
4. Storage: 20 GB container + 50 GB volume
5. Expose ports: 80, 443
6. Click "Deploy On-Demand"
7. Wait for pod to start (2-3 minutes)

### Vast.ai:
1. Go to [vast.ai](https://vast.ai) → Search
2. Filter: RTX 3070+, 16GB RAM, 50GB disk, CUDA 11.8+
3. Sort by $/hour (low to high)
4. Select instance → Rent
5. Image: `pytorch/pytorch:2.0.1-cuda11.8-cudnn8-runtime`

---

## Step 2: Connect & Setup (3 mins)

1. **Connect to your instance:**
   - RunPod: Click "Connect" → "Start Web Terminal"
   - Vast.ai: Click "Open SSH" or use provided SSH command

2. **Install Docker (if not already installed):**
   ```bash
   apt-get update && apt-get install -y git docker.io docker-compose-plugin
   ```

3. **Clone your repository:**
   ```bash
   cd /workspace
   git clone https://github.com/YOUR_USERNAME/TabGraphSyn-Django.git
   cd TabGraphSyn-Django
   ```

---

## Step 3: Configure Environment (2 mins)

```bash
# Copy environment template
cp .env.production.example .env

# Edit configuration
nano .env
```

**Required changes in .env:**
```bash
# Generate secret key (run this command and copy the output):
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Paste the secret key here:
SECRET_KEY=your-generated-secret-key-here

# Get your instance IP:
curl ifconfig.me

# Set allowed hosts (replace YOUR_IP with actual IP):
ALLOWED_HOSTS=YOUR_IP,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://YOUR_IP

# Set debug to false
DEBUG=False
```

Save and exit (Ctrl+X, Y, Enter)

---

## Step 4: Deploy (5 mins)

```bash
# Build and start
docker compose build
docker compose up -d

# Wait for services to start (1-2 minutes)
# Watch logs to see progress
docker compose logs -f
```

**Wait until you see:** "Booting worker" or "Listening at: http://127.0.0.1:8000"

Press Ctrl+C to exit logs.

**Create admin user:**
```bash
docker compose exec web python manage.py createsuperuser
```
Follow prompts to create username/password.

---

## Step 5: Access Your Site! (1 min)

1. **Get your IP:**
   ```bash
   curl ifconfig.me
   ```

2. **Open in browser:**
   ```
   http://YOUR_IP
   ```

3. **Test admin panel:**
   ```
   http://YOUR_IP/admin
   ```

**✅ Your site is now live on the internet!**

---

## Optional: Add Custom Domain

### Quick Domain Setup (with Cloudflare - Recommended)

1. **Get a domain:**
   - Buy from Namecheap, Cloudflare, or Porkbun (~$10/year)
   - Or use free subdomain from FreeDNS or DuckDNS

2. **Add to Cloudflare:**
   - Create free account at cloudflare.com
   - Add your domain
   - Change nameservers at your registrar

3. **Add DNS record:**
   ```
   Type: A
   Name: @
   Content: YOUR_IP
   Proxy: DNS only (grey cloud)
   ```

4. **Update .env:**
   ```bash
   nano .env

   # Update these lines:
   ALLOWED_HOSTS=your-domain.com,www.your-domain.com,YOUR_IP
   CSRF_TRUSTED_ORIGINS=https://your-domain.com
   ```

5. **Restart:**
   ```bash
   docker compose restart web
   ```

6. **Enable Cloudflare SSL:**
   - In Cloudflare: SSL/TLS → Full
   - Enable "Always Use HTTPS"
   - Turn on proxy (orange cloud) for DNS record

**Access your site:** `https://your-domain.com`

---

## Troubleshooting

### Site not loading?
```bash
# Check if services are running
docker compose ps

# Should show "Up" for both web and mongodb
# If not, view logs:
docker compose logs web
```

### "Bad Request (400)" error?
```bash
# Update ALLOWED_HOSTS in .env with your IP/domain
nano .env
docker compose restart web
```

### GPU not working?
```bash
# Verify GPU is accessible
docker compose exec web nvidia-smi

# If error, rebuild:
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Forgot admin password?
```bash
# Create new superuser
docker compose exec web python manage.py createsuperuser
```

---

## Useful Commands

```bash
# View live logs
docker compose logs -f web

# Restart service
docker compose restart web

# Stop all services
docker compose down

# Start all services
docker compose up -d

# Check GPU usage
watch -n 1 nvidia-smi

# Update code
git pull
docker compose build
docker compose restart web
```

---

## Cost Monitoring

**Check your spending:**
- RunPod: Dashboard → Billing
- Vast.ai: Top right → Credits

**Stop instance when not needed:**
- RunPod: Click "Stop" on pod
- Vast.ai: Click "Destroy" instance

You only pay when running!

---

## Next Steps

- [ ] Set up automatic backups (see DEPLOYMENT.md)
- [ ] Configure email for user verification
- [ ] Set up monitoring and alerts
- [ ] Read full deployment guide: [DEPLOYMENT.md](../DEPLOYMENT.md)

---

**Need more help?** See detailed guide: [DEPLOYMENT.md](../DEPLOYMENT.md)

**Cost too high?** Consider hybrid deployment: free tier web hosting + on-demand GPU

Good luck! 🎉
