import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from zoneinfo import ZoneInfo
import os
import matplotlib
matplotlib.use('Agg') # 設定後端為非互動模式 (伺服器用)
import matplotlib.pyplot as plt
import mplfinance as mpf
import io
import base64

# ==========================================
# 1. 參數與設定
# ==========================================
target_tickers = ['SPY', 'QQQ', 'IWM']
ticker_names = {
    'SPY': '標普500 (SPY)',
    'QQQ': '納指100 (QQQ)',
    'IWM': '羅素2000 (IWM)'
}

# --- 核心策略參數 ---
lookback_days = 126   # 回溯天數 (半年)
bins_count = 70       # 籌碼分佈解析度 (小時線數據量大，可用 70)
va_pct = 0.70         # 價值區涵蓋率 (標準 70%)
st_period = 10        # SuperTrend 週期
st_multiplier = 3     # SuperTrend 倍數

# --- 繪圖風格設定 ---
plt.style.use('dark_background')
mpf_style = mpf.make_mpf_style(base_mpf_style='nightclouds', rc={'axes.grid': False})

# ==========================================
# 2. HTML 模板
# ==========================================
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

# ==========================================
# 3. 輔助函式庫
# ==========================================

def calculate_supertrend(df, period, multiplier):
    """
    計算 SuperTrend 指標
    回傳: trend (Series, 1為多頭, -1為空頭)
    """
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    # 計算 ATR (展開寫法，方便閱讀)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    # 計算基礎上下軌
    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)
    
    # 初始化結果容器
    final_upper = pd.Series(0.0, index=df.index)
    final_lower = pd.Series(0.0, index=df.index)
    trend = pd.Series(1, index=df.index)
    
    # 迭代計算
    for i in range(period, len(df)):
        # Final Upper
        if basic_upper.iloc[i] < final_upper.iloc[i-1] or close.iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]
            
        # Final Lower
        if basic_lower.iloc[i] > final_lower.iloc[i-1] or close.iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]
            
        # Trend Direction
        if trend.iloc[i-1] == 1:
            if close.iloc[i] < final_lower.iloc[i]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = 1
        else:
            if close.iloc[i] > final_upper.iloc[i]:
                trend.iloc[i] = 1
            else:
                trend.iloc[i] = -1
                
    return trend

def generate_chart(df_hourly, lookback_slice, sma200_val, poc_price, val_price, vah_price, price_bins, vol_by_bin, bin_indices):
    """
    生成 K 線圖與 Volume Profile 圖片，並轉為 Base64
    """
    fig = plt.figure(figsize=(10, 6), facecolor='#161b22')
    gs = fig.add_gridspec(1, 2,  width_ratios=(3, 1), left=0.05, right=0.95, wspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharey=ax1)

    # 只畫最後 300 小時，避免 K 線太密
    plot_slice = lookback_slice.iloc[-300:] 
    
    # 繪圖
    mpf.plot(plot_slice, type='candle', style=mpf_style, ax=ax1, show_nontrading=False, datetime_format='%m-%d', warn_too_much_data=2000)
    
    # 畫 SMA200 (水平參考線)
    if not np.isnan(sma200_val):
         ax1.axhline(y=sma200_val, color='gray', linestyle='--', linewidth=1, label='SMA200 (Daily)', alpha=0.7)

    # 畫 VP 關鍵價位
    ax1.axhline(y=poc_price, color='#d29922', linewidth=1.5, linestyle='-', label='POC')
    ax1.axhline(y=val_price, color='#3fb950', linewidth=1, linestyle='--', label='VAL')
    ax1.axhline(y=vah_price, color='#ff7b72', linewidth=1, linestyle='--', label='VAH')
    
    # 標示現價
    current_price = lookback_slice['Close'].iloc[-1]
    ax1.axhline(y=current_price, color='white', linewidth=0.8, linestyle=':')
    ax1.text(len(plot_slice) + 2, current_price, f'{current_price:.2f}', color='white', va='center', fontsize=9)

    ax1.set_ylabel("Price")
    ax1.legend(fontsize='small', facecolor='#161b22', edgecolor='#30363d')

    # 右側直方圖
    is_in_va = (bin_indices >= bin_indices[price_bins == val_price][0]) & (bin_indices <= bin_indices[price_bins == vah_price][0])
    colors = np.where(is_in_va, '#58a6ff', '#30363d')
    poc_bin_idx = np.argmax(vol_by_bin)
    colors[poc_bin_idx] = '#d29922'

    ax2.barh(price_bins, vol_by_bin, height=(price_bins[1]-price_bins[0])*0.8, align='center', color=colors, edgecolor=None, alpha=0.8)
    ax2.set_xlabel("Volume")
    ax2.tick_params(left=False, labelleft=False)
    ax2.grid(False)

    # 輸出 Base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100, facecolor=fig.get_facecolor())
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64

