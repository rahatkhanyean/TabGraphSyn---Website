# TabGraphSyn Deployment Guide

This guide will help you deploy TabGraphSyn with GPU support and make it accessible on the internet with a custom domain.

## Table of Contents
1. [Deployment Options](#deployment-options)
2. [Quick Start: RunPod Deployment](#quick-start-runpod-deployment)
3. [Alternative: Vast.ai Deployment](#alternative-vastai-deployment)
4. [Domain Setup](#domain-setup)
5. [SSL/HTTPS Configuration](#ssl-https-configuration)
6. [Post-Deployment](#post-deployment)
7. [Troubleshooting](#troubleshooting)

---

## Deployment Options

For GPU-enabled deployment on a minimal budget (~$10-20/month), we recommend:

1. **RunPod** (Recommended) - Easy to use, reliable, ~$0.20-0.40/hour for GPU instances
2. **Vast.ai** - GPU marketplace, can find cheaper options, ~$0.10-0.30/hour
3. **Lambda Labs** - Good balance of price and performance
4. **Paperspace** - User-friendly, good for beginners

**Cost-Saving Tips:**
- Use spot/interruptible instances when available (50-70% cheaper)
- Stop the instance when not training models
- Use on-demand pricing to avoid monthly commitments initially

---

## Quick Start: RunPod Deployment

### Prerequisites
- RunPod account ([runpod.io](https://runpod.io))
- Docker Hub account (optional, for custom images)
- Domain name (optional, can use IP address initially)

### Step 1: Create RunPod Account & Add Funds
1. Sign up at [runpod.io](https://runpod.io)
2. Add $10-20 to your account (credit card or crypto)
3. Navigate to "Pods" section

### Step 2: Deploy GPU Pod

1. **Click "Deploy"** or "Rent a Pod"

2. **Select GPU:**
   - For budget: RTX 3070/3080 (~$0.20-0.30/hour)
   - Recommended: RTX 4090 or A4000 (~$0.40-0.60/hour)
   - Choose "On-Demand" or "Spot" (cheaper but can be interrupted)

3. **Select Template:**
   - Choose "RunPod PyTorch" or "CUDA 11.8" template
   - Or use "Start from scratch" with custom Docker image

4. **Configure Pod:**
   ```
   Template: RunPod PyTorch
   Container Disk: 20 GB (minimum)
   Volume Disk: 50 GB (for data persistence)
   Expose HTTP Ports: 80, 443
   Expose TCP Ports: 22 (for SSH)
   ```

5. **Click "Deploy On-Demand"** or "Deploy Spot"

### Step 3: SSH into Your Pod

1. Once pod is running, click "Connect" → "Start Web Terminal" or use SSH
   ```bash
   ssh root@<pod-ip> -p <port> -i ~/.ssh/id_ed25519
   ```

2. You should now be in the pod's terminal

### Step 4: Deploy TabGraphSyn

1. **Install required tools:**
   ```bash
   apt-get update
   apt-get install -y git docker.io docker-compose-plugin
   ```

2. **Clone your repository:**
   ```bash
   cd /workspace
   git clone https://github.com/YOUR_USERNAME/TabGraphSyn-Django.git
   cd TabGraphSyn-Django
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.production.example .env
   nano .env
   ```

   **Update these critical values:**
   ```bash
   # Generate secret key
   SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

   # Set your domain or IP
   ALLOWED_HOSTS=your-pod-ip,your-domain.com
   CSRF_TRUSTED_ORIGINS=http://your-pod-ip,https://your-domain.com

   DEBUG=False
   ```

4. **Build and run with Docker Compose:**
   ```bash
   # Build the image
   docker compose build

   # Start the services
   docker compose up -d
   ```

5. **Check if everything is running:**
   ```bash
   docker compose ps
   docker compose logs -f web
   ```

6. **Create superuser (admin account):**
   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

### Step 5: Access Your Site

1. **Find your pod's IP:**
   - RunPod dashboard shows the IP address
   - Or run: `curl ifconfig.me`

2. **Open in browser:**
   ```
   http://YOUR_POD_IP
   ```

3. **Test admin panel:**
   ```
   http://YOUR_POD_IP/admin
   ```

**Congratulations!** Your site is now live on the internet!

---

## Alternative: Vast.ai Deployment

Vast.ai often has cheaper GPU instances through their marketplace.

### Step 1: Create Vast.ai Account
1. Sign up at [vast.ai](https://vast.ai)
2. Add funds ($10-20 to start)

### Step 2: Search for GPU Instance
1. Click "Search" or "Create"
2. **Filters:**
   - GPU: RTX 3070 or better
   - RAM: 16 GB+
   - Disk Space: 50 GB+
   - CUDA Version: 11.8+
   - Sort by: $/hour (lowest first)

3. **Select instance and click "Rent"**

4. **Configuration:**
   ```
   Image: pytorch/pytorch:2.0.1-cuda11.8-cudnn8-runtime
   On-start script: (leave blank for now)
   ```

### Step 3: Connect & Deploy
1. Click "Open SSH" or use provided SSH command
2. Follow same deployment steps as RunPod (Step 4 above)

---

## Domain Setup

### Option 1: Get a New Domain

**Recommended registrars:**
1. **Namecheap** - $10-15/year, user-friendly
2. **Cloudflare** - At-cost pricing (~$9/year), free SSL
3. **Google Domains** - $12/year, simple interface
4. **Porkbun** - Budget-friendly, good prices

**Steps:**
1. Go to your chosen registrar
2. Search for available domain (e.g., `tabgraphsyn.com`, `your-project.ai`)
3. Purchase domain (~$10-15/year)
4. Proceed to "Connect Domain to Server" below

### Option 2: Use Free Subdomain

**Free subdomain services:**
- **FreeDNS** (freedns.afraid.org) - Free subdomains like `yoursite.mooo.com`
- **Duck DNS** (duckdns.org) - Free dynamic DNS
- **No-IP** - Free dynamic DNS with subdomains

### Connect Domain to Server

#### Method 1: Using Cloudflare (Recommended - Free SSL)

1. **Add site to Cloudflare:**
   - Sign up at [cloudflare.com](https://cloudflare.com)
   - Click "Add a Site"
   - Enter your domain
   - Choose "Free" plan

2. **Update nameservers at your registrar:**
   - Cloudflare will show you 2 nameservers
   - Go to your domain registrar (Namecheap, etc.)
   - Update nameservers to Cloudflare's

3. **Add DNS record in Cloudflare:**
   ```
   Type: A
   Name: @ (or your subdomain)
   IPv4 address: YOUR_POD_IP
   Proxy status: DNS only (grey cloud) initially
   TTL: Auto
   ```

4. **Add www record (optional):**
   ```
   Type: CNAME
   Name: www
   Target: your-domain.com
   Proxy status: DNS only
   ```

5. **Enable proxy (orange cloud) after testing:**
   - This enables Cloudflare's CDN and free SSL

#### Method 2: Direct DNS (No Cloudflare)

1. **Log into your domain registrar**
2. **Find DNS settings** (usually "DNS Management" or "Advanced DNS")
3. **Add A record:**
   ```
   Host: @ (or www)
   Points to: YOUR_POD_IP
   TTL: 300 (or 5 minutes)
   ```

4. **Wait for propagation** (5 minutes to 48 hours)
   - Check with: `nslookup your-domain.com`

5. **Update your .env file:**
   ```bash
   nano .env

   # Update these lines:
   ALLOWED_HOSTS=your-domain.com,www.your-domain.com,YOUR_POD_IP
   CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com
   ```

6. **Restart your application:**
   ```bash
   docker compose restart web
   ```

---

## SSL/HTTPS Configuration

### Option 1: Cloudflare SSL (Easiest - Free)

If using Cloudflare:
1. In Cloudflare dashboard, go to SSL/TLS
2. Set SSL mode to "Flexible" or "Full"
3. Enable "Always Use HTTPS"
4. Turn on "Automatic HTTPS Rewrites"
5. Enable proxy (orange cloud) for your DNS records

Your site is now accessible via HTTPS!

### Option 2: Let's Encrypt (Free SSL Certificate)

1. **Install Certbot:**
   ```bash
   apt-get update
   apt-get install -y certbot python3-certbot-nginx
   ```

2. **Stop your containers temporarily:**
   ```bash
   docker compose down
   ```

3. **Get SSL certificate:**
   ```bash
   certbot certonly --standalone -d your-domain.com -d www.your-domain.com
   ```

4. **Update nginx configuration:**
   Create `deploy/nginx-ssl.conf`:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com www.your-domain.com;
       return 301 https://$server_name$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name your-domain.com www.your-domain.com;

       ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

       client_max_body_size 100M;

       location /static/ {
           alias /app/staticfiles/;
       }

       location /media/ {
           alias /app/media/;
       }

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

5. **Update docker-compose.yml to mount certificates:**
   ```yaml
   volumes:
     - /etc/letsencrypt:/etc/letsencrypt:ro
   ```

6. **Restart:**
   ```bash
   docker compose up -d
   ```

7. **Set up auto-renewal:**
   ```bash
   echo "0 0 * * * certbot renew --quiet && docker compose restart web" | crontab -
   ```

---

## Post-Deployment

### 1. Verify Deployment
```bash
# Check services are running
docker compose ps

# View logs
docker compose logs -f

# Test GPU access
docker compose exec web nvidia-smi
```

### 2. Monitor Resources
```bash
# Check disk space
df -h

# Check memory
free -h

# Monitor GPU
watch -n 1 nvidia-smi
```

### 3. Set Up Backups

**Backup MongoDB data:**
```bash
# Create backup script
cat > /workspace/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/workspace/backups"
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d_%H%M%S)

# Backup MongoDB
docker compose exec mongodb mongodump --out /data/backup/$DATE
docker cp tabgraphsyn_mongodb:/data/backup/$DATE $BACKUP_DIR/

# Backup media files
tar -czf $BACKUP_DIR/media_$DATE.tar.gz media/

echo "Backup completed: $DATE"
EOF

chmod +x /workspace/backup.sh
```

**Schedule automatic backups:**
```bash
# Add to crontab (daily at 2 AM)
echo "0 2 * * * /workspace/backup.sh" | crontab -
```

### 4. Security Checklist
- [ ] `DEBUG=False` in .env
- [ ] Strong `SECRET_KEY` generated
- [ ] `ALLOWED_HOSTS` configured correctly
- [ ] SSL/HTTPS enabled
- [ ] Firewall configured (only ports 80, 443, 22 open)
- [ ] Regular backups scheduled
- [ ] Strong admin password set
- [ ] Email verification enabled (if using email)

### 5. Performance Optimization

**For production use:**
```bash
# Update gunicorn workers in deploy/supervisord.conf
# Workers = (2 x CPU cores) + 1
# For 4 CPU cores: 9 workers

# Restart to apply
docker compose restart web
```

---

## Troubleshooting

### Site not accessible
1. Check if container is running: `docker compose ps`
2. Check logs: `docker compose logs web`
3. Verify firewall: `ufw status` (allow ports 80, 443)
4. Check DNS: `nslookup your-domain.com`

### "Bad Request (400)"
- Update `ALLOWED_HOSTS` in .env to include your domain/IP
- Restart: `docker compose restart web`

### "Forbidden (403)" CSRF error
- Update `CSRF_TRUSTED_ORIGINS` in .env
- Include `https://` prefix
- Restart: `docker compose restart web`

### GPU not detected
```bash
# Check NVIDIA driver
nvidia-smi

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Rebuild with GPU support
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Out of disk space
```bash
# Clean old Docker images
docker system prune -a

# Check volume usage
docker volume ls
```

### MongoDB connection errors
```bash
# Check MongoDB is running
docker compose ps mongodb

# Check connection from web container
docker compose exec web python manage.py shell
>>> from pymongo import MongoClient
>>> client = MongoClient('mongodb://mongodb:27017')
>>> client.server_info()
```

### Slow training/inference
```bash
# Check GPU utilization
nvidia-smi

# Verify PyTorch can use GPU
docker compose exec web python -c "import torch; print(torch.cuda.is_available())"
```

---

## Cost Management

### Estimate Monthly Costs

**Scenario 1: Always-on development**
- RTX 3080 @ $0.30/hour × 24h × 30 days = $216/month
- **Not recommended for budget deployment**

**Scenario 2: On-demand usage (recommended)**
- Web app: Use free tier (Render, Railway) = $0
- GPU: 40 hours/month training @ $0.30/hour = $12/month
- Domain: $10-15/year = ~$1.20/month
- **Total: ~$13-14/month**

**Scenario 3: Hybrid approach**
- Cheap VPS for web ($5/month)
- GPU on-demand (40 hrs) = $12/month
- Domain = ~$1.20/month
- **Total: ~$18/month**

### Cost-Saving Tips

1. **Use spot instances** - 50-70% cheaper than on-demand
2. **Stop when not in use** - RunPod charges only when running
3. **Use smaller GPUs for testing** - RTX 3060 instead of A100
4. **Leverage free tiers:**
   - MongoDB Atlas (free 512MB)
   - Cloudflare (free SSL, CDN)
   - Render/Railway (free tier for web app)

---

## Getting a Custom Domain (Detailed)

### Recommended Domain Registrars

1. **Cloudflare Registrar** (Recommended)
   - Cost: ~$9-10/year (.com)
   - Pros: At-cost pricing, free SSL, built-in CDN, DDoS protection
   - Cons: Need existing Cloudflare account
   - URL: [cloudflare.com/products/registrar](https://www.cloudflare.com/products/registrar/)

2. **Namecheap**
   - Cost: $10-13/year (.com first year)
   - Pros: User-friendly, good support, includes WhoisGuard
   - Cons: Renewal rates higher
   - URL: [namecheap.com](https://www.namecheap.com)

3. **Porkbun**
   - Cost: $9-11/year (.com)
   - Pros: Very affordable, includes free WhoisGuard, SSL
   - Cons: Smaller company
   - URL: [porkbun.com](https://porkbun.com)

4. **Google Domains** (Now Squarespace)
   - Cost: $12/year (.com)
   - Pros: Clean interface, Google integration
   - Cons: Recently acquired by Squarespace
   - URL: [domains.google](https://domains.google)

### Domain Name Ideas for Your Project

- `tabgraphsyn.com` - Direct and professional
- `tabgraph.ai` - Modern, AI-focused (.ai domains ~$60/year)
- `syntheticdata.io` - Descriptive (.io domains ~$30/year)
- `yourusername-tabgraph.com` - Personal branding
- Use a free subdomain initially: `tabgraphsyn.freemyip.com`

### Steps to Purchase Domain (Namecheap Example)

1. Go to [namecheap.com](https://www.namecheap.com)
2. Search for your desired domain
3. Add to cart (~$10-13 for .com)
4. **Uncheck upsells** (you don't need them):
   - PremiumDNS - Not needed
   - WhoisGuard - Usually included free first year
   - Email hosting - Not needed initially
5. Complete purchase
6. Follow "Connect Domain to Server" section above

---

## Next Steps

1. **Monitor your deployment:**
   - Set up email alerts for downtime
   - Monitor GPU usage and costs
   - Check logs regularly

2. **Optimize for production:**
   - Enable caching (Redis)
   - Set up CDN (Cloudflare)
   - Configure monitoring (Sentry)

3. **Scale as needed:**
   - Add load balancer for multiple instances
   - Use managed MongoDB (Atlas) for reliability
   - Implement auto-scaling

---

## Support & Resources

- **TabGraphSyn Documentation:** (your repository README)
- **RunPod Docs:** [docs.runpod.io](https://docs.runpod.io)
- **Vast.ai Docs:** [vast.ai/docs](https://vast.ai/docs)
- **Django Deployment:** [docs.djangoproject.com/en/4.2/howto/deployment/](https://docs.djangoproject.com/en/4.2/howto/deployment/)
- **Docker Compose:** [docs.docker.com/compose/](https://docs.docker.com/compose/)

---

## Quick Reference Commands

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f web

# Restart service
docker compose restart web

# Run Django commands
docker compose exec web python manage.py <command>

# Create superuser
docker compose exec web python manage.py createsuperuser

# Enter Django shell
docker compose exec web python manage.py shell

# Check GPU
docker compose exec web nvidia-smi

# Backup database
docker compose exec mongodb mongodump --out /data/backup

# Update code
git pull
docker compose build
docker compose up -d
```

---

**Need help?** Open an issue on GitHub or refer to platform-specific documentation.

Good luck with your deployment! 🚀
