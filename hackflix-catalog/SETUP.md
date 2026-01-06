# GitHub Pages Setup Guide

Complete step-by-step guide to deploy the HackFlix catalog on GitHub Pages.

## Prerequisites

- GitHub account
- Git installed locally
- Python 3.7+ (for validation)

## Step 1: Create GitHub Repository

### Option A: Via GitHub Web Interface

1. Go to https://github.com/new
2. Repository name: `hackflix-catalog`
3. Description: "HackFlix movie and series catalog"
4. Visibility: **Public** (required for GitHub Pages)
5. **Do NOT** initialize with README, .gitignore, or license
6. Click "Create repository"

### Option B: Via GitHub CLI

```bash
gh repo create hackflix-catalog --public --description "HackFlix catalog"
```

## Step 2: Initialize Local Repository

```bash
# Navigate to the hackflix-catalog directory
cd /path/to/hackflix-catalog

# Initialize git repository
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial catalog setup with 5 movies and 3 series"

# Rename branch to main
git branch -M main

# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/hackflix-catalog.git

# Push to GitHub
git push -u origin main
```

## Step 3: Enable GitHub Pages

### Via Web Interface

1. Go to your repository on GitHub
2. Click **Settings** tab
3. Scroll down to **Pages** section (left sidebar)
4. Under "Build and deployment":
   - Source: **Deploy from a branch**
   - Branch: **main**
   - Folder: **/ (root)**
5. Click **Save**

### Verification

After a few moments:
1. Refresh the Pages settings
2. You should see: "Your site is live at `https://YOUR_USERNAME.github.io/hackflix-catalog/`"
3. Visit: `https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json`
4. You should see the JSON catalog

## Step 4: Verify GitHub Actions

1. Go to **Actions** tab in your repository
2. You should see "Validate Catalog" workflow
3. Check that it completed successfully (green checkmark)
4. If failed, click on the workflow to see error details

## Step 5: Test the Catalog URL

```bash
# Test with curl
curl https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json

# Or with Python
python -c "import requests; print(requests.get('https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json').json()['version'])"
```

Expected output: `1.0.0`

## Step 6: Configure HackFlix Client

Update your HackFlix client configuration:

### Using Environment Variable

```bash
# In your .env file
CATALOG_URL=https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json
```

### Using Config File

```python
# In source/config.py
CATALOG_URL = "https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json"
```

## Optional: Custom Domain

### Step 1: Add CNAME File

```bash
# In hackflix-catalog directory
echo "catalog.yourdomain.com" > CNAME
git add CNAME
git commit -m "Add custom domain"
git push
```

### Step 2: Configure DNS

Add DNS record at your domain provider:

**CNAME Record**:
- Name: `catalog` (or subdomain of your choice)
- Target: `YOUR_USERNAME.github.io`
- TTL: 3600 (or default)

### Step 3: Enable HTTPS

1. Wait for DNS propagation (can take up to 24 hours)
2. Go to repository Settings → Pages
3. Check "Enforce HTTPS"
4. Wait for SSL certificate to provision

### Step 4: Update Client

```bash
CATALOG_URL=https://catalog.yourdomain.com/catalog.json
```

## Workflow for Updates

### Adding New Content

```bash
# 1. Edit catalog.json (add movie or series)
vim catalog.json

# 2. Validate changes
python scripts/validate_catalog.py

# 3. Update timestamp
python scripts/update_timestamp.py

# 4. Commit and push
git add catalog.json
git commit -m "Add: [Movie/Series Name]"
git push

# 5. Wait for GitHub Actions to validate and deploy
# Check Actions tab for status

# 6. Verify deployment
curl https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json | grep "last_updated"
```

### Expected Timeline

- **Commit to push**: Instant
- **GitHub Actions validation**: ~30 seconds
- **GitHub Pages deployment**: 1-2 minutes
- **CDN propagation**: Up to 10 minutes
- **Total**: ~5-15 minutes from commit to live

## Troubleshooting

### Issue: GitHub Pages not showing