# ==========================================
# 4. 主計算邏輯
# ==========================================
def calculate_data(ticker):
    try:
        # ----------------------------------
        # 步驟 A: 獲取日線 (判斷趨勢與恐慌)
        # ----------------------------------
        df_daily = yf.download(ticker, period="2y", interval="1d", progress=False)
        
        # 處理 MultiIndex 欄位 (yfinance 新版相容性)
        if isinstance(df_daily.columns, pd.MultiIndex): 
            df_daily.columns = df_daily.columns.get_level_values(0)
        
        # 強制轉型為 float
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']: 
            if col in df_daily.columns:
                df_daily[col] = df_daily[col].astype(float)
        
        # [BUG FIX] 移除時區，避免報錯
        if df_daily.index.tz is not None: 
            df_daily.index = df_daily.index.tz_localize(None)
        
        if len(df_daily) < 200: return None
        
        # 計算指標
        sma200 = df_daily['Close'].rolling(window=200).mean().iloc[-1]
        current_price = df_daily['Close'].iloc[-1]
        is_bull_market = current_price > sma200
        
        # 計算 ATR (用於恐慌濾網)
        prev_close = df_daily['Close'].shift(1)
        tr = pd.concat([
            df_daily['High'] - df_daily['Low'], 
            (df_daily['High'] - prev_close).abs(), 
            (df_daily['Low'] - prev_close).abs()
        ], axis=1).max(axis=1)
        atr_14 = tr.rolling(window=14).mean().iloc[-1]
        
        # 判斷恐慌日: 當日震幅 > 1.8倍 ATR
        today_range = df_daily['High'].iloc[-1] - df_daily['Low'].iloc[-1]
        is_panic_day = today_range > (1.8 * atr_14)

        # 計算 SuperTrend (僅顯示狀態，不擋交易)
        st_trend = calculate_supertrend(df_daily, st_period, st_multiplier)
        current_st_dir = st_trend.iloc[-1]

        # ----------------------------------
        # 步驟 B: 獲取小時線 (計算籌碼 VP)
        # ----------------------------------
        df_hourly = yf.download(ticker, period="730d", interval="1h", progress=False)
        
        if isinstance(df_hourly.columns, pd.MultiIndex): 
            df_hourly.columns = df_hourly.columns.get_level_values(0)
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']: 
            if col in df_hourly.columns:
                df_hourly[col] = df_hourly[col].astype(float)
        
        if df_hourly.index.tz is not None: 
            df_hourly.index = df_hourly.index.tz_localize(None)
        
        if len(df_hourly) == 0: return None

        # 篩選過去 N 天數據
        cutoff = df_hourly.index[-1] - pd.Timedelta(days=lookback_days)
        df_slice = df_hourly[df_hourly.index > cutoff].copy()
        
        # 使用 Typical Price 計算
        p_slice = (df_slice['High'] + df_slice['Low'] + df_slice['Close']) / 3
        v_slice = df_slice['Volume']
        
        # ----------------------------------
        # 步驟 C: 計算 Volume Profile (核心)
        # ----------------------------------
        min_p, max_p = p_slice.min(), p_slice.max()
        bins = np.linspace(min_p, max_p, bins_count)
        vol_bin = np.zeros(bins_count)
        
        # 填入分箱
        for idx, v in zip(np.digitize(p_slice, bins), v_slice):
            if 0 <= idx < bins_count: vol_bin[idx] += v
            
        # 找 POC
        poc_idx = np.argmax(vol_bin)
        
        # 找 VAL / VAH (70%)
        target_v = vol_bin.sum() * va_pct
        curr_v, up, low = vol_bin[poc_idx], poc_idx, poc_idx
        while curr_v < target_v:
            v_u = vol_bin[up+1] if up < bins_count-1 else 0
            v_d = vol_bin[low-1] if low > 0 else 0
            if v_u == 0 and v_d == 0: break
            if v_u > v_d: 
                up += 1; curr_v += v_u
            else: 
                low -= 1; curr_v += v_d
                
        val_price, vah_price, poc_price = bins[low], bins[up], bins[poc_idx]

        # ----------------------------------
        # 步驟 D: 訊號判定
        # ----------------------------------
        is_below_val = current_price < val_price
        dist_pct = ((current_price - val_price) / current_price) * 100
        
        signal_code = 0
        action_html = ""
        status_html = ""
        color_class = ""
        
        trend_txt = "多頭" if is_bull_market else "空頭"
        trend_class = "green" if is_bull_market else "red"
        st_status_txt = "向上" if current_st_dir == 1 else "修正"
        
        # 交易邏輯: 破 VAL 且 長期趨勢多頭
        is_buy_setup = is_below_val and is_bull_market
        
        if is_buy_setup:
            # 優先檢查: 是否恐慌日?
            if is_panic_day:
                signal_code = 0 
                color_class = "yellow"
                action_html = "✋ 波動劇烈 (暫緩接刀)"
                status_html = f"破 VAL 但 ATR 過熱 (震幅過大)"
            else:
                # 正常買點
                signal_code = 1
                color_class = "green"
                # 區分順勢或逆勢
                if current_st_dir == 1:
                    action_html = "★ 強力買進 (完美回調)"
                    status_html = f"破 VAL 且 SuperTrend 支撐有效"
                else:
                    action_html = "⚡ 逆勢買進 (Buy the Dip)"
                    status_html = f"超賣回調 (SuperTrend 轉弱)"
        
        elif current_price > val_price and current_price < vah_price:
            signal_code = 0
            color_class = "yellow"
            action_html = "觀望 / 區間操作"
            status_html = f"價值區震盪"
        elif is_below_val and not is_bull_market:
            signal_code = -1
            color_class = "red"
            action_html = "▼ 放空追殺 (Short)"
            status_html = f"籌碼潰散 (破 MA200 & VAL)"
        else: 
            signal_code = 2
            color_class = "cyan"
            action_html = "強勢持有"
            status_html = f"多頭強勢區"

        # 生成圖表
        chart_base64 = generate_chart(df_hourly, df_slice, sma200, poc_price, val_price, vah_price, bins, vol_bin, np.arange(bins_count))

        return {
            'name': ticker_names[ticker], 'ticker': ticker, 'price': current_price,
            'poc': poc_price, 'val': val_price, 'sma200': sma200,
            'trend_txt': trend_txt, 'trend_class': trend_class,
            'status_html': status_html, 'action_html': action_html, 'color_class': color_class,
            'signal_code': signal_code, 'dist_pct': dist_pct, 'chart_base64': chart_base64,
            'atr': atr_14, 'st_status': st_status_txt
        }
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return None

