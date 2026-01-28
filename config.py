# ==========================================
# 🎯 SYSTEM CONFIGURATION (中央參數庫)
# ==========================================
# 這是系統的「大腦」。修改此處參數，main.py 和 scan 腳本都會自動更新。

# --- 1. 交易標的 ---
TICKER = "QQQ"
START_DATE = "2006-01-01"
INITIAL_CAPITAL = 10000

# --- 2. 👑 Core Strategy (核心策略參數) ---
# 來源: 季度健檢 (scan_5d_quarterly.py)
CORE_PARAMS = {
    'LOOKBACK': 98,        # 回溯天數
    'BINS': 7,             # 價格分箱數
    'VA_PCT': 0.80,        # 價值區成交量佔比
    'ATR_MULT': 2.7,       # ATR 通道倍數
    'PANIC_MULT': 2.0      # 恐慌定義倍數
}

# --- 3. 🔫 Sniper Strategy (狙擊手參數) ---
# 來源: 深海掃描 & 出場監測
SNIPER_PARAMS = {
    'RSI_THRESHOLD': 30,       # 狙擊進場 RSI < 30
    'BIAS_THRESHOLD': -0.11,   # 狙擊進場 乖離率 < -11%
    'SIZE': 0.5,               # 狙擊倉位佔比 (0.5 = 50%)
    'STOP_LOOKBACK': 14        # 狙擊出場 回溯天數 (14天)
}

# --- 4. 🎨 UI & 報告顏色設定 ---
UI_COLORS = {
    'ATR_STOP': '#e5534b',     # 紅色 (長線止盈)
    'SNIPER_STOP': '#ff79c6'   # 亮粉色 (短線止損)
}