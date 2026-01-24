import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from zoneinfo import ZoneInfo
import os
import matplotlib
matplotlib.use('Agg') # 設定後端為非互動模式
import matplotlib.pyplot as plt
import mplfinance as mpf
import io
import base64

# ==========================================
# 0. 系統設定
# ==========================================
# 解決負號顯示問題
plt.rcParams['axes.unicode_minus'] = False 

# ==========================================
# 1. 策略參數 (Final God Mode)
# ==========================================
target_tickers = ['SPY', 'QQQ', 'IWM']
ticker_names = {
    'SPY': '標普500 (SPY)',
    'QQQ': '納指100 (QQQ)',
    'IWM': '羅素2000 (IWM)'
}

# --- 核心參數：根據掃描結果 (ROI +1142%) ---
lookback_days = 69    # ✅ 黃金週期
bins_count = 37       # ✅ 最佳解析度
va_pct = 0.70         

# --- 繪圖風格 ---
plt.style.use('dark_background')
mpf_style = mpf.make_mpf_style(base_mpf_style='nightclouds', rc={'axes.grid': False})

# ==========================================
# 2. HTML 模板
# ==========================================
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Quant Trading Dashboard (Final Logic)</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ background-color: #0d1117; color: #c9d1d9; font-family: 'Microsoft JhengHei', 'Consolas', sans-serif; padding: 20px; }}
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
        .verdict-title {{ font-size: 1.5em; text-align: center; margin-bottom: 15px; font-weight: bold; }}
        .update-time {{ color: #8b949e; font-size: 0.8em; text-align: center; margin-bottom: 20px; }}
        .chart-container {{ margin-top: 15px; text-align: center; border: 1px solid #30363d; }}
        .chart-img {{ max-width: 100%; height: auto; display: block; }}
        .tag {{ font-size: 0.8em; padding: 2px 6px; border-radius: 4px; border: 1px solid; }}
        
        .maintenance-box {{ margin-top: 40px; padding: 15px; border-top: 1px solid #30363d; font-size: 0.9em; text-align: center; }}
        .m-alert {{ color: #ff7b72; border: 1px solid #ff7b72; padding: 10px; border-radius: 6px; background-color: rgba(255, 123, 114, 0.1); }}
        .m-normal {{ color: #8b949e; }}
    </style>
</head>
<body>
    <div class="update-time">最後更新 (美東時間): {update_time}</div>
    <div style="text-align: center; margin-bottom: 20px; font-size: 0.9em; color: #8b949e;">
        策略核心：POC 確保機制 (Hold the Line) | 參數: Lookback 69 / Bins 37
    </div>
    
    {content}

    <div class="maintenance-box">
        <div class="{m_class}">
            🔧 系統維護提示: {m_msg}
        </div>
    </div>
</body>
</html>
"""

# ==========================================
# 3. 繪圖函數 (標籤改為英文)
# ==========================================
def generate_chart(df_hourly, lookback_slice, sma200_val, poc_price, val_price, vah_price, price_bins, vol_by_bin, bin_indices):
    fig = plt.figure(figsize=(10, 6), facecolor='#161b22')
    gs = fig.add_gridspec(1, 2,  width_ratios=(3, 1), left=0.05, right=0.95, wspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharey=ax1)

    # 動態顯示 Lookback 週期
    days_to_show = lookback_days + 1
    cutoff_plot = lookback_slice.index[-1] - pd.Timedelta(days=days_to_show)
    plot_slice = lookback_slice[lookback_slice.index > cutoff_plot]

    mpf.plot(plot_slice, type='candle', style=mpf_style, ax=ax1, show_nontrading=False, datetime_format='%m-%d')
    
    # 關鍵線位 (使用英文標籤，避免方塊亂碼)
    if not np.isnan(sma200_val):
         ax1.axhline(y=sma200_val, color='gray', linestyle='--', linewidth=1, label='SMA200', alpha=0.7)

    ax1.axhline(y=poc_price, color='#d29922', linewidth=1.5, linestyle='-', label='POC', alpha=0.9)
    ax1.axhline(y=val_price, color='#3fb950', linewidth=1, linestyle='--', label='VAL', alpha=0.9)
    ax1.axhline(y=vah_price, color='#ff7b72', linewidth=1, linestyle='--', label='VAH', alpha=0.9)
    
    # 現價
    current_price = lookback_slice['Close'].iloc[-1]
    ax1.axhline(y=current_price, color='white', linewidth=0.8, linestyle=':')
    ax1.text(len(plot_slice) + 2, current_price, f'{current_price:.2f}', color='white', va='center', fontsize=9)

    ax1.set_ylabel("Price")
    ax1.legend(fontsize='small', facecolor='#161b22', edgecolor='#30363d')

    # 籌碼分佈
    is_in_va = (bin_indices >= bin_indices[price_bins == val_price][0]) & (bin_indices <= bin_indices[price_bins == vah_price][0])
    colors = np.where(is_in_va, '#58a6ff', '#30363d')
    poc_bin_idx = np.argmax(vol_by_bin)
    colors[poc_bin_idx] = '#d29922' 

    ax2.barh(price_bins, vol_by_bin, height=(price_bins[1]-price_bins[0])*0.8, align='center', color=colors, alpha=0.8)
    ax2.axis('off') 

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100, facecolor=fig.get_facecolor())
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64

# ==========================================
# 4. 核心運算 (Final Logic Engine)
# ==========================================
def calculate_data(ticker):
    try:
        df_daily = yf.download(ticker, period="2y", interval="1d", progress=False)
        if isinstance(df_daily.columns, pd.MultiIndex): df_daily.columns = df_daily.columns.get_level_values(0)
        
        if len(df_daily) < 200: return None
        sma200 = df_daily['Close'].rolling(window=200).mean().iloc[-1]
        current_price = df_daily['Close'].iloc[-1]
        is_bull_market = current_price > sma200
        
        df_hourly = yf.download(ticker, period="730d", interval="1h", progress=False)
        if isinstance(df_hourly.columns, pd.MultiIndex): df_hourly.columns = df_hourly.columns.get_level_values(0)
        
        if len(df_hourly) == 0: return None

        cutoff = df_hourly.index[-1] - pd.Timedelta(days=lookback_days)
        df_slice = df_hourly[df_hourly.index > cutoff].copy()
        
        p_slice = (df_slice['High'] + df_slice['Low'] + df_slice['Close']) / 3
        v_slice = df_slice['Volume']
        
        min_p, max_p = p_slice.min(), p_slice.max()
        bins = np.linspace(min_p, max_p, bins_count)
        vol_bin = np.zeros(bins_count)
        
        for idx, v in zip(np.digitize(p_slice, bins), v_slice):
            if 0 <= idx < bins_count: vol_bin[idx] += v
            
        poc_idx = np.argmax(vol_bin)
        target_v = vol_bin.sum() * va_pct
        curr_v, up, low = vol_bin[poc_idx], poc_idx, poc_idx
        while curr_v < target_v:
            v_u = vol_bin[up+1] if up < bins_count-1 else 0
            v_d = vol_bin[low-1] if low > 0 else 0
            if v_u == 0 and v_d == 0: break
            if v_u > v_d: up += 1; curr_v += v_u
            else: low -= 1; curr_v += v_d
                
        val_price, vah_price, poc_price = bins[low], bins[up], bins[poc_idx]

        dist_pct_poc = ((current_price - poc_price) / current_price) * 100
        dist_pct_val = ((current_price - val_price) / current_price) * 100 
        
        signal_code = 0
        action_html = ""
        status_html = ""
        color_class = ""
        
        if not is_bull_market:
            signal_code = -1
            color_class = "red"
            action_html = "▼ 清倉離場 (Bear Market)"
            status_html = f"價格 ({current_price:.2f}) 跌破年線 ({sma200:.2f})。"
        else:
            if current_price < val_price:
                signal_code = 1
                color_class = "green"
                action_html = "★ 強力抄底 (Dip Buy)"
                status_html = "價格回調至價值區下緣 (VAL)。<br>勝率最高點，買入並持有。"
            elif current_price > poc_price:
                signal_code = 2
                color_class = "cyan"
                action_html = "▲ 強勢買進/續抱 (Reclaim)"
                status_html = "價格站上 POC 分水嶺。<br>多頭強勢區，確保拎貨在手。"
            else:
                signal_code = 0
                color_class = "yellow"
                action_html = "⚠️ 關鍵決策 (Check POC)"
                status_html = f"位於震盪區間 (VAL < P < POC)。<br>"
                status_html += f"1. 若剛<b>跌破 POC</b>: <span class='red'>應已離場 (獲利了結)</span><br>"
                status_html += f"2. 若從<b>底部上來</b>: <span class='green'>續抱 (目標 POC)</span>"

        chart_base64 = generate_chart(df_hourly, df_slice, sma200, poc_price, val_price, vah_price, bins, vol_bin, np.arange(bins_count))

        return {
            'name': ticker_names[ticker], 'ticker': ticker, 'price': current_price,
            'poc': poc_price, 'val': val_price, 'sma200': sma200,
            'dist_pct_val': dist_pct_val, 
            'status_html': status_html, 'action_html': action_html, 'color_class': color_class,
            'signal_code': signal_code, 'dist_pct': dist_pct_poc, 'chart_base64': chart_base64
        }
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return None

# ==========================================
# 5. 生成 HTML
# ==========================================
cards_html = ""
market_signals = {}

for ticker in target_tickers:
    res = calculate_data(ticker)
    if res:
        market_signals[ticker] = res['signal_code']
        header = f'<div class="header {res["color_class"]}"><span>{res["name"]}</span><span class="tag {res["color_class"]}" style="border-color: currentColor;">{res["ticker"]}</span></div>'
        
        cards_html += f"""
        <div class="card">
            {header}
            <div class="row"><span>現價:</span> <span>{res['price']:.2f}</span></div>
            <div class="row"><span>POC (分水嶺):</span> <span style="color:#d29922">{res['poc']:.2f}</span></div>
            <div class="row"><span>VAL (抄底線):</span> <span style="color:#3fb950">{res['val']:.2f}</span></div>
            <div class="row"><span>距離 VAL:</span> <span style="color:#3fb950">{res['dist_pct_val']:+.2f}%</span></div>
            <div class="row"><span>SMA200 (生命線):</span> <span style="color:gray">{res['sma200']:.2f}</span></div>
            <hr style="border: 0; border-top: 1px dashed #30363d;">
            <div class="row"><span>狀態:</span> <span class="{res['color_class']}">{res['status_html']}</span></div>
            <div class="row"><span>指令:</span> <span class="{res['color_class']} bold" style="font-size:1.2em">{res['action_html']}</span></div>
            <div class="chart-container"><img class="chart-img" src="data:image/png;base64,{res['chart_base64']}"></div>
        </div>
        """

s_qqq = market_signals.get('QQQ', 0)
if s_qqq == -1:
    v_title, v_cls, v_msg = "🚨 熊市警報 (Bear Market)", "red", "QQQ 跌破年線，清空持倉，保留現金。"
elif s_qqq == 1:
    v_title, v_cls, v_msg = "🎯 絕佳買點 (Dip Buy)", "green", "價格回測 VAL 支撐，期望值極高，果斷買入。"
elif s_qqq == 2:
    v_title, v_cls, v_msg = "🚀 趨勢強勢 (Trend Run)", "cyan", "價格站穩 POC 之上，空手者立即買回，持倉者抱緊。"
else:
    v_title, v_cls, v_msg = "⚖️ 多空對峙 (Indecision)", "yellow", "價格在震盪區。若剛跌破 POC 先離場；若持底倉則續抱。"

day_of_month = datetime.datetime.now().day
if day_of_month <= 5:
    m_class = "m-alert"
    m_msg = f"⚠️ <b>月初健檢時間！</b>請執行 <code>monitor_robustness_global.py</code> 確認參數 (69/37) 是否依然是全域王者。"
else:
    m_class = "m-normal"
    m_msg = "參數魯棒性監測：建議每月 1~5 號執行一次全域掃描。"

final_html = html_template.format(
    update_time=datetime.datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %H:%M'), 
    content=f"{cards_html}<div class='verdict'><div class='verdict-title {v_cls}'>{v_title}</div><div style='margin-left: 20px;'>{v_msg}</div></div>",
    m_class=m_class,
    m_msg=m_msg
)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(final_html)

print("Dashboard Updated (Clean English Charts)!")