import matplotlib
matplotlib.use('Agg') # 非互動模式，防止伺服器報錯

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
# 如果 config 在上一層，請取消註解下面兩行
# parent_dir = os.path.dirname(current_dir)
# sys.path.append(parent_dir)

import config  # <--- 引入配置檔

# ==========================================
# 0. 設定
# ==========================================
OUTPUT_FILE = "structure_bottom.html"  # <--- 新的網頁檔名
TICKER = config.TICKER
LOOKBACK_YEARS = 5

# UI 顏色
plt.style.use('dark_background')
COLOR_TEXT = '#c9d1d9'
COLOR_BG = '#0d1117'
COLOR_CARD = '#161b22'

# 從 Config 讀取目前的「瞄準鏡」設定
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
# 2. 核心分析邏輯 (保留你原本的 Logic)
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
    
    # 找出顯著的波段低點 (Local Minima)
    # 使用 argrelextrema 找出左右 20 天內的最低點 (這是你原本的邏輯)
    n = 20 
    df['Min'] = df.iloc[argrelextrema(df['Close'].values, np.less_equal, order=n)[0]]['Close']
    
    # 篩選出顯著低點 (跌破 SMA200 且 發生在局部低點)
    deep_bottoms = df[(df['Min'] > 0) & (df['Close'] < df['SMA200'])].copy()
    
    return df, deep_bottoms

# ==========================================
# 3. 圖表繪製
# ==========================================
def generate_structure_chart(df, bottoms):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, height_ratios=[3, 1], facecolor=COLOR_CARD)
    
    # 上圖：價格與 SMA200
    ax1.set_facecolor(COLOR_CARD)
    ax1.plot(df.index, df['Close'], color='white', linewidth=1, label='Price')
    ax1.plot(df.index, df['SMA200'], color='gray', linestyle='--', linewidth=1, label='SMA200')
    
    # 標記底部
    ax1.scatter(bottoms.index, bottoms['Close'], color='#f0883e', s=50, zorder=5, label='Bear Bottoms')
    
    ax1.set_title(f"{TICKER} Market Bottom Structure (Last {LOOKBACK_YEARS} Years)", color=COLOR_TEXT, fontsize=14)
    ax1.set_ylabel("Price", color=COLOR_TEXT)
    ax1.legend(facecolor=COLOR_CARD, edgecolor='#30363d', labelcolor='white')
    ax1.grid(True, color='#30363d', linestyle=':', alpha=0.5)
    
    # 下圖：RSI
    ax2.set_facecolor(COLOR_CARD)
    ax2.plot(df.index, df['RSI'], color='#58a6ff', linewidth=1)
    ax2.axhline(30, color='red', linestyle='--', linewidth=0.8)
    ax2.axhline(Current_Sniper_RSI, color='#f0883e', linestyle=':', linewidth=1, label=f'Current Threshold ({Current_Sniper_RSI})')
    ax2.set_ylabel("RSI", color=COLOR_TEXT)
    ax2.set_ylim(10, 80)
    ax2.grid(True, color='#30363d', linestyle=':', alpha=0.5)
    
    # X 軸格式
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax2.get_xticklabels(), rotation=45, ha='right', color=COLOR_TEXT)
    ax1.tick_params(colors=COLOR_TEXT)
    ax2.tick_params(colors=COLOR_TEXT)
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100, facecolor=COLOR_CARD)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

