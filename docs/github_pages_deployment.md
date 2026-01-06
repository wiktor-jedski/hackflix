# GitHub Pages Deployment Guide

This document explains how to deploy the HackFlix catalog to GitHub Pages using the prepared `hackflix-catalog` repository.

## Overview

The `hackflix-catalog` directory contains a complete, ready-to-deploy GitHub Pages site with:
- catalog.json (the main catalog file)
- Automated validation via GitHub Actions
- Scripts for maintenance and updates
- Complete documentation

## Repository Structure

```
hackflix-catalog/
├── catalog.json                     # Main catalog file (served via GitHub Pages)
├── SCHEMA.md                        # Schema documentation
├── README.md                        # Repository documentation
├── SETUP.md                         # Detailed setup instructions
├── CONTRIBUTING.md                  # Contribution guidelines
├── CNAME.example                    # Example for custom domain
├── .gitignore                       # Git ignore rules
├── init-repo.sh                     # Quick setup script
├── .github/
│   └── workflows/
│       └── validate.yml             # GitHub Actions workflow
└── scripts/
    ├── validate_catalog.py          # Validation script
    └── update_timestamp.py          # Timestamp updater
```

## Quick Start

### Option 1: Automated Setup (Recommended)

```bash
# Navigate to catalog directory
cd hackflix-catalog

# Run init script with your GitHub username
./init-repo.sh YOUR_GITHUB_USERNAME

# Follow the instructions printed by the script
```

### Option 2: Manual Setup

See detailed instructions in `hackflix-catalog/SETUP.md`.

## Deployment Steps

1. **Create GitHub Repository**
   - Name: `hackflix-catalog`
   - Visibility: Public (required for GitHub Pages)

2. **Push Catalog**
   ```bash
   cd hackflix-catalog
   git init
   git add .
   git commit -m "Initial catalog"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/hackflix-catalog.git
   git push -u origin main
   ```

3. **Enable GitHub Pages**
   - Repository Settings → Pages
   - Source: Deploy from branch `main`
   - Folder: `/` (root)

4. **Wait for Deployment**
   - Check Actions tab for validation status
   - Wait ~2 minutes for initial deployment

5. **Verify**
   ```bash
   curl https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json
   ```

## Configuration

### Update Client Configuration

After deployment, configure HackFlix client:

**In `.env` file:**
```
CATALOG_URL=https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json
```

**Or in `source/config.py`:**
```python
CATALOG_URL = os.getenv(
    "CATALOG_URL",
    "https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json"
)
```

## Maintenance

### Adding New Content

```bash
cd hackflix-catalog

# Edit catalog.json
vim catalog.json

# Validate
python scripts/validate_catalog.py

# Update timestamp
python scripts/update_timestamp.py

# Commit and push
git add catalog.json
git commit -m "Add: Movie Name"
git push

# Wait for auto-deployment (2-5 minutes)
```

### Monitoring

- **GitHub Actions**: Automatic validation on every commit
- **GitHub Pages**: Deployment status in repository Settings
- **Traffic**: Repository Insights → Traffic

## Features

### Automated Validation

Every commit triggers:
- JSON syntax check
- Schema validation
- Business logic checks
- File size verification

### CDN Delivery

GitHub Pages includes:
- Global CDN (Fastly)
- Automatic HTTPS
- CORS headers enabled
- DDoS protection

### Version Control

- Full git history
- Rollback capability
- Collaborative editing via PRs
- Branch protection available

## Custom Domain (Optional)

1. Add CNAME file:
   ```bash
   echo "catalog.yourdomain.com" > CNAME
   git add CNAME && git commit -m "Add custom domain" && git push
   ```

2. Configure DNS:
   - CNAME record: `catalog` → `YOUR_USERNAME.github.io`

3. Enable HTTPS in GitHub Pages settings

## Troubleshooting

### Validation Fails

```bash
# Check errors
python scripts/validate_catalog.py

# Common issues:
# - Missing required fields
# - Invalid JSON syntax
# - Duplicate IDs
# - Wrong magnet format
```

### Deployment Not Working

1. Verify repository is public
2. Check GitHub Actions for errors
3. Wait 5-10 minutes for propagation
4. Clear browser cache

### Old Content Showing

```bash
# Check last_updated timestamp
curl https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json | grep last_updated

# Wait for CDN cache (up to 10 minutes)
# Or force refresh with query param
curl "https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json?$(date +%s)"
```

## Security Best Practices

1. **Enable Branch Protection**
   - Require PR reviews
   - Require status checks (validation)

2. **Review Contributions**
   - Check all PRs before merging
   - Verify magnet links
   - Test changes locally

3. **Monitor Repository**
   - Watch for suspicious commits
   - Review Actions runs
   - Check Issues/Discussions

## Cost

**Free!** GitHub Pages is free for public repositories:
- Bandwidth: 100 GB/month soft limit
- Storage: 1 GB (more than enough)
- Actions: 2000 minutes/month

## Support

- **Setup Help**: See `hackflix-catalog/SETUP.md`
- **Contributing**: See `hackflix-catalog/CONTRIBUTING.md`
- **Schema**: See `hackflix-catalog/SCHEMA.md`
- **Issues**: Report via GitHub Issues

## Next Steps

After successful deployment:

1. ✅ Test catalog URL in browser
2. ✅ Configure HackFlix client
3. ✅ Test sync from client
4. ✅ Set up branch protection
5. ✅ Add more content to catalog

---

**Deployment Time**: ~15 minutes
**Difficulty**: Easy
**Prerequisites**: GitHub account, Git, Python 3.7+
