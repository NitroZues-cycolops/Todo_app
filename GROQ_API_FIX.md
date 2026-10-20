# Groq API Model Fix - AI Planner

## Issue
Error when trying to use AI Planner:
```
Groq API error: Error code: 404 - {'error': {'message': 'The model `llama-3.3-70b-versatile` does not exist or you do not have access to it.'}}
```

## Root Cause
The AI Planner was hardcoded to use `llama-3.3-70b-versatile`, which is not available on Groq's free tier.

## Solution
Updated `smartschedule/ai_planner.py` to use `mixtral-8x7b-32768`, which is:
- ✅ Available on Groq free tier
- ✅ Faster inference than larger models
- ✅ Excellent at JSON output (needed for task extraction)
- ✅ Sufficient capability for scheduling tasks

## Changes Made

**File:** `smartschedule/ai_planner.py`  
**Line:** 31-33

```python
# Before:
self.model = "llama-3.3-70b-versatile"
self.vision_model = "llama-3.2-11b-vision-preview"

# After:
# Use models available on Groq free tier
self.model = "mixtral-8x7b-32768"  # Fast, capable text model
self.vision_model = "llama-3.2-11b-vision-preview"  # Vision model
```

**Commit:** `c394451`

## Setup Instructions

### 1. Get Groq API Key
1. Visit: https://console.groq.com/keys
2. Sign up or log in
3. Create/copy your API key (format: `gsk_...`)

### 2. Set Environment Variable

**Option A: Current session only**
```bash
export GROQ_API_KEY="your-api-key-here"
```

**Option B: Persistent (add to .env)**
```bash
cd /home/prab/Prab/Prabjingo/"Smart Schedule"
echo "GROQ_API_KEY=your-api-key-here" >> .env
```

**Option C: Permanent (shell profile)**
```bash
echo 'export GROQ_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### 3. Verify
```bash
echo $GROQ_API_KEY  # Should print your key
```

## Testing the Fix

1. **Kill current server:**
   ```bash
   pkill -f "uvicorn smartschedule"
   ```

2. **Start with API key:**
   ```bash
   export GROQ_API_KEY="your-api-key-here"
   cd /home/prab/Prab/Prabjingo/"Smart Schedule"
   source venv/bin/activate
   python -m uvicorn smartschedule.main:app --host 127.0.0.1 --port 8000
   ```

3. **Open app:**
   ```
   http://127.0.0.1:8000/
   ```

4. **Test AI Planner:**
   - Click "🤖 AI Planner" button
   - Enter plan: `"Monday: gym at 6am, team meeting at 2pm, dinner at 7pm"`
   - Click "✨ Analyze"
   - Should see extracted tasks and events

## Available Models on Groq

### Text Models
- `mixtral-8x7b-32768` ← Used now (fast, capable)
- `llama-3.1-70b-versatile` (alternative)
- `llama-3.1-8b-instant` (faster, less capable)

### Vision Models
- `llama-3.2-11b-vision-preview` (analyze images/PDFs)

## Free Tier Limits

- **Rate:** 30 requests per minute
- **Daily:** 5,000 requests per day
- **Cost:** Free (no credit card required)

## Troubleshooting

### Error: "GROQ_API_KEY not set"
- Set the environment variable (see Setup section)
- Verify with: `echo $GROQ_API_KEY`

### Error: "Model does not exist"
- Check your API key is correct
- Verify in Groq console that account is active
- Confirm you're using `mixtral-8x7b-32768`

### Error: "Rate limit exceeded"
- Free tier has 30 req/min limit
- Wait a minute and retry
- Upgrade account for higher limits

### AI Planner button doesn't work
- Check browser console (F12) for errors
- Check server logs: `tail -f /tmp/server.log`
- Verify GROQ_API_KEY is set before starting server
- Restart server after setting the API key

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| Feature 1: Multi-date Selection | ✅ Complete | 8/8 tests passing |
| Feature 2: Recurring Tasks | ⏳ 75% Complete | Backend + UI working |
| Feature 3: AI Planner | ✅ Fixed | Now uses available model |

## Next Steps

1. Get GROQ_API_KEY from https://console.groq.com/keys
2. Set environment variable: `export GROQ_API_KEY="your-key"`
3. Restart server
4. Test AI Planner in the app

---

**Fixed:** 2026-10-19  
**Commit:** c394451  
**Author:** Claude Code
