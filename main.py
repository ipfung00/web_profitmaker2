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
plt.rcParams['axes.unicode_minus'] = False 

# ==========================================
# 1. 策略參數 (Final Gold: Sniper Edition)
# ==========================================
target_tickers = ['SPY', 'QQQ', 'IWM']
ticker_names = {
    'SPY': '標普500 (SPY)',
    'QQQ': '納指100 (QQQ)',
    'IWM': '羅素2000 (IWM)'
}

# 👑 核心參數
lookback_days = 98      
bins_count = 7          
va_pct = 0.80           
atr_mult = 2.7          
panic_mult = 2.0        

# 🔫 狙擊手參數
sniper_rsi_threshold = 30
sniper_bias_threshold = -0.11  # -11%
sniper_stop_lookback = 14      # 短期止損

# 🎨 UI 顏色設定
COLOR_ATR_STOP = '#e5534b'    # 紅色 (長線止盈)
COLOR_SNIPER_STOP = '#ff79c6' # 亮粉色 (短線止損) - 改這裡區分顏色

# 繪圖風格
plt.style.use('dark_background')
mpf_style = mpf.make_mpf_style(base_mpf_style='nightclouds', rc={'axes.grid': False})

# ==========================================
# 2. HTML 模板
# ==========================================
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Quant Trading Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ background-color: #0d1117; color: #c9d1d9; font-family: 'Microsoft JhengHei', 'Consolas', sans-serif; padding: 20px; margin: 0; }}
        
        .nav {{ display: flex; border-bottom: 1px solid #30363d; margin-bottom: 20px; }}
        .nav-item {{ padding: 10px 20px; text-decoration: none; color: #8b949e; font-weight: bold; }}
        .nav-item:hover {{ color: #c9d1d9; background-color: #161b22; }}
        .nav-item.active {{ color: #58a6ff; border-bottom: 2px solid #58a6ff; }}

        .card {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; margin-bottom: 20px; }}
        .header {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #30363d; padding-bottom: 5px; display: flex; justify-content: space-between; align-items: center; }}
        
        .green {{ color: #3fb950; }}
        .red {{ color: #ff7b72; }}
        .yellow {{ color: #d29922; }}
        .cyan {{ color: #58a6ff; }}
        .gray {{ color: #8b949e; }}
        .purple {{ color: #a371f7; }}
        .orange {{ color: #f0883e; }}
        
        .bold {{ font-weight: bold; }}
        .row {{ display: flex; justify-content: space-between; margin-bottom: 5px; }}
        
        .verdict {{ background-color: #161b22; border: 1px solid #8b949e; padding: 20px; margin-top: 30px; }}
        .verdict-title {{ font-size: 1.5em; text-align: center; margin-bottom: 15px; font-weight: bold; }}
        
        .update-time {{ color: #8b949e; font-size: 0.8em; text-align: center; margin-bottom: 20px; }}
        .chart-container {{ margin-top: 15px; text-align: center; border: 1px solid #30363d; }}
        .chart-img {{ max-width: 100%; height: auto; display: block; }}
        .tag {{ font-size: 0.8em; padding: 2px 6px; border-radius: 4px; border: 1px solid; }}
        
        .maintenance-box {{ margin-top: 40px; padding: 15px; border-top: 1px solid #30363d; font-size: 0.9em; text-align: center; }}
        .m-alert {{ color: #ff7b72; border: 1px solid #ff7b72; padding: 10px; border-radius: 6px; background-color: rgba(255, 123, 114, 0.1); font-weight: bold; }}
        .m-warning {{ color: #d29922; border: 1px solid #d29922; padding: 10px; border-radius: 6px; background-color: rgba(210, 153, 34, 0.1); font-weight: bold; }}
        .m-normal {{ color: #8b949e; border: 1px dashed #30363d; padding: 10px; border-radius: 6px; }}
    </style>
</head>
<body>
    <div class="nav">
        <a href="index.html" class="nav-item active">🚀 策略訊號 (Signals)</a>
        <a href="structure.html" class="nav-item">🏗️ 市場結構 (Structure)</a>
    </div>

    <div class="update-time">最後更新 (美東時間): {update_time}</div>
    <div style="text-align: center; margin-bottom: 20px; font-size: 0.9em; color: #8b949e;">
        策略核心：Final Gold (Sniper Edition) | 參數: LB {lookback} / ATR {atr}x / Sniper (RSI&lt;{rsi}, Bias&lt;{bias}%)
    </div>
    
    {content}

    <div class="maintenance-box">
        <div class="{m_class}">
            {m_msg}
        </div>
    </div>
</body>
</html>
"""

# ==========================================
# 3. 輔助函數
# ==========================================
def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def generate_chart(df_daily, lookback_slice, sma200_val, poc_price, val_price, vah_price, price_bins, vol_by_bin, stop_price, sniper_stop):
    fig = plt.figure(figsize=(10, 6), facecolor='#161b22')
    gs = fig.add_gridspec(1, 2,  width_ratios=(3, 1), left=0.05, right=0.95, wspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharey=ax1)

    mpf.plot(lookback_slice, type='candle', style=mpf_style, ax=ax1, show_nontrading=False, datetime_format='%Y-%m-%d')
    
    if not np.isnan(sma200_val):
         ax1.axhline(y=sma200_val, color='gray', linestyle='--', linewidth=1, label='SMA200', alpha=0.7)

    # 繪製標準 ATR 止盈線 (紅色)
    if stop_price > 0:
        ax1.axhline(y=stop_price, color=COLOR_ATR_STOP, linewidth=1.5, linestyle='-', label=f'ATR Stop ({atr_mult}x)', alpha=0.9)
    
    # 繪製狙擊手止損線 (亮粉色)
    if sniper_stop > 0:
        ax1.axhline(y=sniper_stop, color=COLOR_SNIPER_STOP, linewidth=1.5, linestyle=':', label=f'Sniper Stop ({atr_mult}x)', alpha=0.9)

    ax1.axhline(y=poc_price, color='#d29922', linewidth=1.5, linestyle=':', label='POC (Entry Only)', alpha=0.8)
    ax1.axhline(y=val_price, color='#3fb950', linewidth=1, linestyle='--', label='VAL (Entry Only)', alpha=0.8)
    
    current_price = lookback_slice['Close'].iloc[-1]
    ax1.axhline(y=current_price, color='white', linewidth=0.8, linestyle=':')
    ax1.text(len(lookback_slice) + 1, current_price, f'{current_price:.2f}', color='white', va='center', fontsize=9)

    ax1.set_ylabel("Price")
    ax1.legend(fontsize='small', facecolor='#161b22', edgecolor='#30363d')

    colors = []
    for p in price_bins:
        if val_price <= p <= vah_price: colors.append('#58a6ff') 
        else: colors.append('#30363d') 
            
    poc_idx = np.argmax(vol_by_bin)
    colors[poc_idx] = '#d29922' 

    ax2.barh(price_bins, vol_by_bin, height=(price_bins[1]-price_bins[0])*0.8, align='center', color=colors, alpha=0.8)
    ax2.axis('off') 

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100, facecolor=fig.get_facecolor())
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64

# ==========================================
# 4. 核心運算
# ==========================================
def calculate_data(ticker):
    try:
        df_daily = yf.download(ticker, period="3y", interval="1d", progress=False)
        if isinstance(df_daily.columns, pd.MultiIndex): df_daily.columns = df_daily.columns.get_level_values(0)
        
        if len(df_daily) < 200: return None
        sma200 = df_daily['Close'].rolling(window=200).mean().iloc[-1]
        
        # 計算 ATR & Panic
        prev_close = df_daily['Close'].shift(1)
        tr = pd.concat([df_daily['High']-df_daily['Low'], (df_daily['High']-prev_close).abs(), (df_daily['Low']-prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        is_panic = (df_daily['High'].iloc[-1] - df_daily['Low'].iloc[-1]) > (panic_mult * atr)
        
        # 計算 RSI & Bias
        rsi_series = calculate_rsi(df_daily['Close'])
        rsi = rsi_series.iloc[-1]
        bias = (df_daily['Close'].iloc[-1] - sma200) / sma200
        
        current_price = df_daily['Close'].iloc[-1]
        is_bull_market = current_price > sma200
        is_sniper_zone = (rsi < sniper_rsi_threshold) and (bias < sniper_bias_threshold)
        
        # 切割數據
        df_slice = df_daily.iloc[-lookback_days:].copy()
        p_slice = (df_slice['High'] + df_slice['Low'] + df_slice['Close']) / 3
        v_slice = df_slice['Volume']
        
        range_min = df_slice['Low'].min()
        range_max = df_slice['High'].max()
        vol_bin, bin_edges = np.histogram(p_slice, bins=bins_count, range=(range_min, range_max), weights=v_slice)
        poc_idx = np.argmax(vol_bin)
        bin_mids = (bin_edges[:-1] + bin_edges[1:]) / 2
        poc_price = bin_mids[poc_idx]
        
        target_v = vol_bin.sum() * va_pct
        curr_v = vol_bin[poc_idx]
        up, low = poc_idx, poc_idx
        while curr_v < target_v:
            v_u = vol_bin[up+1] if up < bins_count-1 else 0
            v_d = vol_bin[low-1] if low > 0 else 0
            if v_u == 0 and v_d == 0: break
            if v_u > v_d: up += 1; curr_v += v_u
            else: low -= 1; curr_v += v_d
                
        val_price = bin_mids[low]
        vah_price = bin_mids[up]
        
        # 止盈線計算
        recent_highest_close = df_slice['Close'].max()
        stop_price = recent_highest_close - (atr_mult * atr)
        
        short_term_high = df_daily['Close'].iloc[-sniper_stop_lookback:].max()
        sniper_stop = short_term_high - (atr_mult * atr)
        
        signal_code = 0
        action_html, status_html, color_class = "", "", ""
        
        # --- 決策樹 ---
        if is_sniper_zone:
            signal_code = 3
            color_class = "orange"
            action_html = "🔫 狙擊手進場 (Sniper Buy)"
            status_html = f"RSI({rsi:.1f})<30 且 乖離({bias*100:.1f}%)<-11%。<br>建議投入 30% 資金。"
        elif not is_bull_market:
            # 特例：狙擊單續抱
            if current_price > sniper_stop:
                signal_code = -3
                color_class = "orange"
                action_html = "🛡️ 狙擊單續抱 (Sniper Hold)"
                status_html = f"價格 < SMA200，但位於短期止損 ({sniper_stop:.2f}) 之上。<br>狙擊單續抱，空手者觀望。"
            else:
                signal_code = -1
                color_class = "red"
                action_html = "▼ 清倉離場 (Bear Market)"
                status_html = f"價格 ({current_price:.2f}) 跌破年線 ({sma200:.2f})。"
        elif is_panic:
            signal_code = 0
            color_class = "yellow"
            action_html = "⚠️ 恐慌觀望 (High Volatility)"
            status_html = f"今日震幅 ({df_daily['High'].iloc[-1]-df_daily['Low'].iloc[-1]:.2f}) > {panic_mult}x ATR。"
        else:
            if current_price < val_price:
                signal_code = 1
                color_class = "green"
                action_html = "★ 強力抄底 (Dip Buy)"
                status_html = "價格回調至 VAL，勝率最高點。"
            elif current_price > poc_price:
                if current_price < stop_price:
                     signal_code = -2
                     color_class = "red"
                     action_html = "▼ 獲利了結 (Take Profit)"
                     status_html = f"跌破 ATR 止盈線 ({stop_price:.2f})。"
                else:
                    signal_code = 2
                    color_class = "cyan"
                    action_html = "▲ 續抱/追勢 (Let Run)"
                    status_html = f"ATR 止盈之上，建議 2x 槓桿。"
            else:
                signal_code = 0
                color_class = "yellow"
                action_html = "⚠️ 觀察 (Wait)"
                status_html = f"位於震盪區間 (VAL < P < POC)。"

        chart_base64 = generate_chart(df_daily, df_slice, sma200, poc_price, val_price, vah_price, bin_mids, vol_bin, stop_price, sniper_stop)

        return {
            'name': ticker_names[ticker], 'ticker': ticker, 'price': current_price,
            'poc': poc_price, 'val': val_price, 'sma200': sma200, 'stop_price': stop_price, 'sniper_stop': sniper_stop,
            'status_html': status_html, 'action_html': action_html, 'color_class': color_class,
            'signal_code': signal_code, 'chart_base64': chart_base64
        }
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return None

# ==========================================
# 5. 生成 HTML & 維護檢查
# ==========================================
cards_html = ""
market_signals = {}

for ticker in target_tickers:
    res = calculate_data(ticker)
    if res:
        market_signals[ticker] = res['signal_code']
        header = f'<div class="header {res["color_class"]}"><span>{res["name"]}</span><span class="tag {res["color_class"]}" style="border-color: currentColor;">{res["ticker"]}</span></div>'
        
        # UI 優化：將 Sniper 止損顏色改為亮粉色
        cards_html += f"""
        <div class="card">
            {header}
            <div class="row"><span>現價:</span> <span>{res['price']:.2f}</span></div>
            <div class="row"><span>ATR 止盈 (長線):</span> <span style="color:{COLOR_ATR_STOP}">{res['stop_price']:.2f}</span></div>
            <div class="row"><span>Sniper 止損 (短線):</span> <span style="color:{COLOR_SNIPER_STOP}">{res['sniper_stop']:.2f}</span></div>
            <div class="row"><span>POC (買點):</span> <span style="color:#d29922">{res['poc']:.2f}</span></div>
            <div class="row"><span>VAL (抄底):</span> <span style="color:#3fb950">{res['val']:.2f}</span></div>
            <div class="row"><span>SMA200:</span> <span style="color:gray">{res['sma200']:.2f}</span></div>
            <hr style="border: 0; border-top: 1px dashed #30363d;">
            <div class="row"><span>狀態:</span> <span class="{res['color_class']}">{res['status_html']}</span></div>
            <div class="row"><span>指令:</span> <span class="{res['color_class']} bold" style="font-size:1.2em">{res['action_html']}</span></div>
            <div class="chart-container"><img class="chart-img" src="data:image/png;base64,{res['chart_base64']}"></div>
        </div>
        """

s_qqq = market_signals.get('QQQ', 0)
if s_qqq == 3: v_title, v_cls, v_msg = "🔫 狙擊時刻 (Sniper Mode)", "orange", "市場極度恐慌，執行 30% 資金抄底。"
elif s_qqq == -3: v_title, v_cls, v_msg = "🛡️ 狙擊防守 (Hold)", "orange", "熊市反彈中，狙擊單請設好短期止損續抱。"
elif s_qqq == -1: v_title, v_cls, v_msg = "🚨 熊市警報", "red", "跌破年線，全數清倉。"
elif s_qqq == -2: v_title, v_cls, v_msg = "💰 獲利了結", "red", "跌破 ATR 止盈線，波段結束。"
elif s_qqq == 1: v_title, v_cls, v_msg = "🎯 絕佳買點", "green", "回測 VAL 支撐，進場抄底。"
elif s_qqq == 2: v_title, v_cls, v_msg = "🚀 趨勢續抱 (2x Leverage)", "purple", "建議持有 QLD (2x QQQ)。"
else: v_title, v_cls, v_msg = "⚖️ 震盪觀察", "yellow", "區間震盪，等待方向。"

# ⏰ 智能維護鬧鐘 (整合年度與季度)
now = datetime.datetime.now()
maintenance_months = [1, 4, 7, 10]
is_quarterly_time = (now.month in maintenance_months) and (now.day <= 7)
is_annual_time = (now.month == 12) # 整個 12 月都會提醒

m_class = "m-normal"
m_msg = "✅ 系統狀態正常。"

if is_annual_time:
    m_class = "m-alert"
    m_msg = "🎯 <b>年度靶場校準警報！</b> 現在是 12 月，請務必執行 <code>monitor_market_structure.py</code> 檢查瞄準鏡是否失準。"
    print("\n" + "!"*60)
    print(f"🚨 系統維護警報 (Annual Calibration) 🚨")
    print(f"   現在是 12 月，請檢查市場結構！")
    print("   👉 python monitor_market_structure.py")
    print("!"*60 + "\n")
elif is_quarterly_time:
    m_class = "m-warning"
    m_msg = f"🔧 <b>季度健檢提醒：</b> 現在是 {now.month} 月初，請執行 <code>scan_5d_quarterly.py</code> 確認核心參數。"
    print("\n" + "!"*60)
    print(f"🔧 系統維護提醒 (Quarterly Maintenance)")
    print("   👉 python scan_5d_quarterly.py")
    print("!"*60 + "\n")
else:
    next_q = [m for m in maintenance_months if m > now.month]
    next_check = next_q[0] if next_q else 1
    m_msg = f"✅ 系統狀態正常。<br>下季健檢：{next_check} 月 | 年度校準：12 月。"

final_html = html_template.format(
    lookback=lookback_days, bins=bins_count, va=va_pct, atr=atr_mult, panic=panic_mult,
    rsi=sniper_rsi_threshold, bias=sniper_bias_threshold*100,
    update_time=datetime.datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %H:%M'), 
    content=f"{cards_html}<div class='verdict'><div class='verdict-title {v_cls}'>{v_title}</div><div style='margin-left: 20px;'>{v_msg}</div></div>",
    m_class=m_class,
    m_msg=m_msg
)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(final_html)

print("✅ UI Updated: Sniper Stop color changed to Pink & Annual Timer Set.")