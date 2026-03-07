import matplotlib
matplotlib.use('Agg') # 非互動模式

import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf
import datetime
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.signal import argrelextrema
import io
import base64

# ==========================================
# 路徑修正 & Config 讀取
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
import config  # <--- 引入配置檔

# ==========================================
# 0. 設定
# ==========================================
OUTPUT_FILE = "structure_bottom.html"
TICKER = config.TICKER
LOOKBACK_YEARS = 10

plt.style.use('dark_background')
COLOR_TEXT = '#c9d1d9'
COLOR_BG = '#0d1117'
COLOR_CARD = '#161b22'

Current_Sniper_RSI = config.SNIPER_PARAMS['RSI_THRESHOLD']
Current_Sniper_Bias = config.SNIPER_PARAMS['BIAS_THRESHOLD']

# ==========================================
# 1. 輔助函數
# ==========================================
def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ==========================================
# 2. 核心分析邏輯
# ==========================================
def analyze_structure():
    print(f"🔍 正在分析 {TICKER} 過去 {LOOKBACK_YEARS} 年的市場底部結構...")
    
    start_date = (pd.Timestamp.now() - pd.DateOffset(years=LOOKBACK_YEARS)).strftime('%Y-%m-%d')
    df = yf.download(TICKER, start=start_date, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    # 計算指標
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    df['RSI'] = calculate_rsi(df['Close'], 14)
    df['Bias'] = (df['Close'] - df['SMA200']) / df['SMA200']
    
    # 找出顯著的波段低點 (過濾掉太近的雜訊)
    n = 20 
    df['Min'] = df.iloc[argrelextrema(df['Close'].values, np.less_equal, order=n)[0]]['Close']
    
    # 篩選出顯著低點 (必須在年線之下才算真正的恐慌底)
    deep_bottoms = df[(df['Min'] > 0) & (df['Close'] < df['SMA200'])].copy()
    
    return df, deep_bottoms

# ==========================================
# 3. 圖表繪製 (改善 2: 加入 Bias 乖離率子圖)
# ==========================================
def generate_structure_chart(df, bottoms):
    # 改為 3 層圖表
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True, height_ratios=[3, 1, 1], facecolor=COLOR_CARD)
    
    # --- 上圖：價格與 SMA200 ---
    ax1.set_facecolor(COLOR_CARD)
    ax1.plot(df.index, df['Close'], color='white', linewidth=1, label='Price')
    ax1.plot(df.index, df['SMA200'], color='gray', linestyle='--', linewidth=1, label='SMA200')
    ax1.scatter(bottoms.index, bottoms['Close'], color='#f0883e', s=50, zorder=5, label='Bear Bottoms')
    
    ax1.set_title(f"{TICKER} Market Bottom Structure (Last {LOOKBACK_YEARS} Years)", color=COLOR_TEXT, fontsize=14)
    ax1.set_ylabel("Price", color=COLOR_TEXT)
    ax1.legend(facecolor=COLOR_CARD, edgecolor='#30363d', labelcolor='white')
    ax1.grid(True, color='#30363d', linestyle=':', alpha=0.5)
    
    # --- 中圖：RSI ---
    ax2.set_facecolor(COLOR_CARD)
    ax2.plot(df.index, df['RSI'], color='#58a6ff', linewidth=1)
    ax2.axhline(30, color='gray', linestyle='--', linewidth=0.8)
    ax2.axhline(Current_Sniper_RSI, color='#f0883e', linestyle=':', linewidth=1.5, label=f'RSI Threshold ({Current_Sniper_RSI})')
    ax2.set_ylabel("RSI", color=COLOR_TEXT)
    ax2.set_ylim(10, 80)
    ax2.legend(loc='upper right', facecolor=COLOR_CARD, edgecolor='#30363d', labelcolor='white', fontsize='small')
    ax2.grid(True, color='#30363d', linestyle=':', alpha=0.5)

    # --- 下圖：Bias 乖離率 ---
    ax3.set_facecolor(COLOR_CARD)
    ax3.plot(df.index, df['Bias'] * 100, color='#a371f7', linewidth=1)
    ax3.axhline(0, color='gray', linestyle='--', linewidth=0.8)
    ax3.axhline(Current_Sniper_Bias * 100, color='#f0883e', linestyle=':', linewidth=1.5, label=f'Bias Threshold ({Current_Sniper_Bias*100:.1f}%)')
    ax3.set_ylabel("Bias (%)", color=COLOR_TEXT)
    ax3.legend(loc='lower right', facecolor=COLOR_CARD, edgecolor='#30363d', labelcolor='white', fontsize='small')
    ax3.grid(True, color='#30363d', linestyle=':', alpha=0.5)
    
    # X 軸格式
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax3.get_xticklabels(), rotation=45, ha='right', color=COLOR_TEXT)
    ax1.tick_params(colors=COLOR_TEXT)
    ax2.tick_params(colors=COLOR_TEXT)
    ax3.tick_params(colors=COLOR_TEXT)
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100, facecolor=COLOR_CARD)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

