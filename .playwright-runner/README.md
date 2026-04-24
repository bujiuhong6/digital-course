# MVP 录屏

在仓库根执行：

1. 种子库（会写入 `/tmp/ai-python-teach-task11-demo.db`）  
   `PYTHONPATH=services/api python3 scripts/seed_task11_desktop_demo.py`

2. API（`JWT_SECRET` 须与 [tests/conftest.py](../services/api/tests/conftest.py) 中一致，否则学生登录为 401）  
   `cd services/api && DATABASE_URL=sqlite+aiosqlite:////tmp/ai-python-teach-task11-demo.db JWT_SECRET=test-jwt-secret-for-teacher-cookie-consistent-123 python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000`

3. 学生端静态预览  
   `cd apps/student-desktop && pnpm build && pnpm exec vite preview --host 127.0.0.1 --port 4173`

4. 安装依赖与浏览器后运行  
   `cd .playwright-runner && npm install && npx playwright install chromium && node record_mvp_features_demo.mjs`

输出为 `.webm`，默认目录：`./opt/cursor/artifacts`（相对本目录即 `workspace/opt/cursor/artifacts`）。
