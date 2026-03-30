<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/c93008a6-9adb-4196-a0ac-22e602fbc4f9

## Run Locally

**Prerequisites:**  Node.js


1. Install backend dependencies:
   `cd backend && pip install -r requirements.txt`
   - 已修复：`supabase` 包会引起 Windows pyiceberg 编译异常，已改为 `supabase-py`。
2. Install frontend dependencies:
   `npm install`
3. Set the required environment variables in `.env`:
   - `SUPABASE_URL` - Your Supabase project URL
   - `SUPABASE_KEY` - Your Supabase API key
   - `LLM_API_BASE` - LLM API endpoint (default: https://api.deepseek.com/v1)
   - `LLM_API_KEY` - Your LLM API key (e.g., DeepSeek API key)
   - `LLM_MODEL` - Model name (default: deepseek-chat)
4. Run the app:
   后端：`cd backend && python -m uvicorn main:app --reload --port 8000`
   前端：`npm run dev`