# ==========================================
# 5. 主程式執行與 HTML 生成
# ==========================================
cards_html = ""
market_signals = {}

print("Starting analysis...")

for ticker in target_tickers:
    print(f"Analyzing {ticker}...")
    res = calculate_data(ticker)
    if res:
        market_signals[ticker] = res['signal_code']
        
        # 卡片 Header
        header = f'<div class="header {res["color_class"]}"><span>{res["name"]}</span><span class="small-tag {res["color_class"]}" style="border-color: currentColor;">{res["ticker"]}</span></div>'
        
        # 卡片內容 (新增 "距離 VAL" 行)
        cards_html += f"""
        <div class="card">
            {header}
            <div class="row"><span>現價:</span> <span>{res['price']:.2f}</span></div>
            <div class="row"><span>POC:</span> <span>{res['poc']:.2f}</span></div>
            <div class="row"><span>VAL:</span> <span>{res['val']:.2f}</span></div>
            
            <div class="row"><span>距離 VAL:</span> <span class="{res['color_class']}">{res['dist_pct']:+.2f}%</span></div>
            
            <div class="row"><span>趨勢:</span> <span class="{res['trend_class']}">{res['trend_txt']} (MA200: {res['sma200']:.0f})</span></div>
            <div class="row"><span>短線(ST):</span> <span class="gray">{res['st_status']} (ATR: {res['atr']:.2f})</span></div>
            <hr style="border: 0; border-top: 1px dashed #30363d;">
            <div class="row"><span>狀態:</span> <span class="{res['color_class']}">{res['status_html']}</span></div>
            <div class="row"><span>指令:</span> <span class="{res['color_class']} bold">{res['action_html']}</span></div>
            <div class="chart-container"><img class="chart-img" src="data:image/png;base64,{res['chart_base64']}"></div>
        </div>
        """

# 全局市場總結
s_spy, s_qqq, s_iwm = market_signals.get('SPY', 0), market_signals.get('QQQ', 0), market_signals.get('IWM', 0)

if s_spy == -1 and s_qqq == -1 and s_iwm == -1:
    v_html, v_cls, adv = "🚨 崩盤警報", "red", "清空多單，現金為王。"
elif s_iwm == -1 and (s_qqq >= 0 or s_spy >= 0):
    v_html, v_cls, adv = "⚠️ 變盤預警", "yellow", "市場風險急升，禁止加倉。"
elif s_spy == 1 and s_qqq == 1:
    v_html, v_cls, adv = "🔥 黃金機會", "green", "大膽買進 QQQ 與 SPY。"
elif s_qqq == 1 and s_iwm >= 0:
    v_html, v_cls, adv = "✅ 科技股上車", "green", "分批承接 QQQ。"
else:
    v_html, v_cls, adv = "😴 市場震盪", "cyan", "多看少做，避開高波動日。"

# 寫入檔案
final_html = html_template.format(
    update_time=datetime.datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %H:%M'), 
    content=f"{cards_html}<div class='verdict'><div class='verdict-title {v_cls}'>{v_html}</div><div style='margin-left: 20px;'>{adv}</div></div>"
)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(final_html)

print("Analysis complete. index.html updated!")