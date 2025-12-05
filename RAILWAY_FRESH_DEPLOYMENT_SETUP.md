# Railway Fresh Deployment - Setup Guide

## Status: Service Recreated from Scratch

You've deleted the old service and created a new one from GitHub. Here's what you need to configure:

---

## Step 1: Environment Variables (REQUIRED)

Go to the new service → **Variables** tab and add these:

### Required Variables:

```bash
SECRET_KEY=7c#5pmt&59lv#w*dhmf5vv57rm1+b7t=m1+u1jcttm7z0qy*%7
DEBUG=False
DJANGO_ALLOWED_HOSTS=.up.railway.app,.railway.app,atlas.alexandratechlab.com,atlas-crm.alexandratechlab.com
```

### Database Variable:

If you have an existing Postgres service in the project:
```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

Or create a new Postgres database:
1. Click "+ New" in Railway project
2. Select "Database" → "PostgreSQL"
3. Once created, add the reference above

---

## Step 2: Verify Build Configuration

The service should auto-detect the Dockerfile. Verify in **Settings** → **Build**:

- **Builder**: Should show "Dockerfile" (auto-detected)
- **Dockerfile Path**: `Dockerfile` (or leave blank)
- **Build Command**: Leave empty (Dockerfile handles it)

---

## Step 3: Verify Deploy Configuration

In **Settings** → **Deploy**:

- **Start Command**: Should be empty (Dockerfile CMD will be used)
  - Or set to: `gunicorn crm_fulfillment.wsgi --bind 0.0.0.0:$PORT --workers 3 --timeout 120`
- **Restart Policy**: On Failure
- **Max Retries**: 10

---

## Step 4: Generate Domain

In **Settings** → **Networking**:

1. Click "Generate Domain"
2. You'll get: `https://<service-name>-production.up.railway.app`

---

## Step 5: Monitor Deployment

1. Go to **Deployments** tab
2. Watch the build logs
3. Look for:
   ```
   Building with Dockerfile...
   #1 [internal] load build definition from Dockerfile
   #2 FROM python:3.12-slim
   ...
   Successfully built
   ```

4. Then watch runtime logs for:
   ```
   Collecting static files...
   Making migrations...
   Applying migrations...
   Starting gunicorn...
   Listening at: http://0.0.0.0:8000
   ```

---

## Expected Build Process

### Build Phase:
```
Building...
=> [1/6] FROM python:3.12-slim
=> [2/6] WORKDIR /app
=> [3/6] RUN apt-get update && apt-get install -y gcc python3-dev...
=> [4/6] COPY requirements.txt /app/
=> [5/6] RUN pip install --upgrade pip && pip install -r requirements.txt
=> [6/6] COPY . /app/
Successfully built
```

### Deploy Phase:
```
Starting Container...
Running entrypoint.sh...
Collecting static files...
150 static files copied to '/app/staticfiles'
Making migrations...
No changes detected
Applying migrations...
Operations to perform: Apply all migrations
Running migrations: OK
Applying Roles&Permissions...
Creating superuser (if needed)...
Superuser already exists

Starting gunicorn 21.2.0
Listening at: http://0.0.0.0:8000 (PID: 1)
Using worker: sync
Booting worker with pid: 7
Booting worker with pid: 8
Booting worker with pid: 9
```

---

## Step 6: Post-Deployment Tasks

Once the service is running successfully:

### A. Create Superuser (if needed)

Via Railway dashboard → Service → ... menu → "Shell" or via CLI:

```bash
RAILWAY_TOKEN="cbe816b4-cd55-4d6b-9c3c-f3535da1d131" railway run python manage.py createsuperuser --noinput --email admin@atlas.com
```

### B. Test the Deployment

```bash
# Test admin page
curl https://<your-domain>/admin/

# Should return Django admin HTML
```

### C. Access Admin Panel

1. Go to: `https://<your-domain>/admin/`
2. Login with superuser credentials (created by entrypoint.sh):
   - Email: `admin@devm7md.xyz`
   - Username: `admin`
   - Password: `admin123`

---

## Troubleshooting

### If Build Fails:

**Check build logs** for specific error. Common issues:

1. **Dependencies error**: Check `requirements.txt`
2. **Dockerfile syntax**: Check `Dockerfile`
3. **Missing files**: Verify all files pushed to GitHub

### If Container Crashes:

**Check runtime logs** for errors:

1. **Database connection**: Verify `DATABASE_URL` is set
2. **Secret key**: Verify `SECRET_KEY` is set
3. **Static files**: May fail to collect if missing directories
4. **Migrations**: May fail if database schema issues

### If Shows 502 Error:

- Container is starting but not responding
- Check if gunicorn is binding to correct `$PORT`
- Verify `PORT` environment variable exists (Railway auto-sets it)

### If Still Shows Next.js:

**This should NOT happen** with a fresh service. If it does:
1. Verify you're looking at the correct service
2. Check the GitHub repository connection
3. Try disconnecting and reconnecting the repo

---

## Service Configuration Checklist

- [ ] Repository connected: `maanisingh/atlas-crm`
- [ ] Branch: `master`
- [ ] Builder: Dockerfile (auto-detected)
- [ ] Environment variables set:
  - [ ] `SECRET_KEY`
  - [ ] `DEBUG=False`
  - [ ] `DATABASE_URL`
  - [ ] `DJANGO_ALLOWED_HOSTS`
- [ ] Domain generated
- [ ] Deployment successful
- [ ] Admin page accessible
- [ ] Can login to admin

---

## Quick Reference

**GitHub Repository**: https://github.com/maanisingh/atlas-crm
**Branch**: master
**Project ID**: 3781876d-0f00-478c-b419-0ec4b0c7819a
**Project Token**: cbe816b4-cd55-4d6b-9c3c-f3535da1d131

**Default Superuser** (created by entrypoint.sh):
- Email: admin@devm7md.xyz
- Username: admin
- Password: admin123

---

## What Changed from Old Service

### Old Service Issues:
- ❌ Was running cached Next.js container
- ❌ Ignored Dockerfile
- ❌ Configuration conflicts

### New Fresh Service:
- ✅ Clean slate - no cache
- ✅ Will detect and use Dockerfile
- ✅ Correct Django deployment
- ✅ All configuration files ready in repo

---

## Files in Repository (Ready for Deployment)

All necessary files are already in the GitHub repository:

- ✅ `Dockerfile` (Python 3.12, Django, Gunicorn)
- ✅ `requirements.txt` (All dependencies fixed)
- ✅ `Procfile` (Alternative to Dockerfile)
- ✅ `railway.json` (Railway configuration)
- ✅ `nixpacks.toml` (Build environment)
- ✅ `entrypoint.sh` (Setup script)
- ✅ `runtime.txt` (Python 3.12.3)
- ✅ `manage.py` (Django management)
- ✅ `.railwayignore` (Exclude unnecessary files)
- ✅ All Django app code

**Nothing needs to be changed** - just configure variables and deploy!

---

## Next Steps

1. **Set environment variables** (most important!)
2. **Wait for build to complete** (2-3 minutes)
3. **Check deployment logs** for success
4. **Generate domain** if not auto-generated
5. **Test admin page** at `https://<domain>/admin/`
6. **Verify login works**

---

**Generated**: December 5, 2025
**Status**: Fresh service - ready for configuration
**Expected Result**: Django Atlas CRM running successfully on Railway

---
