# API Key Setup Guide

This guide explains how to configure routing API keys for the Margsathi navigation system.

## Overview

The system supports multiple routing providers with automatic fallback:
- **MapMyIndia** - Indian mapping service with local traffic data
- **Mapbox** - Global routing with excellent coverage
- **Google Maps** - Comprehensive worldwide routing
- **OSRM** - Open-source routing (no API key required)

## Security Model

🔒 **All API keys are stored in environment variables and accessed only on the backend.**

- API keys are NEVER exposed to the frontend
- Keys are loaded from `.env` file using `os.getenv()`
- The `.env` file must be added to `.gitignore` to prevent accidental commits

## Quick Start

### 1. Copy Environment Template

```bash
cp .env.example .env
```

### 2. Choose Your Provider

Edit `.env` and set your preferred provider:

```bash
# Options: mapmyindia, mapbox, google, osrm
ROUTING_PROVIDER=osrm
```

### 3. Add API Keys (Optional)

If using OSRM (default), no API key is needed. For other providers, add your keys:

## Provider Setup Instructions

### OSRM (Recommended for Development)

**No API key required!** OSRM uses a public server.

```bash
ROUTING_PROVIDER=osrm
OSRM_BASE_URL=https://router.project-osrm.org
```

✅ **Advantages**: Free, no signup, works immediately  
⚠️ **Limitations**: Public server, rate limits may apply

---

### Mapbox

1. Sign up at [https://www.mapbox.com/](https://www.mapbox.com/)
2. Go to **Account → Tokens**
3. Create a new access token or copy your default token
4. Add to `.env`:

```bash
ROUTING_PROVIDER=mapbox
MAPBOX_API_KEY=pk.eyJ1IjoieW91ci11c2VybmFtZSIsImEiOiJ5b3VyLXRva2VuIn0...
```

✅ **Advantages**: Excellent global coverage, fast, reliable  
💰 **Pricing**: Free tier: 100,000 requests/month

---

### Google Maps

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Directions API**
4. Go to **APIs & Services → Credentials**
5. Create API key
6. Add to `.env`:

```bash
ROUTING_PROVIDER=google
GOOGLE_MAPS_API_KEY=AIzaSyD...your-key-here
```

✅ **Advantages**: Most comprehensive data, traffic info  
💰 **Pricing**: $200 free credit/month, then $5 per 1000 requests

---

### MapMyIndia

1. Sign up at [https://www.mapmyindia.com/](https://www.mapmyindia.com/)
2. Go to **API Dashboard**
3. Generate API key
4. Add to `.env`:

```bash
ROUTING_PROVIDER=mapmyindia
MAPMYINDIA_API_KEY=your_api_key_here
```

✅ **Advantages**: Best for India, local traffic data  
💰 **Pricing**: Contact MapMyIndia for pricing

## Provider Fallback Chain

The system automatically tries providers in this order:

1. **Preferred provider** (set in `ROUTING_PROVIDER`)
2. **Other configured providers** (with valid API keys)
3. **OSRM** (always available as last resort)

Example: If you set `ROUTING_PROVIDER=mapbox` but the Mapbox API fails, the system will automatically try other configured providers, finally falling back to OSRM.

## Verifying Configuration

### Check Provider Status

Start the backend server:

```bash
cd c:\Users\Dell\Desktop\Margsathi\Margsathi\Margsathi
..\..\.venv\Scripts\python -m uvicorn backend.main:app --reload
```

Check the logs on startup:

```
INFO: Routing Provider Configuration:
INFO:   Mapbox: ✓ Configured
INFO:   Google Maps: ✗ No API key
INFO:   MapMyIndia: ✗ No API key
INFO:   OSRM: ✓ Available (no key required)
INFO:   Preferred Provider: mapbox
```

### Test Routing Endpoint

```bash
curl -X POST http://localhost:8000/api/routing/suggest \
  -H "Content-Type: application/json" \
  -d '{"source":"BTM Layout","destination":"MG Road","mode":"car"}'
```

Check the response for `_provider_used` field to see which provider was used.

## Security Best Practices

### ✅ DO:
- Store API keys in `.env` file
- Add `.env` to `.gitignore`
- Use environment variables in production
- Rotate API keys periodically
- Monitor API usage and costs

### ❌ DON'T:
- Hardcode API keys in source code
- Commit `.env` to version control
- Expose API keys in frontend code
- Share API keys publicly
- Use production keys in development

## Troubleshooting

### "All routing providers failed"

**Cause**: No providers are configured or all failed  
**Solution**: 
1. Check `.env` file exists and has valid keys
2. Restart backend server to reload environment
3. Check logs for specific provider errors

### "Mapbox API authentication failed"

**Cause**: Invalid or expired API key  
**Solution**: 
1. Verify API key in Mapbox dashboard
2. Check for extra spaces in `.env` file
3. Ensure key starts with `pk.` (public token)

### "Google Maps API request denied"

**Cause**: API not enabled or key restrictions  
**Solution**:
1. Enable Directions API in Google Cloud Console
2. Check API key restrictions (HTTP referrers, IP addresses)
3. Verify billing is enabled

### Rate Limit Errors

**Cause**: Exceeded provider's rate limits  
**Solution**:
1. System will automatically fallback to next provider
2. Consider upgrading API plan
3. Implement request caching (future enhancement)

## API Key Rotation

To rotate API keys without downtime:

1. Generate new API key from provider
2. Update `.env` with new key
3. Restart backend server
4. Verify routing works
5. Revoke old API key from provider dashboard

## Production Deployment

For production environments:

1. **Use environment variables** (not `.env` file)
2. **Set via hosting platform**:
   - Heroku: `heroku config:set MAPBOX_API_KEY=...`
   - AWS: Use Parameter Store or Secrets Manager
   - Docker: Pass via `-e` flag or docker-compose
3. **Enable monitoring** for API usage and errors
4. **Set up alerts** for rate limit warnings

## Support

For issues or questions:
- Check backend logs for detailed error messages
- Verify API keys are valid in provider dashboards
- Ensure `.env` file is properly formatted
- Test with OSRM first (no key required) to isolate issues
