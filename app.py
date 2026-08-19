from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

import twstock
from twstock import BestFourPoint, Stock


SERVER_URL = "https://twstock-gpt-api.onrender.com"

app = FastAPI(
    title="台灣股票查詢與分析 API",
    description="使用 twstock 查詢台股行情、歷史資料及技術指標",
    version="2.0.0",
    servers=[{"url": SERVER_URL}],
)


def check_code(code: str):
    if code not in twstock.codes:
        raise HTTPException(
            status_code=404,
            detail="找不到這個台股代號",
        )


def convert_taiwan_time(timestamp):
    if not timestamp:
        return None

    return datetime.fromtimestamp(
        timestamp,
        tz=ZoneInfo("Asia/Taipei"),
    ).strftime("%Y-%m-%d %H:%M:%S")


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "台灣股票查詢與分析 API 正常運作",
        "version": "2.0.0",
    }


@app.get("/stock/{code}", operation_id="getTaiwanStock")
def get_stock(code: str):
    """查詢單一台股的最新行情，例如2330。"""

    check_code(code)

    result = twstock.realtime.get(code)

    if not result.get("success"):
        raise HTTPException(
            status_code=502,
            detail=result.get("rtmessage", "目前無法取得即時行情"),
        )

    info = result.get("info", {})
    realtime = result.get("realtime", {})

    return {
        "code": info.get("code"),
        "name": info.get("name"),
        "fullname": info.get("fullname"),
        "time": convert_taiwan_time(result.get("timestamp")),
        "timezone": "Asia/Taipei",
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


@app.get("/codes/{code}", operation_id="getTaiwanStockInformation")
def get_stock_information(code: str):
    """查詢股票名稱、市場、產業及上市日期。"""

    check_code(code)
    stock_info = twstock.codes[code]

    return {
        "type": stock_info.type,
        "code": stock_info.code,
        "name": stock_info.name,
        "isin": stock_info.ISIN,
        "listed_date": stock_info.start,
        "market": stock_info.market,
        "industry": stock_info.group,
        "cfi": stock_info.CFI,
        "data_source": stock_info.data_source,
    }


@app.get(
    "/history/{code}/{year}/{month}",
    operation_id="getTaiwanStockMonthlyHistory",
)
def get_monthly_history(code: str, year: int, month: int):
    """查詢指定年份與月份的每日歷史行情。"""

    check_code(code)

    if year < 2000 or year > 2100:
        raise HTTPException(status_code=400, detail="年份格式錯誤")

    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="月份必須介於1至12")

    stock = Stock(code, initial_fetch=False)
    data = stock.fetch(year, month)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="這個月份沒有查到交易資料",
        )

    return {
        "code": code,
        "name": twstock.codes[code].name,
        "year": year,
        "month": month,
        "records": [
            {
                "date": item.date.strftime("%Y-%m-%d"),
                "capacity": item.capacity,
                "turnover": item.turnover,
                "open": item.open,
                "high": item.high,
                "low": item.low,
                "close": item.close,
                "change": item.change,
                "transactions": item.transaction,
            }
            for item in data
        ],
        "source": "twstock / TWSE-TPEX",
    }


@app.get(
    "/analysis/{code}",
    operation_id="analyzeTaiwanStock",
)
def analyze_stock(
    code: str,
    short_days: int = 5,
    long_days: int = 10,
):
    """
    計算均價、均量、均線連續方向、乖離值及四大買賣點。
    預設使用5日與10日均線。
    """

    check_code(code)

    if short_days < 2 or long_days < 2:
        raise HTTPException(
            status_code=400,
            detail="均線天數至少必須為2日",
        )

    stock = Stock(code)

    if len(stock.data) < max(short_days, long_days):
        raise HTTPException(
            status_code=502,
            detail="歷史資料不足，無法計算",
        )

    price_ma = stock.moving_average(
        stock.price,
        short_days,
    )
    capacity_ma = stock.moving_average(
        stock.capacity,
        short_days,
    )
    bias_ratio = stock.ma_bias_ratio(
        short_days,
        long_days,
    )

    best_four_point = BestFourPoint(stock)
    buy_reason = best_four_point.best_four_point_to_buy()
    sell_reason = best_four_point.best_four_point_to_sell()

    if buy_reason:
        signal = "買進訊號"
        reason = buy_reason
    elif sell_reason:
        signal = "賣出訊號"
        reason = sell_reason
    else:
        signal = "沒有明確訊號"
        reason = None

    return {
        "code": code,
        "name": twstock.codes[code].name,
        "latest_trading_date": stock.date[-1].strftime(
            "%Y-%m-%d"
        ),
        "latest_close": stock.price[-1],
        "short_days": short_days,
        "long_days": long_days,
        "latest_short_moving_average": price_ma[-1],
        "latest_short_capacity_average": capacity_ma[-1],
        "moving_average_continuous_days": stock.continuous(
            price_ma
        ),
        "latest_bias_value": bias_ratio[-1],
        "best_four_point_signal": signal,
        "best_four_point_reason": reason,
        "recent_closing_prices": stock.price[-10:],
        "recent_volumes": stock.capacity[-10:],
        "notice": "四大買賣點僅為技術指標，不代表投資建議",
        "source": "twstock / TWSE-TPEX",
    }


@app.get(
    "/privacy",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def privacy():
    return """
    <html>
      <body>
        <h1>隱私權政策</h1>
        <p>本服務只接收股票代號及分析參數。</p>
        <p>本服務不要求或儲存姓名、帳號及金融資料。</p>
        <p>行情資料來源為 TWSE、TPEX 與 twstock。</p>
      </body>
    </html>
    """
