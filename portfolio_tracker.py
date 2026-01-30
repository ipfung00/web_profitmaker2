import matplotlib
# [關鍵修正] 必須在 import pyplot 之前設定 Agg 模式
matplotlib.use('Agg') 

import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os
import io
import base64
import datetime
from zoneinfo import ZoneInfo
import config  # <--- 引入配置檔

# ==========================================
# 設定
# ==========================================
LEDGER_FILE = 'real_trades.csv'
BENCHMARK = 'QQQ'
OUTPUT_HTML = 'portfolio.html'

# UI 風格 (從 config 讀取，確保全站統一)
plt.style.use('dark_background')
# [優化] 使用 config 內的顏色，如果找不到則使用預設值
COLOR_MY_EQ = config.UI_COLORS.get('STRAT_LINE', '#00ff00') 
COLOR_BENCH = config.UI_COLORS.get('BH_LINE', '#808080')

# ==========================================
# 核心邏輯
# ==========================================
def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        print(f"❌ 找不到帳本: {LEDGER_FILE}")
        return None
    df = pd.read_csv(LEDGER_FILE)
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date')

def calculate_portfolio(df_trades):
    if df_trades is None or df_trades.empty: return None, None
    start_date = df_trades['Date'].min()
    end_date = datetime.datetime.now()
    
    print(f"📥 下載市場數據 ({start_date.date()} ~ Now)...")
    market_data = yf.download(BENCHMARK, start=start_date, progress=False)['Close']
    if isinstance(market_data, pd.DataFrame): market_data = market_data.iloc[:, 0]
    
    dates = pd.date_range(start_date, end_date, freq='D')
    portfolio_history = []
    
    cash = 0.0
    shares = 0.0
    total_invested = 0.0
    trade_idx = 0
    
    for d in dates:
        while trade_idx < len(df_trades) and df_trades.iloc[trade_idx]['Date'] <= d:
            t = df_trades.iloc[trade_idx]
            amt = t['Price'] * t['Shares']
            if t['Action'] == 'DEPOSIT': cash += amt; total_invested += amt
            elif t['Action'] == 'WITHDRAW': cash -= amt; total_invested -= amt
            elif t['Action'] == 'BUY': cash -= (amt + t['Fee']); shares += t['Shares']
            elif t['Action'] == 'SELL': cash += (amt - t['Fee']); shares -= t['Shares']
            trade_idx += 1
            
        try:
            price = market_data.asof(d)
            if pd.isna(price): price = 0
        except: price = 0
            
        equity = cash + (shares * price)
        ret = (equity - total_invested) / total_invested * 100 if total_invested > 0 else 0.0
        
        portfolio_history.append({'Date': d, 'Equity': equity, 'Return': ret})
        
    return pd.DataFrame(portfolio_history).set_index('Date'), market_data

