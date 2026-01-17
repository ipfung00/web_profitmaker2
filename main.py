import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import os

# --- 設定目標 ---
target_tickers = ['SPY', 'QQQ', 'IWM']
ticker_names = {
    'SPY': '標普500 (SPY)',
    'QQQ': '納指100 (QQQ)',
    'IWM': '羅素2000 (IWM)'
}

# --- 參數 ---
lookback = 126
bins_count = 70
va_pct = 0.70

# --- CSS 樣式 (模仿終端機) ---
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Volume Profile Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ background-color: #0d1117; color: #c9d1d9; font-family: 'Consolas', 'Monaco', monospace; padding: 20px; }}
        .card {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; margin-bottom: 20px; }}
        .header {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #30363d; padding-bottom: 5px; }}
        .green {{ color: #3fb950; }}
        .red {{ color: #ff7b72; }}
        .yellow {{ color: #d29922; }}
        .cyan {{ color: #58a6ff; }}
        .bold {{ font-weight: bold; }}
        .row {{ display: flex; justify-content: space-between; margin-bottom: 5px; }}
        .verdict {{ background-color: #161b22; border: 1px solid #8b949e; padding: 20px; margin-top: 30px; }}
        .verdict-title {{ font-size: 1.5em; text-align: center; margin-bottom: 15px; }}
        .update-time {{ color: #8b949e; font-size: 0.8em; text-align: center; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="update-time">最後更新 (UTC): {update_time}</div>
    {content}
</body>
</html>
"""

def calculate_data(ticker):
    try:
        df = yf.download(ticker, period="2y", interval="1d", progress=False)
        if len(df) < 200: return None
        
        close = df['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        volume = df['Volume']
        if isinstance(volume, pd.DataFrame): volume = volume.iloc[:, 0]
        
        sma200 = close.rolling(window=200).mean().iloc[-1]
        current_price = close.iloc[-1]
        
        price_slice = close.iloc[-lookback:]
        vol_slice = volume.iloc[-lookback:]
        
        min_p, max_p = price_slice.min(), price_slice.max()
        price_bins = np.linspace(min_p, max_p, bins_count)
        binned_indices = np.digitize(price_slice, price_bins)
        
        vol_by_bin = np.zeros(bins_count)
        for idx, vol in zip(binned_indices, vol_slice):
            if 0 <= idx < bins_count: vol_by_bin[idx] += vol
            
        poc_idx = np.argmax(vol_by_bin)
        total_vol = vol_by_bin.sum()
        target_vol = total_vol * va_pct
        current_vol = vol_by_bin[poc_idx]
        
        upper, lower = poc_idx, poc_idx
        while current_vol < target_vol:
            v_up = vol_by_bin[upper+1] if upper < bins_count-1 else 0
            v_down = vol_by_bin[lower-1] if lower > 0 else 0
            if v_up == 0 and v_down == 0: break
            if v_up > v_down:
                upper += 1
                current_vol += v_up
            else:
                lower -= 1
                current_vol += v_down
                
        val_price = price_bins[lower]
        vah_price = price_bins[upper]
        poc_price = price_bins[poc_idx]

        is_below_val = current_price < val_price
        is_bull_market = current_price > sma200
        dist_pct = ((current_price - val_price) / current_price) * 100
        
        signal_code = 0
        action_html = ""
        status_html = ""
        color_class = ""
        
        if is_below_val:
            if is_bull_market:
                signal_code = 1
                color_class = "green"
                action_html = "★ 強力買進 (Buy Dip)"
                status_html = f"超賣回調 (破 VAL {abs(dist_pct):.2f}%)"
            else:
                signal_code = -1
                color_class = "red"
                action_html = "▼ 放空追殺 (Short)"
                status_html = f"籌碼潰散 (破 VAL {abs(dist_pct):.2f}%)"
        elif current_price > val_price and current_price < vah_price:
            signal_code = 0
            color_class = "yellow"
            action_html = "觀望 / 區間操作"
            status_html = f"價值區震盪 (距 VAL {dist_pct:.2f}%)"
        else: 
            signal_code = 2
            color_class = "cyan"
            action_html = "強勢持有"
            status_html = f"多頭強勢區 (距 VAL {dist_pct:.2f}%)"

        trend_txt = "多頭" if is_bull_market else "空頭"
        trend_class = "green" if is_bull_market else "red"

        return {
            'name': ticker_names[ticker],
            'price': current_price,
            'poc': poc_price,
            'val': val_price,
            'sma200': sma200,
            'trend_txt': trend_txt,
            'trend_class': trend_class,
            'status_html': status_html,
            'action_html': action_html,
            'color_class': color_class,
            'signal_code': signal_code,
            'dist_pct': dist_pct
        }

    except Exception as e:
        return None

# --- 生成 HTML ---
cards_html = ""
market_signals = {}

for ticker in target_tickers:
    res = calculate_data(ticker)
    if res:
        market_signals[ticker] = res['signal_code']
        dist_str = f"{res['dist_pct']:+.2f}%"
        
        cards_html += f"""
        <div class="card">
            <div class="header {res['color_class']}">{res['name']}</div>
            <div class="row"><span>現價:</span> <span>{res['price']:.2f} <span class="{res['color_class']}">({dist_str})</span></span></div>
            <div class="row"><span>POC:</span> <span>{res['poc']:.2f}</span></div>
            <div class="row"><span>VAL:</span> <span>{res['val']:.2f}</span></div>
            <div class="row"><span>趨勢:</span> <span class="{res['trend_class']}">{res['trend_txt']} (MA200: {res['sma200']:.0f})</span></div>
            <hr style="border: 0; border-top: 1px dashed #30363d;">
            <div class="row"><span>狀態:</span> <span class="{res['color_class']}">{res['status_html']}</span></div>
            <div class="row"><span>指令:</span> <span class="{res['color_class']} bold">{res['action_html']}</span></div>
        </div>
        """

# 總結邏輯
s_spy = market_signals.get('SPY', 0)
s_qqq = market_signals.get('QQQ', 0)
s_iwm = market_signals.get('IWM', 0)

verdict_html = ""
verdict_class = ""
advice_html = ""

if s_spy == -1 and s_qqq == -1 and s_iwm == -1:
    verdict_html = "🚨 崩盤警報：系統性殺盤"
    verdict_class = "red"
    advice_html = "<ol><li>清空多單，現金為王。</li><li>反手做空 IWM。</li><li>不要接刀。</li></ol>"
elif s_iwm == -1 and (s_qqq >= 0 or s_spy >= 0):
    verdict_html = "⚠️ 變盤預警：金絲雀已死"
    verdict_class = "yellow"
    advice_html = "<ol><li>市場風險急升。</li><li>縮緊科技股止損。</li><li>禁止加倉。</li></ol>"
elif s_spy == 1 and s_qqq == 1:
    verdict_html = "🔥 黃金機會：完美回調"
    verdict_class = "green"
    advice_html = "<ol><li>大膽買進 QQQ 與 SPY。</li><li>設定今日低點為防守。</li><li>勝率極高。</li></ol>"
elif s_qqq == 1 and s_iwm >= 0:
    verdict_html = "✅ 科技股上車機會"
    verdict_class = "green"
    advice_html = "<ol><li>IWM 未死，良性回調。</li><li>分批承接 QQQ。</li></ol>"
else:
    verdict_html = "😴 市場震盪：無訊號"
    verdict_class = "cyan"
    advice_html = "<ol><li>多看少做。</li><li>等待價格回到 VAL。</li><li>保持耐心。</li></ol>"

final_html = html_template.format(
    update_time=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M'),
    content=f"""
    {cards_html}
    <div class="verdict">
        <div class="verdict-title {verdict_class}">{verdict_html}</div>
        <div style="margin-left: 20px;">{advice_html}</div>
    </div>
    """
)

# 輸出到 index.html
with open("index.html", "w", encoding="utf-8") as f:
    f.write(final_html)

print("HTML 生成完畢")
