from flask import Flask, render_template, request, jsonify, send_file
import requests, io, csv, time
from fpdf import FPDF
import yfinance as yf

app = Flask(__name__)

crypto_portfolio = []
stock_portfolio = []

COINS = [
    ("bitcoin", "BTC", "Bitcoin"),
    ("ethereum", "ETH", "Ethereum"),
    ("cardano", "ADA", "Cardano"),
    ("dogecoin", "DOGE", "Dogecoin"),
    ("solana", "SOL", "Solana")
]

STOCKS = [
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("GOOGL", "Alphabet"),
    ("AMZN", "Amazon"),
    ("TSLA", "Tesla")
]

def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0

def fetch_crypto_price(id_):
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={id_}&vs_currencies=usd", timeout=10)
        j = r.json()
        return j.get(id_, {}).get("usd", 0.0)
    except:
        return 0.0

def fetch_crypto_ohlc(id_, days=14):
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/coins/{id_}/ohlc?vs_currency=usd&days={days}", timeout=15)
        data = r.json()
        candles = []
        for d in data:
            ts = int(d[0])
            candles.append({"x": ts, "o": round(d[1], 2), "h": round(d[2], 2), "l": round(d[3], 2), "c": round(d[4], 2)})
        return candles
    except:
        return []

def fetch_stock_ohlc(symbol, period="14d", interval="1d"):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=period, interval=interval)
        candles = []
        for dt, row in hist.iterrows():
            ts = int(dt.timestamp() * 1000)
            candles.append({"x": ts, "o": round(row["Open"], 2), "h": round(row["High"], 2), "l": round(row["Low"], 2), "c": round(row["Close"], 2)})
        return candles
    except:
        return []

@app.route("/")
def index():
    return render_template("index.html", coins=COINS, stocks=STOCKS)

@app.route("/api/portfolio")
def api_portfolio():
    for c in crypto_portfolio:
        c["price"] = fetch_crypto_price(c["id"])
        c["value"] = round(c["price"] * safe_float(c.get("quantity", 0)), 2)
    for s in stock_portfolio:
        try:
            ticker = yf.Ticker(s["symbol"])
            price = ticker.history(period="1d")["Close"].iloc[-1]
        except:
            price = safe_float(s.get("price", 0))
        s["price"] = round(price, 2)
        s["value"] = round(s["price"] * safe_float(s.get("quantity", 0)), 2)
    return jsonify({"crypto": crypto_portfolio, "stocks": stock_portfolio, "timestamp": int(time.time())})

@app.route("/api/add_crypto", methods=["POST"])
def api_add_crypto():
    j = request.json or {}
    id_ = j.get("id")
    symbol = j.get("symbol")
    name = j.get("name") or symbol
    qty = safe_float(j.get("quantity", 0))
    avg = safe_float(j.get("avgCost", 0))
    if not id_ or qty <= 0:
        return jsonify({"error": "invalid"}), 400
    existing = next((x for x in crypto_portfolio if x.get("id") == id_), None)
    if existing:
        existing_qty = existing.get("quantity", 0)
        total_qty = existing_qty + qty
        existing["avgCost"] = round(((existing.get("avgCost", 0) * existing_qty) + avg * qty) / max(1, total_qty), 2)
        existing["quantity"] = total_qty
    else:
        crypto_portfolio.append({"id": id_, "symbol": symbol, "name": name, "quantity": qty, "avgCost": avg, "price": 0.0, "value": 0.0})
    return jsonify({"ok": True})

@app.route("/api/add_stock", methods=["POST"])
def api_add_stock():
    j = request.json or {}
    symbol = j.get("symbol")
    name = j.get("name") or symbol
    qty = safe_float(j.get("quantity", 0))
    avg = safe_float(j.get("avgCost", 0))
    if not symbol or qty <= 0:
        return jsonify({"error": "invalid"}), 400
    existing = next((x for x in stock_portfolio if x.get("symbol") == symbol), None)
    if existing:
        existing_qty = existing.get("quantity", 0)
        total_qty = existing_qty + qty
        existing["avgCost"] = round(((existing.get("avgCost", 0) * existing_qty) + avg * qty) / max(1, total_qty), 2)
        existing["quantity"] = total_qty
    else:
        stock_portfolio.append({"symbol": symbol, "name": name, "quantity": qty, "avgCost": avg, "price": 0.0, "value": 0.0})
    return jsonify({"ok": True})

@app.route("/api/remove_crypto/<id_>", methods=["POST"])
def api_remove_crypto(id_):
    global crypto_portfolio
    crypto_portfolio = [c for c in crypto_portfolio if c.get("id") != id_]
    return jsonify({"ok": True})

@app.route("/api/remove_stock/<symbol>", methods=["POST"])
def api_remove_stock(symbol):
    global stock_portfolio
    stock_portfolio = [s for s in stock_portfolio if s.get("symbol") != symbol]
    return jsonify({"ok": True})

@app.route("/api/crypto_ohlc/<id_>")
def api_crypto_ohlc(id_):
    data = fetch_crypto_ohlc(id_, days=14)
    return jsonify({"data": data})

@app.route("/api/stock_ohlc/<symbol>")
def api_stock_ohlc(symbol):
    data = fetch_stock_ohlc(symbol, period="14d", interval="1d")
    return jsonify({"data": data})

def generate_csv(data, headers):
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(headers)
    for r in data:
        cw.writerow([r.get(h, "") for h in headers])
    b = io.BytesIO()
    b.write(si.getvalue().encode("utf-8"))
    b.seek(0)
    return b

def generate_pdf(title, data, headers):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", size=10)
    for h in headers:
        pdf.cell(32, 8, h[:14], 1)
    pdf.ln()
    for row in data:
        for h in headers:
            pdf.cell(32, 8, str(row.get(h, ""))[:30], 1)
        pdf.ln()
    out = io.BytesIO()
    pdf.output(out)
    out.seek(0)
    return out

@app.route("/download/<string:type_>/csv")
def download_csv(type_):
    if type_ == "stocks":
        data = stock_portfolio
        headers = ["name", "symbol", "quantity", "avgCost", "price", "value"]
    else:
        data = crypto_portfolio
        headers = ["name", "symbol", "id", "quantity", "avgCost", "price", "value"]
    return send_file(generate_csv(data, headers), mimetype="text/csv", as_attachment=True, download_name=f"{type_}_portfolio.csv")

@app.route("/download/<string:type_>/pdf")
def download_pdf(type_):
    if type_ == "stocks":
        data = stock_portfolio
        headers = ["name", "symbol", "quantity", "avgCost", "price", "value"]
        title = "Stocks Portfolio"
    else:
        data = crypto_portfolio
        headers = ["name", "symbol", "id", "quantity", "avgCost", "price", "value"]
        title = "Coins Portfolio"
    return send_file(generate_pdf(title, data, headers), mimetype="application/pdf", as_attachment=True, download_name=f"{type_}_portfolio.pdf")

if __name__ == "__main__":
    app.run(debug=True)