**Solution**:
1. Check repository is public
2. Verify Pages is enabled in Settings
3. Check Actions tab for build errors
4. Wait 5-10 minutes for initial deployment

### Issue: Validation failing

**Solution**:
```bash
# Run validation locally
python scripts/validate_catalog.py

# Fix reported errors
# Re-commit and push
```

### Issue: 404 on catalog.json

**Solution**:
1. Verify file exists in repository: `catalog.json`
2. Check GitHub Pages settings use correct branch
3. Wait for deployment to complete
4. Try accessing base URL first: `https://YOUR_USERNAME.github.io/hackflix-catalog/`

### Issue: Old content showing

**Solution**:
```bash
# Clear CDN cache (wait 10 minutes)
# Or force refresh with query parameter
curl "https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json?$(date +%s)"
```

### Issue: CORS errors

**Solution**:
- GitHub Pages automatically sets CORS headers
- No action needed
- If still seeing errors, check browser console for details

## Monitoring

### Check Deployment Status

```bash
# Via GitHub CLI
gh run list --repo YOUR_USERNAME/hackflix-catalog

# View specific run
gh run view RUN_ID
```

### Monitor Traffic

1. Go to repository Insights → Traffic
2. View unique visitors and page views
3. Check popular content

### Bandwidth Limits

- **GitHub Pages**: 100 GB/month soft limit
- **Actions**: 2000 minutes/month (free tier)
- **Storage**: 1 GB (more than enough for catalog)

If limits exceeded:
- Contact GitHub Support for increase
- Consider self-hosting or CDN
- Implement client-side caching

## Backup Strategy

### Automated Backups

GitHub is your backup! But for extra safety:

```bash
# Clone repository to backup location
git clone https://github.com/YOUR_USERNAME/hackflix-catalog.git backup/

# Or create releases
git tag -a v1.0.0 -m "Catalog version 1.0.0"
git push origin v1.0.0
```

### Export Catalog

```bash
# Download current live version
curl -o catalog-backup-$(date +%Y%m%d).json \
  https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json
```

## Security

### Best Practices

1. **Never commit**: API keys, passwords, or sensitive data
2. **Review PRs**: Check all contributions before merging
3. **Enable branch protection**: Require PR reviews for main branch
4. **Use .gitignore**: Prevent accidental commits
5. **Monitor Actions**: Watch for suspicious workflow runs

### Branch Protection (Recommended)

1. Go to Settings → Branches
2. Add rule for `main` branch
3. Enable:
   - ✅ Require pull request before merging
   - ✅ Require status checks to pass (Validate Catalog)
   - ✅ Require branches to be up to date

## Performance Optimization

### Client-Side Caching

Implement in your client:

```python
import requests
from datetime import datetime

def fetch_catalog_if_updated(url, last_updated=None):
    """Only fetch if catalog has been updated"""
    headers = {}
    if last_updated:
        headers['If-Modified-Since'] = last_updated

    response = requests.get(url, headers=headers)

    if response.status_code == 304:
        print("Catalog not modified, using cache")
        return None

    return response.json()
```

### CDN Configuration

GitHub Pages uses Fastly CDN automatically:
- Global edge locations
- Automatic HTTPS
- DDoS protection
- No configuration needed

## Next Steps

After successful deployment:

1. ✅ Verify catalog URL is accessible
2. ✅ Test with HackFlix client
3. ✅ Add more content to catalog
4. ✅ Set up branch protection
5. ✅ Configure notifications for Issues/PRs
6. ✅ Document contribution guidelines
7. ✅ Create first release tag

## Support

- **GitHub Docs**: https://docs.github.com/en/pages
- **GitHub Actions**: https://docs.github.com/en/actions
- **Issues**: Report problems in repository issues
- **Discussions**: Ask questions in repository discussions

---

**Setup Time**: ~15 minutes (excluding DNS propagation for custom domain)
**Difficulty**: Easy
**Cost**: Free (GitHub Pages is free for public repositories)
