from fastapi import FastAPI, HTTPException
import twstock

app = FastAPI(
    title="台灣股票查詢 API",
    description="使用 twstock 查詢台灣股票即時資訊",
    version="1.0.0",
)


@app.get("/")
def home():
    return {"status": "ok", "message": "twstock API 正常運作"}


@app.get("/stock/{code}", operation_id="getTaiwanStock")
def get_stock(code: str):
    """查詢台灣股票即時資訊，例如：2330。"""

    if code not in twstock.codes:
        raise HTTPException(status_code=404, detail="找不到這個股票代號")

    result = twstock.realtime.get(code)

    if not result.get("success"):
        raise HTTPException(
            status_code=502,
            detail=result.get("rtmessage", "目前無法取得股票資料"),
        )

    info = result.get("info", {})
    realtime = result.get("realtime", {})

    return {
        "code": info.get("code"),
        "name": info.get("name"),
        "fullname": info.get("fullname"),
        "time": info.get("time"),
        "latest_trade_price": realtime.get("latest_trade_price"),
        "open": realtime.get("open"),
        "high": realtime.get("high"),
        "low": realtime.get("low"),
        "trade_volume": realtime.get("trade_volume"),
        "accumulate_trade_volume": realtime.get(
            "accumulate_trade_volume"
        ),
        "best_bid_price": realtime.get("best_bid_price"),
        "best_ask_price": realtime.get("best_ask_price"),
        "source": "twstock / TWSE-TPEX",
    }
