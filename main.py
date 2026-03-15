import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from zoneinfo import ZoneInfo
import os
import matplotlib
matplotlib.use('Agg') # 設定後端為非互動模式
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import mplfinance as mpf
import io
import base64
import config  # <--- 引入配置檔

# ==========================================
# 0. 系統設定
# ==========================================
plt.rcParams['axes.unicode_minus'] = False 
plt.style.use('dark_background')
mpf_style = mpf.make_mpf_style(base_mpf_style='nightclouds', rc={'axes.grid': False})

# ==========================================
# 1. 讀取策略參數 (從 config.py)
# ==========================================
target_tickers = ['SPY', 'QQQ', 'IWM']
ticker_names = {
    'SPY': '標普500 (SPY)',
    'QQQ': '納指100 (QQQ)',
    'IWM': '羅素2000 (IWM)'
}

# 👑 核心參數
lookback_days = config.CORE_PARAMS['LOOKBACK']
bins_count = config.CORE_PARAMS['BINS']
va_pct = config.CORE_PARAMS['VA_PCT']
atr_mult = config.CORE_PARAMS['ATR_MULT']
panic_mult = config.CORE_PARAMS['PANIC_MULT']

# 🔫 狙擊手參數
sniper_rsi_threshold = config.SNIPER_PARAMS['RSI_THRESHOLD']
sniper_bias_threshold = config.SNIPER_PARAMS['BIAS_THRESHOLD']
sniper_size = config.SNIPER_PARAMS['SIZE']
sniper_stop_lookback = config.SNIPER_PARAMS['STOP_LOOKBACK']

# 🎨 UI 顏色設定
COLOR_ATR_STOP = config.UI_COLORS['ATR_STOP']
COLOR_SNIPER_STOP = config.UI_COLORS['SNIPER_STOP']
COLOR_BUY_CORE = config.UI_COLORS['BUY_CORE']
COLOR_BUY_SNIPER = config.UI_COLORS['BUY_SNIPER']

