# Mapbox Routing Configuration - Quick Start Guide

## ✅ Configuration Complete!

Your `.env` file has been updated to use Mapbox as the primary routing provider.

### Current Configuration:

```bash
ROUTING_PROVIDER=mapbox
MAPBOX_API_KEY=pk.eyJ1IjoidGVqYTEyMzQ1Njc4IiwiYSI6ImNtam55Y2pieDBpbW4zY3NkMThydWY1YXcifQ.m_RPJfnP6TEgRI0tiZTnmw
```

## 🔄 Restart Backend Server

To apply the changes, you need to restart the backend server:

### Step 1: Stop the Current Server

In the terminal running the backend (usually showing uvicorn logs):
1. Press `Ctrl + C` to stop the server

### Step 2: Restart the Server

Run this command:
```bash
cd c:\Users\Dell\Desktop\Margsathi\Margsathi\Margsathi
..\..\.venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Verify Mapbox is Active

After restart, you should see in the logs:
```
INFO: Routing Provider Configuration:
INFO:   Mapbox: ✓ Configured
INFO:   Google Maps: ✗ No API key
INFO:   MapMyIndia: ✗ No API key
INFO:   OSRM: ✓ Available (no key required)
INFO:   Preferred Provider: mapbox
```

## 🧪 Test Mapbox Routing

### Option 1: Use the Web Interface

1. Open http://localhost:3000/routing
2. Enter any two locations:
   - Source: "Koramangala"
   - Destination: "Whitefield"
3. Wait 2.5 seconds
4. The route will be calculated using **Mapbox Directions API**

### Option 2: Test via API

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/routing/suggest" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"source":"BTM Layout","destination":"MG Road","mode":"car"}' `
  | Select-Object -ExpandProperty Content | ConvertFrom-Json
```

Look for `"_provider_used": "mapbox"` in the response to confirm Mapbox is being used.

### Option 3: Check Provider Status

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/routing/providers/status" `
  -Method GET `
  | Select-Object -ExpandProperty Content | ConvertFrom-Json
```

Should show:
```json
{
  "configured_providers": ["mapbox", "osrm"],
  "preferred_provider": "mapbox",
  "fallback_chain": ["mapbox", "osrm"]
}
```

## 🎯 What Changed?

### Before (OSRM):
- Provider: OSRM (free, public server)
- Accuracy: Good
- Coverage: Global
- Rate Limits: Shared public server

### After (Mapbox):
- Provider: Mapbox Directions API v5
- Accuracy: **Excellent** (premium routing engine)
- Coverage: Global with traffic data
- Rate Limits: 100,000 requests/month (free tier)
- Features:
  - ✅ Real-time traffic consideration
  - ✅ More accurate ETAs
  - ✅ Better route optimization
  - ✅ Turn-by-turn navigation
  - ✅ Alternative routes

## 🔍 How to Verify It's Working

After restarting the backend, check the route response:

### Mapbox Response Indicators:

1. **Geometry Format**: GeoJSON (more detailed)
2. **Provider Metadata**: `"_provider_used": "mapbox"`
3. **Better Accuracy**: More precise coordinates
4. **Traffic Data**: Routes may differ from OSRM based on current traffic

### Example Mapbox Response:

```json
{
  "recommended_route": "BTM Layout → Richmond Road → MG Road",
  "distance_km": 6.8,
  "duration_minutes": 12.5,
  "geometry": "...",  // GeoJSON format from Mapbox
  "steps": [...],     // Detailed turn-by-turn from Mapbox
  "_provider_used": "mapbox"  // ← Confirms Mapbox is being used
}
```

## 🛡️ Fallback Behavior

If Mapbox fails (rate limit, network issue, etc.), the system will automatically fall back to OSRM:

```
1. Try Mapbox → Failed (rate limit)
2. Try OSRM → Success ✅
3. Return route from OSRM
```

You'll see in logs:
```
INFO: Attempting route with provider: mapbox
WARNING: Mapbox API rate limit exceeded, trying next
INFO: Attempting route with provider: osrm
INFO: Route successfully retrieved from osrm
```

## 📊 Monitoring API Usage

### Check Mapbox Dashboard:

1. Go to [https://account.mapbox.com/](https://account.mapbox.com/)
2. Navigate to **Statistics**
3. View **Directions API** usage
4. Monitor requests to stay within free tier (100k/month)

### Free Tier Limits:

- **100,000 requests/month** = ~3,300 requests/day
- Resets monthly
- Overage: $0.50 per 1,000 requests

## 🚀 Next Steps

1. **Restart the backend server** (see Step 1-2 above)
2. **Test a route** in the web interface
3. **Verify Mapbox is active** by checking logs or API response
4. **Enjoy better routing!** 🎉

## 🔧 Troubleshooting

### Issue: Still using OSRM after restart

**Solution**: 
- Verify `.env` file has `ROUTING_PROVIDER=mapbox`
- Check backend logs for "Mapbox: ✓ Configured"
- Ensure you restarted the server (not just refreshed browser)

### Issue: "Mapbox API authentication failed"

**Solution**:
- Verify API key in `.env` is correct
- Check key starts with `pk.`
- Ensure no extra spaces in `.env` file
- Verify key is active in Mapbox dashboard

### Issue: Routes look the same as before

**Solution**:
- Mapbox and OSRM may return similar routes for simple paths
- Try a longer route (e.g., "Electronic City" → "Hebbal")
- Check `_provider_used` field in response to confirm provider
- Routes may differ more during peak traffic hours

## 📝 Summary

✅ **Configuration Updated**: `.env` now uses Mapbox  
✅ **API Key Verified**: Valid Mapbox access token configured  
⏳ **Action Required**: Restart backend server  
🎯 **Expected Result**: All routes will use Mapbox Directions API  
🔄 **Fallback**: Automatic fallback to OSRM if Mapbox fails  

**Your system is ready for premium Mapbox routing!**