# ==========================================
# 4. HTML 生成 (改善 1: 加入容錯時間窗)
# ==========================================
def generate_html(df, bottoms, chart_b64):
    
    rsi_vals = []
    bias_vals = []
    missed_count = 0
    table_rows = ""
    
    for idx, row in bottoms.iterrows():
        d_str = idx.strftime('%Y-%m-%d')
        
        # 建立容錯時間窗：往前 5 天到往後 5 天 (涵蓋真正的交易日)
        start_date = idx - pd.Timedelta(days=5)
        end_date = idx + pd.Timedelta(days=5)
        window_df = df.loc[start_date:end_date]
        
        # 檢查視窗內是否曾經觸發過 Sniper 條件
        triggered_in_window = window_df[(window_df['RSI'] < Current_Sniper_RSI) & (window_df['Bias'] < Current_Sniper_Bias)]
        
        if not triggered_in_window.empty:
            # 如果有觸發，找出觸發時最極端的那一天來顯示
            best_trigger = triggered_in_window.loc[triggered_in_window['Bias'].idxmin()]
            rsi_to_show = best_trigger['RSI']
            bias_to_show = best_trigger['Bias']
            trigger_date_str = best_trigger.name.strftime('%m-%d')
            
            # 若不是在最低點當天觸發，加上小字提示
            if best_trigger.name == idx:
                status = "<span class='green bold'>✅ CAUGHT (精準)</span>"
            else:
                status = f"<span class='green'>✅ CAUGHT</span><br><small class='gray'>(於 {trigger_date_str} 觸發)</small>"
        else:
            # 完全沒觸發，顯示最低點當天的數據
            rsi_to_show = row['RSI']
            bias_to_show = row['Bias']
            status = "<span class='red bold'>❌ MISSED</span>"
            missed_count += 1
            
        rsi_vals.append(rsi_to_show)
        bias_vals.append(bias_to_show)
            
        table_rows += f"""
        <tr>
            <td>{d_str}</td>
            <td>{row['Close']:.2f}</td>
            <td>{rsi_to_show:.1f}</td>
            <td>{bias_to_show*100:.1f}%</td>
            <td>{status}</td>
        </tr>
        """
        
    avg_rsi = np.mean(rsi_vals) if rsi_vals else 0
    avg_bias = np.mean(bias_vals) if bias_vals else 0
    miss_rate = (missed_count / len(bottoms) * 100) if not bottoms.empty else 0
    
    if avg_rsi > Current_Sniper_RSI:
        diag_color = "red"
        diag_msg = f"⚠️ 警告: 平均底部 RSI ({avg_rsi:.1f}) 高於設定值 ({Current_Sniper_RSI})。"
    elif miss_rate > 50:
        diag_color = "red"
        diag_msg = f"❌ 嚴重: 即使有容錯窗，錯失率仍高達 {miss_rate:.0f}%，請考慮放寬 Sniper 條件。"
    else:
        diag_color = "green"
        diag_msg = "✅ 健康: 目前參數能有效涵蓋並捕捉大部分歷史底部。"

    nav_css = """
        .nav { display: flex; border-bottom: 1px solid #30363d; margin-bottom: 20px; flex-wrap: wrap; }
        .nav-item { padding: 10px 20px; text-decoration: none; color: #8b949e; font-weight: bold; cursor: pointer; }
        .nav-item:hover { color: #c9d1d9; background-color: #161b22; }
        .nav-item.active { color: #58a6ff; border-bottom: 2px solid #58a6ff; }
    """

    nav_html = """
    <div class="nav">
        <a href="index.html" class="nav-item">🚀 策略訊號 (Signals)</a>
        <a href="trades.html" class="nav-item">📊 模擬回測 (Backtest)</a>
        <a href="portfolio.html" class="nav-item">💰 真實帳戶 (Portfolio)</a>
        <a href="structure.html" class="nav-item">🏗️ 市場結構 (Structure)</a>
        <a href="structure_bottom.html" class="nav-item active">📉 市場底部結構 (Bottoms)</a>
    </div>
    """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Market Bottom Structure</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ background-color: #0d1117; color: #c9d1d9; font-family: 'Microsoft JhengHei', sans-serif; padding: 20px; margin: 0; }}
            {nav_css}
            .card {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; margin-bottom: 20px; }}
            .header {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #30363d; padding-bottom: 5px; }}
            
            .stat-box {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 15px; }}
            .stat-box div {{ background-color: #21262d; padding: 10px 15px; border-radius: 6px; flex: 1; min-width: 120px; text-align: center; border: 1px solid #30363d; }}
            .stat-val {{ font-size: 1.5em; font-weight: bold; margin-top: 5px; }}
            
            .green {{ color: #3fb950; }} .red {{ color: #ff7b72; }} .gray {{ color: #8b949e; }} .cyan {{ color: #58a6ff; }} .bold {{ font-weight: bold; }}
            
            .chart-container {{ margin-top: 15px; text-align: center; }}
            .chart-img {{ max-width: 100%; height: auto; display: block; border: 1px solid #30363d; border-radius: 6px; }}
            
            table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; text-align: center; }}
            th, td {{ padding: 10px; border-bottom: 1px solid #30363d; }}
            th {{ color: #8b949e; background-color: #21262d; }}
            tr:hover {{ background-color: #21262d; }}
            
            .diag-box {{ padding: 15px; border: 1px dashed; border-radius: 6px; font-weight: bold; text-align: center; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        {nav_html}
        
        <div class="card">
            <div class="header cyan">📉 過去 {LOOKBACK_YEARS} 年熊市底部結構健檢</div>
            <div style="color:#8b949e; margin-bottom: 15px;">
                目前設定 Sniper 門檻: <b>RSI < {Current_Sniper_RSI}</b> 且 <b>乖離率 < {Current_Sniper_Bias*100:.1f}%</b><br>
                <small>* 判定標準：在歷史低點發生前後 5 天內曾觸發，即視為成功捕捉 (CAUGHT)。</small>
            </div>
            
            <div class="stat-box">
                <div><div class="gray">歷史大底次數</div><div class="stat-val">{len(bottoms)} 次</div></div>
                <div><div class="gray">平均底部 RSI</div><div class="stat-val">{avg_rsi:.1f}</div></div>
                <div><div class="gray">平均底部 Bias</div><div class="stat-val">{avg_bias*100:.1f}%</div></div>
                <div><div class="gray">Sniper 捕捉率</div><div class="stat-val {diag_color}">{100-miss_rate:.0f}%</div></div>
            </div>
            
            <div class="diag-box" style="color: {diag_color}; border-color: {diag_color}; background-color: rgba(0,0,0,0.2);">
                {diag_msg}
            </div>

            <div class="chart-container">
                <img class="chart-img" src="data:image/png;base64,{chart_b64}">
            </div>
        </div>

        <div class="card">
            <div class="header gray">📋 歷史底部詳細數據 (容錯時間窗判定)</div>
            <table>
                <thead>
                    <tr>
                        <th>波段最低點日期</th><th>最低價格</th><th>觸發 RSI</th><th>觸發乖離率 (Bias)</th><th>判定狀態</th>
                    </tr>
                </thead>
                <tbody>{table_rows}</tbody>
            </table>
        </div>
    </body>
    </html>
    """
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 市場底部報告已生成: {OUTPUT_FILE}")

# ==========================================
# 5. 主程式
# ==========================================
if __name__ == "__main__":
    df, bottoms = analyze_structure()
    chart_b64 = generate_structure_chart(df, bottoms)
    generate_html(df, bottoms, chart_b64)