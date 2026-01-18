import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from zoneinfo import ZoneInfo
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplfinance as mpf
import io
import base64

# --- 設定目標 ---
target_tickers = ['SPY', 'QQQ', 'IWM']
ticker_names = {
    'SPY': '標普500 (SPY)',
    'QQQ': '納指100 (QQQ)',
    'IWM': '羅素2000 (IWM)'
}

# --- 參數 (小時線模式) ---
lookback = 126
bins_count = 70  # 維持高解析度
va_pct = 0.70

# --- 繪圖風格 ---
plt.style.use('dark_background')
mpf_style = mpf.make_mpf_style(base_mpf_style='nightclouds', rc={'axes.grid': False})

# --- HTML Template ---
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Volume Profile Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ background-color: #0d1117; color: #c9d1d9; font-family: 'Consolas', 'Monaco', monospace; padding: 20px; }}
        .card {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; margin-bottom: 20px; }}
        .header {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #30363d; padding-bottom: 5px; display: flex; justify-content: space-between; align-items: center; }}
        .green {{ color: #3fb950; }}
        .red {{ color: #ff7b72; }}
        .yellow {{ color: #d29922; }}
        .cyan {{ color: #58a6ff; }}
        .gray {{ color: #8b949e; }}
        .bold {{ font-weight: bold; }}
        .row {{ display: flex; justify-content: space-between; margin-bottom: 5px; }}
        .verdict {{ background-color: #161b22; border: 1px solid #8b949e; padding: 20px; margin-top: 30px; }}
        .verdict-title {{ font-size: 1.5em; text-align: center; margin-bottom: 15px; }}
        .update-time {{ color: #8b949e; font-size: 0.8em; text-align: center; margin-bottom: 20px; }}
        .chart-container {{ margin-top: 15px; text-align: center; border: 1px solid #30363d; }}
        .chart-img {{ max-width: 100%; height: auto; display: block; }}
        .small-tag {{ font-size: 0.8em; padding: 2px 6px; border-radius: 4px; border: 1px solid; }}
    </style>
</head>
<body>
    <div class="update-time">最後更新 (美東時間): {update_time}</div>
    {content}
</body>
</html>
"""

def generate_chart(df, lookback_slice, sma200_val, poc_price, val_price, vah_price, price_bins, vol_by_bin, bin_indices):
    fig = plt.figure(figsize=(10, 6), facecolor='#161b22')
    gs = fig.add_gridspec(1, 2,  width_ratios=(3, 1), left=0.05, right=0.95, wspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharey=ax1)

    # 繪製 K 線 (加上 warn_too_much_data 參數抑制警告)
    mpf.plot(lookback_slice, type='candle', style=mpf_style, ax=ax1, show_nontrading=False, datetime_format='%m-%d', warn_too_much_data=2000)
    
    if not np.isnan(sma200_val):
         ax1.axhline(y=sma200_val, color='gray', linestyle='--', linewidth=1, label='SMA200', alpha=0.7)

    ax1.axhline(y=poc_price, color='#d29922', linewidth=1.5, linestyle='-', label='POC')
    ax1.axhline(y=val_price, color='#3fb950', linewidth=1, linestyle='--', label='VAL')
    ax1.axhline(y=vah_price, color='#ff7b72', linewidth=1, linestyle='--', label='VAH')
    
    current_price = lookback_slice['Close'].iloc[-1]
    ax1.axhline(y=current_price, color='white', linewidth=0.8, linestyle=':')
    
    # 修正文字座標
    ax1.text(len(lookback_slice) + 1, current_price, f'{current_price:.2f}', color='white', va='center', fontsize=9)

    ax1.set_ylabel("Price")
    ax1.legend(fontsize='small', facecolor='#161b22', edgecolor='#30363d')

    is_in_va = (bin_indices >= bin_indices[price_bins == val_price][0]) & (bin_indices <= bin_indices[price_bins == vah_price][0])
    colors = np.where(is_in_va, '#58a6ff', '#30363d')
    poc_bin_idx = np.argmax(vol_by_bin)
    colors[poc_bin_idx] = '#d29922'

    ax2.barh(price_bins, vol_by_bin, height=(price_bins[1]-price_bins[0])*0.8, align='center', color=colors, edgecolor=None, alpha=0.8)
    ax2.set_xlabel("Volume")
    ax2.tick_params(left=False, labelleft=False)
    ax2.grid(False)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100, facecolor=fig.get_facecolor())
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64

def calculate_data(ticker):
    try:
        # --- 1. 日線數據 (Trend & ATR) ---
        df_daily = yf.download(ticker, period="2y", interval="1d", progress=False)
        if isinstance(df_daily.columns, pd.MultiIndex):
            df_daily.columns = df_daily.columns.get_level_values(0)
        
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in numeric_cols:
            if col in df_daily.columns:
                df_daily[col] = df_daily[col].astype(float)
        
        if len(df_daily) < 200: return None
        
        # 計算 SMA200
        sma200 = df_daily['Close'].rolling(window=200).mean().iloc[-1]
        current_price = df_daily['Close'].iloc[-1]
        is_bull_market = current_price > sma200

        # === ATR (14) 計算 ===
        prev_close = df_daily['Close'].shift(1)
        tr1 = df_daily['High'] - df_daily['Low']
        tr2 = (df_daily['High'] - prev_close).abs()
        tr3 = (df_daily['Low'] - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = tr.rolling(window=14).mean().iloc[-1]
        
        # 判斷恐慌日
        today_range = df_daily['High'].iloc[-1] - df_daily['Low'].iloc[-1]
        is_panic_day = today_range > (1.8 * atr_14)

        # --- 2. 小時線數據 (Volume Profile) ---
        df_hourly = yf.download(ticker, period="1y", interval="1h", progress=False)
        if isinstance(df_hourly.columns, pd.MultiIndex):
            df_hourly.columns = df_hourly.columns.get_level_values(0)
        for col in numeric_cols:
            if col in df_hourly.columns:
                df_hourly[col] = df_hourly[col].astype(float)
        if len(df_hourly) == 0: return None

        cutoff_date = df_hourly.index[-1] - pd.Timedelta(days=lookback)
        df_slice = df_hourly[df_hourly.index > cutoff_date].copy()
        
        # 使用 Typical Price
        price_slice = (df_slice['High'] + df_slice['Low'] + df_slice['Close']) / 3
        vol_slice = df_slice['Volume']
        
        min_p, max_p = price_slice.min(), price_slice.max()
        price_bins = np.linspace(min_p, max_p, bins_count)
        bin_indices = np.arange(bins_count)
        
        binned_indices_data = np.digitize(price_slice, price_bins)
        vol_by_bin = np.zeros(bins_count)
        for idx, vol in zip(binned_indices_data, vol_slice):
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

        # --- 訊號判定 ---
        is_below_val = current_price < val_price
        dist_pct = ((current_price - val_price) / current_price) * 100
        
        signal_code = 0
        action_html = ""
        status_html = ""
        color_class = ""
        
        trend_txt = "多頭" if is_bull_market else "空頭"
        trend_class = "green" if is_bull_market else "red"
        
        atr_status = "正常" if not is_panic_day else "劇烈(PANIC)"

        if is_below_val:
            if is_bull_market:
                if is_panic_day:
                    signal_code = 0 
                    color_class = "yellow"
                    action_html = "✋ 波動劇烈 (暫緩接刀)"
                    status_html = f"破 VAL 但 ATR 過熱 (震幅 {today_range:.2f} > {1.8*atr_14:.2f})"
                else:
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

        chart_base64 = generate_chart(df_hourly, df_slice, sma200, poc_price, val_price, vah_price, price_bins, vol_by_bin, bin_indices)

        return {
            'name': ticker_names[ticker],
            'ticker': ticker,
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
            'dist_pct': dist_pct,
            'chart_base64': chart_base64,
            'atr': atr_14,
            'atr_status': atr_status
        }

    except Exception as e:
        print(f"Error calculating {ticker}: {e}")
        return None

# --- 生成 HTML ---
cards_html = ""
market_signals = {}

for ticker in target_tickers:
    res = calculate_data(ticker)
    if res:
        market_signals[ticker] = res['signal_code']
        # 這裡的 dist_str 變數留著也沒關係，但我們在 HTML 中不再使用它顯示
        dist_str = f"{res['dist_pct']:+.2f}%"
        
        header_html = f"""
            <div class="header {res['color_class']}">
                <span>{res['name']}</span>
                <span class="small-tag {res['color_class']}" style="border-color: currentColor;">{res['ticker']}</span>
            </div>
        """
        
        # [修改] 移除現價旁邊的 ({dist_str}) 
        cards_html += f"""
        <div class="card">
            {header_html}
            <div class="row"><span>現價:</span> <span>{res['price']:.2f}</span></div>
            <div class="row"><span>POC:</span> <span>{res['poc']:.2f}</span></div>
            <div class="row"><span>VAL:</span> <span>{res['val']:.2f}</span></div>
            <div class="row"><span>趨勢:</span> <span class="{res['trend_class']}">{res['trend_txt']} (MA200: {res['sma200']:.0f})</span></div>
            <div class="row"><span>波動(ATR):</span> <span class="gray">{res['atr_status']} ({res['atr']:.2f})</span></div>
            <hr style="border: 0; border-top: 1px dashed #30363d;">
            <div class="row"><span>狀態:</span> <span class="{res['color_class']}">{res['status_html']}</span></div>
            <div class="row"><span>指令:</span> <span class="{res['color_class']} bold">{res['action_html']}</span></div>
            <div class="chart-container">
                <img class="chart-img" src="data:image/png;base64,{res['chart_base64']}" alt="{res['name']} Chart">
            </div>
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
    verdict_html = "😴 市場震盪 / 波動保護"
    verdict_class = "cyan"
    advice_html = "<ol><li>多看少做。</li><li>等待價格回到 VAL。</li><li>避開高波動日。</li></ol>"

final_html = html_template.format(
    update_time=datetime.datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %H:%M'),
    content=f"""
    {cards_html}
    <div class="verdict">
        <div class="verdict-title {verdict_class}">{verdict_html}</div>
        <div style="margin-left: 20px;">{advice_html}</div>
    </div>
    """
)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(final_html)

print("Main script updated successfully!")