def generate_report(df_port, market_data):
    # Benchmark
    start_price = market_data.asof(df_port.index[0])
    qqq_ret = (market_data - start_price) / start_price * 100
    df_port['QQQ_Return'] = qqq_ret.reindex(df_port.index, method='ffill')
    
    # Plot
    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#161b22')
    ax.set_facecolor('#161b22')
    ax.plot(df_port.index, df_port['Return'], color=COLOR_MY_EQ, linewidth=2, label='Real Portfolio')
    ax.plot(df_port.index, df_port['QQQ_Return'], color=COLOR_BENCH, linestyle='--', linewidth=1.5, label='QQQ')
    ax.fill_between(df_port.index, df_port['Return'], df_port['QQQ_Return'], where=(df_port['Return']>df_port['QQQ_Return']), color='green', alpha=0.1, interpolate=True)
    ax.fill_between(df_port.index, df_port['Return'], df_port['QQQ_Return'], where=(df_port['Return']<=df_port['QQQ_Return']), color='red', alpha=0.1, interpolate=True)
    ax.set_title("Real Account Performance vs QQQ", color='white', fontsize=14)
    ax.set_ylabel("Return (%)", color='#8b949e')
    ax.legend(fontsize=10, facecolor='#161b22', edgecolor='#30363d', labelcolor='white')
    ax.grid(True, color='#30363d', linestyle=':', alpha=0.5)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.tick_params(colors='#8b949e')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100, facecolor='#161b22')
    plt.close(fig)
    buf.seek(0)
    chart_b64 = base64.b64encode(buf.read()).decode('utf-8')
    
    # HTML
    cur_eq = df_port['Equity'].iloc[-1]
    cur_ret = df_port['Return'].iloc[-1]
    cur_qqq = df_port['QQQ_Return'].iloc[-1]
    diff = cur_ret - cur_qqq
    diff_cls = "green" if diff > 0 else "red"
    
    df_ledger = pd.read_csv(LEDGER_FILE).sort_values('Date', ascending=False)
    table_html = df_ledger.to_html(index=False, classes="table", border=0, justify='left')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Portfolio Tracker</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ background-color: #0d1117; color: #c9d1d9; font-family: 'Microsoft JhengHei', sans-serif; padding: 20px; margin: 0; }}
            .nav {{ display: flex; border-bottom: 1px solid #30363d; margin-bottom: 20px; }}
            .nav-item {{ padding: 10px 20px; text-decoration: none; color: #8b949e; font-weight: bold; cursor: pointer; }}
            .nav-item:hover {{ color: #c9d1d9; background-color: #161b22; }}
            .nav-item.active {{ color: #58a6ff; border-bottom: 2px solid #58a6ff; }}
            .card {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; margin-bottom: 20px; }}
            .stat-box {{ display: flex; justify-content: space-around; text-align: center; margin-bottom: 20px; }}
            .stat-val {{ font-size: 1.5em; font-weight: bold; margin-top: 5px; }}
            .green {{ color: #3fb950; }} .red {{ color: #ff7b72; }} .gray {{ color: #8b949e; }} .text-white {{ color: #c9d1d9; }}
            
            table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #30363d; }}
            th {{ color: #8b949e; }}
            tr:hover {{ background-color: #21262d; }}
        </style>
    </head>
    <body>
        <div class="nav">
            <a href="index.html" class="nav-item">🚀 策略訊號 (Signals)</a>
            <a href="trades.html" class="nav-item">📊 模擬回測 (Backtest)</a>
            <a href="portfolio.html" class="nav-item active">💰 真實帳戶 (Portfolio)</a>
            <a href="structure.html" class="nav-item">🏗️ 市場結構 (Structure)</a>
        </div>
        <div style="text-align:right; color:#8b949e; font-size:0.8em; margin-bottom:10px;">
            更新: {datetime.datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %H:%M')}
        </div>
        
        <div class="card">
            <div class="stat-box">
                <div><div class="gray">總淨值</div><div class="stat-val text-white">${cur_eq:,.0f}</div></div>
                <div><div class="gray">我的報酬</div><div class="stat-val {diff_cls}">{cur_ret:+.2f}%</div></div>
                <div><div class="gray">QQQ 報酬</div><div class="stat-val gray">{cur_qqq:+.2f}%</div></div>
                <div><div class="gray">Alpha</div><div class="stat-val {diff_cls}">{diff:+.2f}%</div></div>
            </div>
            <div style="text-align: center;"><img src="data:image/png;base64,{chart_b64}" style="max-width:100%"></div>
        </div>
        
        <div class="card">
            <div class="gray" style="margin-bottom:10px; font-weight:bold;">📝 交易日記 (Ledger)</div>
            {table_html}
        </div>
    </body>
    </html>
    """
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f: f.write(html)
    print(f"✅ 真實帳戶報告已生成: {OUTPUT_HTML}")

if __name__ == "__main__":
    print("💰 啟動真實帳戶追蹤器...")
    df_t = load_ledger()
    if df_t is not None:
        df_p, m_data = calculate_portfolio(df_t)
        if df_p is not None: generate_report(df_p, m_data)