# ==========================================
# 2. HTML 模板工具
# ==========================================
def get_html_header(title, active_tab):
    cls_sig = "active" if active_tab == "signal" else ""
    cls_trd = "active" if active_tab == "trade" else ""
    cls_prt = "active" if active_tab == "portfolio" else ""
    cls_str = "active" if active_tab == "structure" else ""
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ background-color: #0d1117; color: #c9d1d9; font-family: 'Microsoft JhengHei', 'Consolas', sans-serif; padding: 20px; margin: 0; }}
        
        .nav {{ display: flex; border-bottom: 1px solid #30363d; margin-bottom: 20px; }}
        .nav-item {{ padding: 10px 20px; text-decoration: none; color: #8b949e; font-weight: bold; cursor: pointer; }}
        .nav-item:hover {{ color: #c9d1d9; background-color: #161b22; }}
        .nav-item.active {{ color: #58a6ff; border-bottom: 2px solid #58a6ff; }}

        .card {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; margin-bottom: 20px; }}
        .header {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #30363d; padding-bottom: 5px; display: flex; justify-content: space-between; align-items: center; }}
        
        .green {{ color: #3fb950; }} .red {{ color: #ff7b72; }} .yellow {{ color: #d29922; }} 
        .cyan {{ color: #58a6ff; }} .gray {{ color: #8b949e; }} .purple {{ color: #a371f7; }} .orange {{ color: #f0883e; }}
        .bold {{ font-weight: bold; }} 
        .row {{ display: flex; justify-content: space-between; margin-bottom: 5px; }}
        
        .verdict {{ background-color: #161b22; border: 1px solid #8b949e; padding: 20px; margin-top: 30px; }}
        .verdict-title {{ font-size: 1.5em; text-align: center; margin-bottom: 15px; font-weight: bold; }}
        
        .update-time {{ color: #8b949e; font-size: 0.8em; text-align: center; margin-bottom: 20px; }}
        .chart-container {{ margin-top: 15px; text-align: center; border: 1px solid #30363d; }}
        .chart-img {{ max-width: 100%; height: auto; display: block; }}
        .tag {{ font-size: 0.8em; padding: 2px 6px; border-radius: 4px; border: 1px solid; }}
        
        /* 參數儀表板樣式 */
        .param-box {{ 
            display: flex; flex-wrap: wrap; gap: 15px; 
            background-color: #21262d; border: 1px solid #30363d; border-radius: 6px; 
            padding: 10px 15px; margin-bottom: 20px; font-size: 0.85em; color: #8b949e; justify-content: center;
        }}
        .param-group {{ display: flex; align-items: center; gap: 5px; }}
        .param-label {{ font-weight: bold; color: #c9d1d9; }}
        .param-val {{ color: #58a6ff; font-family: 'Consolas', monospace; }}
        .divider {{ border-left: 1px solid #30363d; margin: 0 5px; }}
        
        table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ color: #8b949e; }}
        tr:hover {{ background-color: #21262d; }}
        .pnl-pos {{ color: #3fb950; }}
        .pnl-neg {{ color: #ff7b72; }}
        
        .maintenance-box {{ margin-top: 40px; padding: 15px; border-top: 1px solid #30363d; font-size: 0.9em; text-align: center; }}
        .m-alert {{ color: #ff7b72; border: 1px solid #ff7b72; padding: 10px; border-radius: 6px; background-color: rgba(255, 123, 114, 0.1); font-weight: bold; }}
        .m-warning {{ color: #d29922; border: 1px solid #d29922; padding: 10px; border-radius: 6px; background-color: rgba(210, 153, 34, 0.1); font-weight: bold; }}
        .m-normal {{ color: #8b949e; border: 1px dashed #30363d; padding: 10px; border-radius: 6px; }}
    </style>
</head>
<body>
    <div class="nav">
        <a href="index.html" class="nav-item {cls_sig}">🚀 策略訊號 (Signals)</a>
        <a href="trades.html" class="nav-item {cls_trd}">📊 模擬回測 (Backtest)</a>
        <a href="portfolio.html" class="nav-item {cls_prt}">💰 真實帳戶 (Portfolio)</a>
        <a href="structure.html" class="nav-item {cls_str}">🏗️ 市場結構 (Structure)</a>
        <a href="structure_bottom.html" class="nav-item">📉 市場底部結構 (Bottoms)</a>
    </div>
    <div class="update-time">最後更新 (美東時間): {datetime.datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %H:%M')}</div>
"""

def get_html_footer(m_class, m_msg):
    return f"""
    <div class="maintenance-box">
        <div class="{m_class}">
            {m_msg}
        </div>
    </div>
</body>
</html>
"""

def get_config_html():
    c = config.CORE_PARAMS
    s = config.SNIPER_PARAMS
    
    return f"""
    <div class="param-box">
        <div class="param-group"><span class="param-label">👑 Core:</span> <span class="param-val">LB {c['LOOKBACK']}</span></div>
        <div class="param-group"><span class="param-label">ATR:</span> <span class="param-val">{c['ATR_MULT']}x</span></div>
        <div class="param-group"><span class="param-label">VP:</span> <span class="param-val">{c['BINS']} Bins / {int(c['VA_PCT']*100)}%</span></div>
        <div class="divider"></div>
        <div class="param-group"><span class="param-label">🔫 Sniper:</span> <span class="param-val">RSI < {s['RSI_THRESHOLD']}</span></div>
        <div class="param-group"><span class="param-label">Bias:</span> <span class="param-val">< {int(s['BIAS_THRESHOLD']*100)}%</span></div>
        <div class="param-group"><span class="param-label">Size:</span> <span class="param-val">{int(s['SIZE']*100)}%</span></div>
    </div>
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

# ==========================================
# 4. PART A: 訊號生成與圖表 (index.html)
# ==========================================
def generate_chart(df_daily, lookback_slice, sma200_slice, poc_price, val_price, vah_price, price_bins, vol_by_bin, active_stop_price, active_stop_label, stop_color_css, show_sniper_ref):
    fig = plt.figure(figsize=(10, 6), facecolor='#161b22')
    gs = fig.add_gridspec(1, 2,  width_ratios=(3, 1), left=0.05, right=0.95, wspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharey=ax1)

    # 準備外加的曲線 (SMA200)
    ap = []
    if not sma200_slice.isna().all():
        ap.append(mpf.make_addplot(sma200_slice, color='gray', linestyle='--', width=1.2, ax=ax1))

    mpf.plot(lookback_slice, type='candle', style=mpf_style, ax=ax1, addplot=ap, show_nontrading=False, datetime_format='%Y-%m-%d')
    
    if active_stop_price > 0:
        ax1.axhline(y=active_stop_price, color=stop_color_css, linewidth=2, linestyle='-', label=active_stop_label, alpha=0.9)
    
    if show_sniper_ref > 0:
        ax1.axhline(y=show_sniper_ref, color=COLOR_SNIPER_STOP, linewidth=1.5, linestyle=':', label='預估 Sniper 止損', alpha=0.6)

    ax1.axhline(y=poc_price, color='#d29922', linewidth=1.5, linestyle=':', label='POC (Value Center)', alpha=0.8)
    ax1.axhline(y=val_price, color='#3fb950', linewidth=1, linestyle='--', label='VAL (Dip Buy Zone)', alpha=0.8)
    
    current_price = lookback_slice['Close'].iloc[-1]
    ax1.axhline(y=current_price, color='white', linewidth=0.8, linestyle=':')
    ax1.text(len(lookback_slice) + 1, current_price, f'{current_price:.2f}', color='white', va='center', fontsize=9)

    ax1.set_ylabel("Price")
    ax1.legend(fontsize='small', facecolor='#161b22', edgecolor='#30363d')

    colors = []
    for p in price_bins:
        if val_price <= p <= vah_price: colors.append('#58a6ff') 
        else: colors.append('#30363d') 
    colors[np.argmax(vol_by_bin)] = '#d29922' 

    ax2.barh(price_bins, vol_by_bin, height=(price_bins[1]-price_bins[0])*0.8, align='center', color=colors, alpha=0.8)
    ax2.axis('off') 

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100, facecolor=fig.get_facecolor())
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64

def calculate_data(ticker, backtest_status=None):
    try:
        df_daily = yf.download(ticker, period="3y", interval="1d", progress=False)
        if isinstance(df_daily.columns, pd.MultiIndex): df_daily.columns = df_daily.columns.get_level_values(0)
        
        if len(df_daily) < 200: return None
        
        sma200_series = df_daily['Close'].rolling(window=200).mean()
        sma200_val = sma200_series.iloc[-1]
        sma200_chart = sma200_series.iloc[-lookback_days:]
        
        prev_close = df_daily['Close'].shift(1)
        tr = pd.concat([df_daily['High']-df_daily['Low'], (df_daily['High']-prev_close).abs(), (df_daily['Low']-prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        is_panic = (df_daily['High'].iloc[-1] - df_daily['Low'].iloc[-1]) > (panic_mult * atr)
        
        rsi_series = calculate_rsi(df_daily['Close'])
        rsi = rsi_series.iloc[-1]
        bias = (df_daily['Close'].iloc[-1] - sma200_val) / sma200_val
        
        current_price = df_daily['Close'].iloc[-1]
        is_bull_market = current_price > sma200_val
        is_sniper_zone = (rsi < sniper_rsi_threshold) and (bias < sniper_bias_threshold)
        
        # 1. 繪圖用的 Slice (包含今日)
        df_chart = df_daily.iloc[-lookback_days:].copy()
        
        # 2. 計算 VP 指標用的 Slice (嚴格模式：排除今日)
        df_calc = df_daily.iloc[-lookback_days-1 : -1].copy() 
        
        p_slice = (df_calc['High'] + df_calc['Low'] + df_calc['Close']) / 3
        v_slice = df_calc['Volume']
        
        range_min = df_calc['Low'].min()
        range_max = df_calc['High'].max()
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
        
        recent_highest_close = df_chart['Close'].max()
        local_stop_price = recent_highest_close - (atr_mult * atr)
        
        short_term_high = df_daily['Close'].iloc[-sniper_stop_lookback-1 : -1].max()
        local_sniper_stop = short_term_high - (atr_mult * atr)
        
        signal_code = 0
        action_html, status_html, color_class = "", "", ""

        # ==============================================================
        # 狀態判定與止損線指派 (保證 UI 與 底層一致)
        # ==============================================================
        if backtest_status and backtest_status['in_pos']:
            active_stop_price = backtest_status.get('real_stop_price', local_stop_price)
            show_sniper_ref = 0 
            html_sniper_row = "" 
            
            if backtest_status['is_fishing']:
                active_stop_label = "Sniper 止損"
                stop_color_css = COLOR_SNIPER_STOP
                signal_code = -3 
                color_class = "orange"; action_html = "🛡️ 狙擊單續抱 (Sniper Hold)"
                status_html = f"狀態同步: 狙擊中。止損參考近 {sniper_stop_lookback} 日高點。"
            else:
                active_stop_label = "ATR 止盈"
                stop_color_css = COLOR_ATR_STOP
                signal_code = 2 
                color_class = "purple"; action_html = "🚀 趨勢續抱 (Core Hold)"
                status_html = f"狀態同步: 趨勢中。止損線由系統底層精確計算。"
        else:
            active_stop_price = local_stop_price
            active_stop_label = "預估 Core 止損"
            stop_color_css = "gray" 
            show_sniper_ref = local_sniper_stop
            html_sniper_row = f'<div class="row"><span>預估 Sniper 止損:</span> <span style="color:{COLOR_SNIPER_STOP}">{local_sniper_stop:.2f}</span></div>'
            
            if is_sniper_zone:
                signal_code = 3; color_class = "orange"; action_html = "🔫 狙擊手進場 (Sniper Buy)"
                # [BUG FIX 1] 移除硬編碼，從變數動態讀取 RSI 與 Bias 參數門檻
                status_html = f"RSI({rsi:.1f})<{sniper_rsi_threshold} 且 乖離({bias*100:.1f}%)<{sniper_bias_threshold*100:.0f}%。<br>建議投入 {int(sniper_size*100)}% 資金。"
            
            elif not is_bull_market:
                if current_price > local_sniper_stop:
                    signal_code = -3; color_class = "orange"; action_html = "🛡️ 狙擊單續抱 (Sniper Hold)"
                    status_html = f"價格 < SMA200，但位於短期止損 ({local_sniper_stop:.2f}) 之上。"
                else:
                    signal_code = -1; color_class = "red"; action_html = "▼ 清倉離場 (Bear Market)"
                    status_html = f"價格 ({current_price:.2f}) 跌破年線 ({sma200_val:.2f})。"
            
            elif is_panic:
                signal_code = 0; color_class = "yellow"; action_html = "⚠️ 恐慌觀望 (High Volatility)"
                status_html = f"今日震幅 > {panic_mult}x ATR。"
                
            else:
                if current_price < local_stop_price:
                     signal_code = -2; color_class = "red"; action_html = "🛑 趨勢破壞 (Trend Broken)"
                     status_html = f"跌破預估 ATR 防守線 ({local_stop_price:.2f})，多頭波段結束/觀望。"
                
                elif current_price < val_price:
                    signal_code = 1; color_class = "green"; action_html = "★ 強力抄底 (Dip Buy)"
                    status_html = "價格回調至 VAL，且守住 ATR 支撐，勝率最高點。"
                    
                elif current_price > poc_price:
                    signal_code = 2; color_class = "cyan"; action_html = "▲ 續抱/追勢 (Let Run)"
                    status_html = f"位於強勢區間 (Price > POC)，趨勢向上。"
                
                else:
                    signal_code = 0; color_class = "yellow"; action_html = "⚠️ 觀察 (Wait)"
                    status_html = f"位於震盪區間 (VAL < P < POC)，但仍守住 ATR 線。"

        atr_gap_pct = (current_price - active_stop_price) / current_price * 100
        if atr_gap_pct < 0: gap_color = "#ff7b72"
        elif atr_gap_pct < 1.5: gap_color = "#d29922"
        else: gap_color = "#3fb950"

        chart_base64 = generate_chart(df_daily, df_chart, sma200_chart, poc_price, val_price, vah_price, bin_mids, vol_bin, active_stop_price, active_stop_label, stop_color_css, show_sniper_ref)

        return {
            'name': ticker_names[ticker], 'ticker': ticker, 'price': current_price,
            'poc': poc_price, 'val': val_price, 'sma200': sma200_val,
            'active_stop_price': active_stop_price, 'active_stop_label': active_stop_label, 'stop_color_css': stop_color_css,
            'html_sniper_row': html_sniper_row,
            'status_html': status_html, 'action_html': action_html, 'color_class': color_class,
            'signal_code': signal_code, 'chart_base64': chart_base64,
            'atr_gap_pct': atr_gap_pct, 'gap_color': gap_color
        }
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return None

# ==========================================
# 5. PART B: 回測與 YTD 生成 (trades.html)
# ==========================================
def run_qqq_backtest():
    print("⏳ 正在計算 QQQ 交易紀錄與 YTD 績效 (包含狀態同步)...")
    start_date = config.START_DATE
    df = yf.download("QQQ", start=start_date, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    prev_close = df['Close'].shift(1)
    tr = pd.concat([df['High']-df['Low'], (df['High']-prev_close).abs(), (df['Low']-prev_close).abs()], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()
    df['Is_Panic'] = (df['High'] - df['Low']) > (panic_mult * df['ATR'])
    df['RSI'] = calculate_rsi(df['Close'], 14)
    df['Bias'] = (df['Close'] - df['SMA200']) / df['SMA200']
    
    roll_max_sniper = df['Close'].rolling(window=sniper_stop_lookback).max().shift(1).fillna(0).values
    
    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    volumes = df['Volume'].values
    smas = df['SMA200'].values
    atrs = df['ATR'].values
    panics = df['Is_Panic'].values
    rsis = df['RSI'].values
    biases = df['Bias'].values
    tps = (highs + lows + closes) / 3
    dates = df.index
    
    balance = config.INITIAL_CAPITAL
    position = 0
    in_pos = False
    highest_close = 0.0
    is_fishing = False
    real_stop_price = 0.0 
    
    start_idx = 200
    bh_shares = config.INITIAL_CAPITAL / closes[start_idx]
    
    equity_curve = []
    trade_log = []
    entry_date, entry_price, entry_type = None, 0.0, ""
    
    for i in range(start_idx, len(df)):
        curr_date = dates[i]
        curr_close = closes[i]
        curr_sma = smas[i]
        curr_atr = atrs[i]
        is_panic = panics[i]
        curr_rsi = rsis[i]
        curr_bias = biases[i]
        
        p_slice = tps[i-lookback_days : i]
        v_slice = volumes[i-lookback_days : i]
        range_min = np.min(lows[i-lookback_days : i])
        range_max = np.max(highs[i-lookback_days : i])

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
        
        if not in_pos:
            if (curr_rsi < sniper_rsi_threshold) and (curr_bias < sniper_bias_threshold):
                invest_amt = balance * sniper_size
                position = invest_amt / curr_close
                balance -= invest_amt
                in_pos = True
                highest_close = curr_close
                is_fishing = True
                entry_date, entry_price, entry_type = curr_date, curr_close, "Sniper"
            elif curr_close > curr_sma and not is_panic:
                if (curr_close < val_price) or (curr_close > poc_price):
                    position = balance / curr_close
                    balance = 0
                    in_pos = True
                    highest_close = curr_close
                    is_fishing = False
                    entry_date, entry_price, entry_type = curr_date, curr_close, "Core"
        else:
            if curr_close > highest_close: highest_close = curr_close
            if is_fishing and curr_close > curr_sma: is_fishing = False
            
            should_sell = False
            sell_reason = ""
            
            if is_fishing:
                stop_price = roll_max_sniper[i] - (atr_mult * curr_atr)
                real_stop_price = stop_price 
                if curr_close < stop_price: should_sell, sell_reason = True, "Sniper Stop"
            else:
                stop_price = highest_close - (atr_mult * curr_atr)
                real_stop_price = stop_price 
                
                if curr_close < curr_sma: 
                    should_sell, sell_reason = True, "Bear Market"
                elif curr_close < stop_price: 
                    should_sell, sell_reason = True, "ATR Stop"
            
            if should_sell:
                balance += position * curr_close
                pnl = (curr_close - entry_price) / entry_price * 100
                trade_log.append({
                    'Entry Date': entry_date, 'Exit Date': curr_date, 'Type': entry_type,
                    'Entry Price': entry_price, 'Exit Price': curr_close, 'PnL %': pnl,
                    'Hold Days': (curr_date - entry_date).days, 'Reason': sell_reason
                })
                in_pos = False
                position = 0
                highest_close = 0.0
                is_fishing = False
                real_stop_price = 0.0

        curr_equity = balance + (position * curr_close)
        curr_bh_equity = bh_shares * curr_close
        equity_curve.append({'Date': curr_date, 'Strategy': curr_equity, 'BuyHold': curr_bh_equity})

    if in_pos:
        unrealized_pnl = (closes[-1] - entry_price) / entry_price * 100
        trade_log.append({
            'Entry Date': entry_date, 'Exit Date': pd.NaT, 'Type': entry_type,
            'Entry Price': entry_price, 'Exit Price': closes[-1], 'PnL %': unrealized_pnl,
            'Hold Days': (dates[-1] - entry_date).days, 'Reason': 'OPEN'
        })
    
    current_status = {
        'in_pos': in_pos, 
        'is_fishing': is_fishing, 
        'type': entry_type if in_pos else "NONE",
        'real_stop_price': real_stop_price if in_pos else 0.0
    }
    return pd.DataFrame(trade_log), pd.DataFrame(equity_curve).set_index('Date'), current_status

def generate_trades_html(df_trades, df_eq):
    current_year = datetime.datetime.now().year
    df_ytd = df_eq[df_eq.index.year == current_year].copy()
    if df_ytd.empty: df_ytd = df_eq.iloc[-250:]
    
    if not df_ytd.empty:
        start_strat = df_ytd['Strategy'].iloc[0]
        start_bh = df_ytd['BuyHold'].iloc[0]
        y_strat = (df_ytd['Strategy'] / start_strat - 1) * 100
        y_bh = (df_ytd['BuyHold'] / start_bh - 1) * 100
        
        fig, ax = plt.subplots(figsize=(10, 5), facecolor='#161b22')
        ax.set_facecolor('#161b22')
        ax.plot(df_ytd.index, y_strat, color='#00ff00', linewidth=2, label='Strategy (YTD)')
        ax.plot(df_ytd.index, y_bh, color='#808080', linestyle='--', linewidth=1.5, label='QQQ (YTD)')
        ax.set_title(f"QQQ Year-to-Date Performance ({current_year})", color='white', fontsize=14)
        ax.set_ylabel("Return (%)", color='#8b949e')
        ax.legend(fontsize=10, facecolor='#161b22', edgecolor='#30363d', labelcolor='white')
        ax.grid(True, color='#30363d', linestyle=':', alpha=0.5)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        ax.tick_params(axis='x', colors='#8b949e')
        ax.tick_params(axis='y', colors='#8b949e')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100, facecolor='#161b22')
        plt.close(fig)
        buf.seek(0)
        chart_b64 = base64.b64encode(buf.read()).decode('utf-8')
    else:
        chart_b64 = ""

    recent_trades = df_trades.tail(50).iloc[::-1]
    table_rows = ""
    for _, row in recent_trades.iterrows():
        pnl = row['PnL %']
        pnl_cls = "pnl-pos" if pnl > 0 else "pnl-neg"
        pnl_txt = f"{pnl:+.2f}%"
        entry_d = row['Entry Date'].strftime('%Y-%m-%d')
        exit_d = row['Exit Date'].strftime('%Y-%m-%d') if pd.notnull(row['Exit Date']) else "HOLDING"
        reason = row['Reason'] if row['Reason'] != 'OPEN' else '<span class="m-warning">HOLDING</span>'
        buy_color = config.UI_COLORS['BUY_SNIPER'] if row['Type']=='Sniper' else config.UI_COLORS['BUY_CORE']
        
        table_rows += f"""
        <tr>
            <td>{entry_d}</td>
            <td style="color: {buy_color}">{row['Type']}</td>
            <td>{row['Entry Price']:.2f}</td>
            <td>{exit_d}</td>
            <td>{row['Exit Price']:.2f}</td>
            <td class="{pnl_cls} bold">{pnl_txt}</td>
            <td>{reason}</td>
        </tr>
        """

    return f"""
    <div class="card">
        <div class="header green">📈 年度績效對比 (Strategy vs QQQ)</div>
        <div class="chart-container"><img class="chart-img" src="data:image/png;base64,{chart_b64}"></div>
    </div>
    <div class="card">
        <div class="header cyan">📋 最近 50 筆交易紀錄 (QQQ)</div>
        <table>
            <thead>
                <tr>
                    <th>進場日期</th><th>類型</th><th>買入價</th><th>出場日期</th><th>賣出價</th><th>損益 %</th><th>備註</th>
                </tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
    </div>
    """

# ==========================================
# 6. 生成 HTML
# ==========================================
df_trades, df_eq, qqq_status = run_qqq_backtest()

cards_html = ""
market_signals = {}
for ticker in target_tickers:
    status_to_pass = qqq_status if ticker == "QQQ" else None
    res = calculate_data(ticker, status_to_pass)
    
    if res:
        market_signals[ticker] = res['signal_code']
        header = f'<div class="header {res["color_class"]}"><span>{res["name"]}</span><span class="tag {res["color_class"]}" style="border-color: currentColor;">{res["ticker"]}</span></div>'
        
        cards_html += f"""
        <div class="card">
            {header}
            <div class="row"><span>現價:</span> <span>{res['price']:.2f}</span></div>
            <div class="row">
                <span>{res['active_stop_label']}:</span> 
                <span>
                    <span style="color:{res['gap_color']}; font-size:0.9em; margin-right:5px;">[{res['atr_gap_pct']:+.2f}%]</span>
                    <span style="color:{res['stop_color_css']}">{res['active_stop_price']:.2f}</span> 
                </span>
            </div>
            {res['html_sniper_row']}
            <div class="row"><span>POC:</span> <span style="color:#d29922">{res['poc']:.2f}</span></div>
            <div class="row"><span>VAL:</span> <span style="color:#3fb950">{res['val']:.2f}</span></div>
            <div class="row"><span>SMA200:</span> <span style="color:gray">{res['sma200']:.2f}</span></div>
            <hr style="border: 0; border-top: 1px dashed #30363d;">
            <div class="row"><span>狀態:</span> <span class="{res['color_class']}">{res['status_html']}</span></div>
            <div class="row"><span>指令:</span> <span class="{res['color_class']} bold" style="font-size:1.2em">{res['action_html']}</span></div>
            <div class="chart-container"><img class="chart-img" src="data:image/png;base64,{res['chart_base64']}"></div>
        </div>
        """

s_qqq = market_signals.get('QQQ', 0)
if s_qqq == 3: v_title, v_cls, v_msg = "🔫 狙擊時刻 (Sniper)", "orange", "市場極度恐慌，建議全倉進場接刀。"
elif s_qqq == -3: v_title, v_cls, v_msg = "🛡️ 狙擊防守 (Hold)", "orange", "熊市反彈中，狙擊單續抱。"
elif s_qqq == -1: v_title, v_cls, v_msg = "🚨 熊市警報", "red", "跌破年線，全數清倉。"
# [BUG FIX 2] 修正空手狀態下的文字顯示邏輯
elif s_qqq == -2: v_title, v_cls, v_msg = "🛑 趨勢破壞", "red", "跌破 ATR 防守線，多頭波段結束/觀望。"
elif s_qqq == 1: v_title, v_cls, v_msg = "🎯 絕佳買點", "green", "回測 VAL 支撐，進場抄底。"
elif s_qqq == 2: v_title, v_cls, v_msg = "🚀 趨勢續抱", "purple", "建議持有 QQQ。"
else: v_title, v_cls, v_msg = "⚖️ 震盪觀察", "yellow", "區間震盪，等待方向。"

now = datetime.datetime.now()
m_months = [1, 4, 7, 10]
if now.month == 12: m_class, m_msg = "m-alert", "🎯 <b>年度校準警報！</b> 請執行 <code>monitor_market_structure.py</code>。"
elif (now.month in m_months) and (now.day <= 7): m_class, m_msg = "m-warning", "🔧 <b>季度健檢提醒：</b> 請執行 <code>scan_5d_quarterly.py</code>。"
else: 
    next_check = [m for m in m_months if m > now.month][0] if [m for m in m_months if m > now.month] else 1
    m_class, m_msg = "m-normal", f"✅ 系統正常。<br>下季健檢：{next_check} 月 | 年度校準：12 月。"

html_index = get_html_header("Quant Dashboard - Signals", "signal") + \
             get_config_html() + \
             cards_html + f"<div class='verdict'><div class='verdict-title {v_cls}'>{v_title}</div><div style='margin-left: 20px;'>{v_msg}</div></div>" + \
             get_html_footer(m_class, m_msg)
with open("index.html", "w", encoding="utf-8") as f: f.write(html_index)

html_trades = get_html_header("Quant Dashboard - Trades", "trade") + generate_trades_html(df_trades, df_eq) + get_html_footer(m_class, m_msg)
with open("trades.html", "w", encoding="utf-8") as f: f.write(html_trades)

print(f"✅ Main Dashboard Updated (v3.8 Strict - UI Text Synced).")