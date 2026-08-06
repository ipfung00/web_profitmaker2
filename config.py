# ==========================================
# 🎯 SYSTEM CONFIGURATION (中央參數庫)
# ==========================================
# 這是系統的「大腦」。修改此處參數，全系統都會自動同步。

# --- 1. 交易標的 ---
TICKER = "QQQ"
START_DATE = "2019-01-01"
INITIAL_CAPITAL = 10000

# --- 2. 👑 Core Strategy (核心策略參數) ---
# 來源: 季度健檢 (scan_5d_quarterly.py)
CORE_PARAMS = {
    'LOOKBACK': 102,        # 回溯天數
    'BINS': 8,             # 價格分箱數
    'VA_PCT': 0.83,        # 價值區成交量佔比
    'ATR_MULT': 2.9,       # ATR 通道倍數
    'PANIC_MULT': 2      # 恐慌定義倍數
}

# --- 3. 🔫 Sniper Strategy (狙擊手參數) ---
# 來源: 深海掃描 & 出場監測
SNIPER_PARAMS = {
    'RSI_THRESHOLD': 27,       # <--- 從 30 改為 27 (避開 Overfit 雜訊)
    'BIAS_THRESHOLD': -0.11,   # <--- 維持 -11% (最完美的恐慌深度)
    'SIZE': 1,                 # <--- 剛才改的 100% 資金全倉接刀
    'STOP_LOOKBACK': 14        
}

# --- 4. 🎨 UI & 報告顏色設定 (全系統統一) ---
UI_COLORS = {
    # 止盈止損線
    'ATR_STOP': '#e5534b',     # 紅色 (長線止盈)
    'SNIPER_STOP': '#ff79c6',  # 亮粉色 (短線止損)
    
    # 資金曲線
    'STRAT_LINE': '#00ff00',   # 策略淨值 (螢光綠)
    'BH_LINE': '#808080',      # QQQ/B&H 基準 (灰色)
    
    # 交易訊號點
    'BUY_CORE': '#00ffff',     # Core 買入 (青色)
    'BUY_SNIPER': '#ffd700',   # Sniper 買入 (金色)
    'SELL': '#ff00ff'          # 賣出 (洋紅色)
}