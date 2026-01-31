import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from zoneinfo import ZoneInfo

# ==========================================
# 1. 結構觀察清單 (完整版)
# ==========================================
tickers_config = {
    'Macro': {
        '^VIX': '恐慌指數 (VIX)',
        '^TNX': '10年美債 (US10Y)',
        'DX-Y.NYB': '美元指數 (DXY)',
        'BTC-USD': '比特幣 (BTC)',
        'GC=F': '黃金 (Gold)',
        'CL=F': '原油 (Oil)',
        'TLT': '20年公債 (TLT)',
        'HYG': '高收益債 (HYG)'
    },
    'Sectors': {
        'XLK': '科技 (Tech)',
        'XLF': '金融 (Financial)',
        'XLE': '能源 (Energy)',
        'XLV': '醫療 (Health)',
        'XLY': '非必消 (Discret.)',
        'XLP': '必消 (Staples)',
        'XLI': '工業 (Indust.)',
        'XLC': '通訊 (Comm.)',
        'XLB': '原物料 (Material)',
        'XLU': '公用 (Utilities)',
        'SMH': '半導體 (Semis)'
    },
    'Breadth': {
        'SPY': '標普市值 (SPY)',
        'RSP': '標普等權 (RSP)'
    }
}

all_tickers = []
for category in tickers_config.values():
    all_tickers.extend(category.keys())

# ==========================================
# 2. 數據抓取 (逐個處理，防崩潰)
# ==========================================
def get_data():
    print("⏳ 下載市場數據中 (強健模式)...")
    
    # 初始化字典
    prices = {}
    d_chg = {}
    w_chg = {}
    m_chg = {}
    
    try:
        # 下載數據
        df_all = yf.download(all_tickers, period="2y", interval="1d", progress=False)
        
        # 處理 MultiIndex (如果是多個 Ticker)
        if isinstance(df_all.columns, pd.MultiIndex):
            df_close = df_all['Close']
        else:
            # 如果只有一個 Ticker 或結構不同
            df_close = df_all
            
        # 針對每一個 Ticker 獨立處理
        for t in all_tickers:
            try:
                # 1. 取出該 Ticker 的數據並移除空值 (這步很關鍵，解決週末數據問題)
                if t in df_close.columns:
                    series = df_close[t].dropna()
                else:
                    print(f"⚠️ 警告: 找不到 {t} 的數據")
                    continue
                
                if len(series) < 2: 
                    continue

                # 2. 抓取現價
                prices[t] = series.iloc[-1]
                
                # 3. 計算漲跌 (如果長度不夠，使用 0)
                # 日漲跌
                d_chg[t] = ((series.iloc[-1] - series.iloc[-2]) / series.iloc[-2]) * 100
                
                # 週漲跌 (5天)
                if len(series) >= 6:
                    w_chg[t] = ((series.iloc[-1] - series.iloc[-6]) / series.iloc[-6]) * 100
                else:
                    w_chg[t] = 0
                    
                # 月漲跌 (22天)
                if len(series) >= 23:
                    m_chg[t] = ((series.iloc[-1] - series.iloc[-23]) / series.iloc[-23]) * 100
                else:
                    m_chg[t] = 0
                    
            except Exception as e:
                print(f"❌ 計算 {t} 時發生錯誤: {e}")
                prices[t] = 0
                d_chg[t] = 0
                w_chg[t] = 0
                m_chg[t] = 0

    except Exception as e:
        print(f"❌ 下載數據時發生嚴重錯誤: {e}")

    return prices, d_chg, w_chg, m_chg

# ==========================================
# 3. HTML 生成 (表格樣式)
# ==========================================
def generate_section_html(title, ticker_dict, prices, d_chg, w_chg, m_chg):
    rows_html = ""
    
    # 排序邏輯
    sorted_tickers = list(ticker_dict.keys())
    if title == '2. 板塊輪動 (Sectors)':
        # 板塊依照日漲幅排序
        sorted_tickers.sort(key=lambda x: d_chg.get(x, 0), reverse=True)

    for t in sorted_tickers:
        name = ticker_dict[t]
        
        # 安全取值，如果沒有數據顯示 "-"
        price = prices.get(t, 0)
        d = d_chg.get(t, 0)
        w = w_chg.get(t, 0)
        m = m_chg.get(t, 0)
        
        if price == 0 and d == 0:
            # 數據缺失時的顯示
            price_str = "-"
            d_str = "-"
            w_str = "-"
            m_str = "-"
            color_d = "gray"
            color_w = "gray"
            color_m = "gray"
        else:
            price_str = f"{price:.2f}"
            d_str = f"{d:+.2f}%"
            w_str = f"{w:+.2f}%"
            m_str = f"{m:+.2f}%"
        
            # 顏色邏輯
            is_risk = t in ['^VIX', '^TNX', 'DX-Y.NYB']
            if is_risk:
                color_d = "red" if d > 0 else "green"
                color_w = "red" if w > 0 else "green"
                color_m = "red" if m > 0 else "green"
            else:
                color_d = "green" if d > 0 else "red"
                color_w = "green" if w > 0 else "red"
                color_m = "green" if m > 0 else "red"

        rows_html += f"""
        <tr>
            <td class="col-name">
                <div style="font-weight:bold;">{name}</div>
                <div class="ticker-code">{t}</div>
            </td>
            <td class="col-price">{price_str}</td>
            <td class="{color_d}">{d_str}</td>
            <td class="{color_w} mobile-hide">{w_str}</td>
            <td class="{color_m} mobile-hide">{m_str}</td>
        </tr>
        """
        
    return f"""
    <div class="section-title">{title}</div>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th style="text-align:left;">名稱</th>
                    <th>現價</th>
                    <th>1日 %</th>
                    <th class="mobile-hide">1週 %</th>
                    <th class="mobile-hide">1月 %</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """

def generate_html(prices, d_chg, w_chg, m_chg):
    
    macro_html = generate_section_html('1. 宏觀風險 (Macro)', tickers_config['Macro'], prices, d_chg, w_chg, m_chg)
    sector_html = generate_section_html('2. 板塊輪動 (Sectors)', tickers_config['Sectors'], prices, d_chg, w_chg, m_chg)
    breadth_html = generate_section_html('3. 市場廣度 (Breadth)', tickers_config['Breadth'], prices, d_chg, w_chg, m_chg)

    # 廣度診斷
    val_spy = d_chg.get('SPY', 0)
    val_rsp = d_chg.get('RSP', 0)
    diff = val_rsp - val_spy
    
    if diff > 0.1:
        b_msg = "🟢 健康：中小股 (RSP) 強於 權值股 (SPY)"
        b_border = "#3fb950"
    elif diff < -0.1:
        b_msg = "🔴 虛弱：僅靠權值股 (SPY) 拉抬，中小股在跌"
        b_border = "#ff7b72"
    else:
        b_msg = "🟡 中性：市場表現同步"
        b_border = "#d29922"

    breadth_banner = f"""
    <div style="margin-top:20px; padding:15px; background:#161b22; border-left: 4px solid {b_border}; color:#c9d1d9;">
        <strong>市場廣度診斷：</strong> {b_msg}
    </div>
    """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Market Structure (Table)</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ background-color: #0d1117; color: #c9d1d9; font-family: 'Microsoft JhengHei', 'Consolas', sans-serif; padding: 20px; margin:0; }}
            
            .nav {{ display: flex; border-bottom: 1px solid #30363d; margin-bottom: 20px; }}
            .nav-item {{ padding: 10px 20px; text-decoration: none; color: #8b949e; font-weight: bold; }}
            .nav-item:hover {{ color: #c9d1d9; background-color: #161b22; }}
            .nav-item.active {{ color: #58a6ff; border-bottom: 2px solid #58a6ff; }}
            
            .section-title {{ border-left: 4px solid #58a6ff; padding-left: 10px; margin: 30px 0 10px 0; font-size: 1.2em; color: white; font-weight:bold; }}
            
            .table-container {{ overflow-x: auto; background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; }}
            table {{ width: 100%; border-collapse: collapse; min-width: 350px; }}
            th {{ background-color: #21262d; color: #8b949e; padding: 12px; font-size: 0.9em; text-align: right; }}
            td {{ padding: 12px; border-bottom: 1px solid #30363d; text-align: right; font-family: 'Consolas', monospace; }}
            tr:last-child td {{ border-bottom: none; }}
            
            th:first-child, td:first-child {{ text-align: left; }}
            
            .ticker-code {{ font-size: 0.8em; color: #8b949e; }}
            .col-name {{ font-family: 'Microsoft JhengHei', sans-serif; }}
            .col-price {{ color: #f0f6fc; font-weight: bold; }}

            .green {{ color: #3fb950; }}
            .red {{ color: #ff7b72; }}
            .gray {{ color: #8b949e; }}
            
            @media (max-width: 600px) {{
                .mobile-hide {{ display: none; }}
                body {{ padding: 10px; }}
                th, td {{ padding: 10px 5px; font-size: 0.9em; }}
            }}
        </style>
    </head>
    <body>
        <div class="nav">
            <a href="index.html" class="nav-item">🚀 策略訊號 (Signals)</a>
            <a href="trades.html" class="nav-item">📊 模擬回測 (Backtest)</a>
            <a href="portfolio.html" class="nav-item">💰 真實帳戶 (Portfolio)</a>
            <a href="structure.html" class="nav-item active">🏗️ 市場結構 (Structure)</a>
            <a href="structure_bottom.html" class="nav-item">📉 市場底部結構 (Bottoms)</a>
        </div>

        <div class="update-time" style="text-align:right; color:#8b949e; font-size:0.8em; margin-bottom:10px;">
            更新時間: {datetime.datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %H:%M')}
        </div>

        {macro_html}
        {sector_html}
        {breadth_html}
        {breadth_banner}

    </body>
    </html>
    """
    
    with open("structure.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ Structure Dashboard Updated (Robust Table Version)!")

if __name__ == "__main__":
    prices, d_chg, w_chg, m_chg = get_data()
    generate_html(prices, d_chg, w_chg, m_chg)