# ==========================================
# 4. HTML 生成
# ==========================================
def generate_html(df, bottoms, chart_b64):
    
    # 統計數據
    rsi_vals = []
    bias_vals = []
    missed_count = 0
    table_rows = ""
    
    for idx, row in bottoms.iterrows():
        d_str = idx.strftime('%Y-%m-%d')
        rsi = row['RSI']
        bias = row['Bias']
        
        rsi_vals.append(rsi)
        bias_vals.append(bias)
        
        is_triggered = (rsi < Current_Sniper_RSI and bias < Current_Sniper_Bias)
        status = "<span class='green'>✅ CAUGHT</span>" if is_triggered else "<span class='red'>❌ MISSED</span>"
        if not is_triggered: missed_count += 1
            
        table_rows += f"""
        <tr>
            <td>{d_str}</td>
            <td>{row['Close']:.2f}</td>
            <td>{rsi:.1f}</td>
            <td>{bias*100:.1f}%</td>
            <td>{status}</td>
        </tr>
        """
        
    avg_rsi = np.mean(rsi_vals) if rsi_vals else 0
    avg_bias = np.mean(bias_vals) if bias_vals else 0
    miss_rate = (missed_count / len(bottoms) * 100) if not bottoms.empty else 0
    
    # 診斷訊息
    if avg_rsi > Current_Sniper_RSI:
        diag_color = "red"
        diag_msg = f"⚠️ 警告: 平均底部 RSI ({avg_rsi:.1f}) 高於設定值 ({Current_Sniper_RSI})，可能導致錯過進場機會。"
    elif miss_rate > 50:
        diag_color = "red"
        diag_msg = f"❌ 嚴重: 錯失率高達 {miss_rate:.0f}%，請放寬 Sniper 條件。"
    else:
        diag_color = "green"
        diag_msg = "✅ 健康: 目前參數能有效捕捉大部分歷史底部。"

    # [新分頁] 導航列：新增了「市場底部結構」
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
            {"""
            .nav { display: flex; border-bottom: 1px solid #30363d; margin-bottom: 20px; flex-wrap: wrap; }
            .nav-item { padding: 10px 20px; text-decoration: none; color: #8b949e; font-weight: bold; cursor: pointer; }
            .nav-item:hover { color: #c9d1d9; background-color: #161b22; }
            .nav-item.active { color: #58a6ff; border-bottom: 2px solid #58a6ff; }
            """}
            .card {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; margin-bottom: 20px; }}
            .header {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #30363d; padding-bottom: 5px; }}
            
            .stat-box {{ display: flex; justify-content: space-around; text-align: center; margin-bottom: 20px; }}
            .stat-val {{ font-size: 1.5em; font-weight: bold; margin-top: 5px; color: #c9d1d9; }}
            .green {{ color: #3fb950; }} .red {{ color: #ff7b72; }} .orange {{ color: #f0883e; }} .gray {{ color: #8b949e; }}
            
            table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #30363d; }}
            th {{ color: #8b949e; }}
            tr:hover {{ background-color: #21262d; }}
            
            .chart-container {{ text-align: center; margin-top: 20px; }}
            .chart-img {{ max-width: 100%; height: auto; border: 1px solid #30363d; border-radius: 6px; }}
            
            .diag-box {{ padding: 10px; border-radius: 6px; background-color: rgba(255,255,255,0.05); border-left: 5px solid {diag_color}; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        {nav_html}
        
        <div style="text-align:right; color:#8b949e; font-size:0.8em; margin-bottom:10px;">
            更新: {datetime.datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %H:%M')}
        </div>

        <div class="card">
            <div class="header orange">📉 市場底部結構分析 (Bottoms Analysis)</div>
            
            <div class="stat-box">
                <div><div class="gray">平均底部 RSI</div><div class="stat-val">{avg_rsi:.1f}</div></div>
                <div><div class="gray">平均底部 Bias</div><div class="stat-val">{avg_bias*100:.1f}%</div></div>
                <div><div class="gray">Sniper 捕捉率</div><div class="stat-val {diag_color}">{100-miss_rate:.0f}%</div></div>
            </div>
            
            <div class="diag-box" style="color: {diag_color};">
                {diag_msg}
            </div>

            <div class="chart-container">
                <img class="chart-img" src="data:image/png;base64,{chart_b64}">
            </div>
        </div>

        <div class="card">
            <div class="header gray">📋 歷史底部詳細數據</div>
            <table>
                <thead>
                    <tr>
                        <th>日期</th><th>價格</th><th>RSI</th><th>乖離率 (Bias)</th><th>狀態</th>
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
    if not bottoms.empty:
        chart_b64 = generate_structure_chart(df, bottoms)
        generate_html(df, bottoms, chart_b64)
    else:
        print("⚠️ 無法生成報告：過去 5 年沒有符合條件的底部。")