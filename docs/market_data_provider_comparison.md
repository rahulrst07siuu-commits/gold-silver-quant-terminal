# Indian Commodity (MCX) Market Data Provider Comparison

This document provides an objective, institutional evaluation of officially documented Indian broker APIs and licensed data vendors providing live and historical market data for **MCX Gold and Silver futures**.

---

## 1. Provider Comparison Matrix

| Evaluation Dimension | **DhanHQ API v2** *(Recommended Primary)* | **Zerodha Kite Connect v3** *(Recommended Fallback)* | **Upstox API v2** | **TrueData / Global DataFeeds** (Licensed Vendor) |
| :--- | :--- | :--- | :--- | :--- |
| **MCX Gold Futures** | ✅ Full support (`MCX_COMM` segment) | ✅ Full support (`MCX` exchange) | ✅ Full support (`MCX_FO` segment) | ✅ Full support (Direct exchange feed) |
| **MCX Silver Futures** | ✅ Full support (SILVER, SILVERM, MIC) | ✅ Full support (SILVER, SILVERM, MIC) | ✅ Full support (SILVER, SILVERM, MIC) | ✅ Full support (SILVER, SILVERM, MIC) |
| **Live WebSocket Feed** | ✅ Binary WebSocket (Ticker, Quote, Depth) | ✅ Binary WebSocket (LTP, Quote, 5-Depth) | ✅ Protobuf Binary WebSocket | ✅ Ultra-low-latency TCP / WebSocket |
| **Historical Intraday Candles** | ✅ 1m, 5m, 15m, 60m (Hourly), Daily | ✅ 1m, 3m, 5m, 15m, 30m, 60m, Daily | ✅ 1m, 30m, Daily | ✅ Tick, 1m, 5m, 1h, Daily tick-level history |
| **API Subscription Cost** | **₹0 / Free** (for Dhan demat holders) | **₹2,000/mo** (Base) + **₹2,000/mo** (History) | ₹0 / Free for trading clients | ₹2,500 – ₹4,500/month |
| **Token Validity / Auth Flow** | **Long-lived JWT token** (30-day validity from web portal) | **Daily interactive login** (requires daily `request_token` exchange) | Daily OAuth2 token renewal | Vendor API key / static credentials |
| **Rate Limits** | 10 requests / second (Data APIs) | 3 requests / second (Strictly enforced) | 5 requests / second | Unthrottled or 50+ req/sec |
| **Market Depth (L2)** | 5-level market depth | 5-level market depth | 5-level market depth | Full 5-depth or 20-depth |
| **Quotation Convention** | Native MCX (Gold: ₹/10g, Silver: ₹/kg) | Native MCX (Gold: ₹/10g, Silver: ₹/kg) | Native MCX (Gold: ₹/10g, Silver: ₹/kg) | Native MCX |
| **Automated Background Ingestion** | **Exceptional** (ideal for headless servers/cron) | Moderate (requires automated Selenium/browser login for token) | Moderate (requires daily OAuth) | **Exceptional** (Server-grade continuous uptime) |

---

## 2. Selection Rationale & Recommendation

### **Primary Selection: DhanHQ API v2**
* **Cost Efficiency**: DhanHQ provides enterprise-grade historical and live WebSocket feeds **completely free of API subscription charges** for registered account holders.
* **Headless Background Scheduling**: Unlike Zerodha, which enforces a mandatory daily manual login via web browser to obtain a `request_token`, Dhan allows generating a secure, **long-lived access token** (valid up to 30 days) from the user portal. This enables persistent, unattended background cron jobs and scheduled data ingestion without breaking after 24 hours.
* **Full MCX Commodity Suite**: Native support for all active Gold contracts (`GOLD`, `GOLDM`, `GOLDPETAL`) and Silver contracts (`SILVER`, `SILVERM`, `SILVERMIC`) with live open interest and 5-depth order book.

### **Fallback Selection: Zerodha Kite Connect v3**
* Zerodha offers the most mature, liquid commodity developer ecosystem in India.
* When Kite credentials and historical API permissions are activated, the connector seamlessly routes to Kite REST endpoints (`/instruments/historical/{token}/60minute`).

### **Simulation / Fallback: Offline Mock & Staged Provider**
* For environments where real-time API keys have not yet been placed in `.env`, the system provides an automated **Mock & Continuous Historical Engine** that simulates live market updates, validates data quality, and ensures the forecasting pipeline operates continuously without interruption.

---

## 3. MCX Trading Hours & Schedule

* **Regular Trading Session**: Monday to Friday: `09:00 AM IST` to `11:30 PM IST` (or `11:55 PM IST` during US Daylight Saving Time).
* **Weekend & Exchange Holidays**: Saturday and Sunday closed. Exchange holidays published by MCX India.
* **Data Ingestion Schedule**: The automated scheduler executes ingestion runs every hour at `:02` minutes past the hour during open market sessions. Outside market hours, the scheduler idles to conserve system resources and prevent rate-limit penalties.
