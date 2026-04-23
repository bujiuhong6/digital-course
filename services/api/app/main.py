from fastapi import FastAPI

from .config import settings

app = FastAPI(title="Teaching API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, bool]:
    # 导入即校验配置可加载；避免静默使用错误环境
    _ = settings.database_url
    return {"ok": True}
