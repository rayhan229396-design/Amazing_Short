# analysis.py
import pandas as pd
import numpy as np
import ta
from datetime import datetime
import logging
from utils.data_fetcher import get_dhaka_time, fetch_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProSignalAnalyzer:
    """প্রো মার্কেট সিগন্যাল অ্যানালাইজার - ৪-লেয়ার কনফ্লুয়েন্স সিস্টেম (FIXED)"""
    
    def __init__(self):
        self.version = "2.1"
        self.signal_history = []
        self.pattern_weights = {
            'bullish_engulfing': 25,
            'bearish_engulfing': -25,
            'hammer': 20,
            'shooting_star': -20,
            'bullish_harami': 15,
            'bearish_harami': -15,
            'doji': 0
        }
        
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """সমস্ত ইন্ডিকেটর যোগ করুন"""
        if df.empty or len(df) < 50:
            return df
        
        df = df.copy()
        
        try:
            # === ট্রেন্ড ইন্ডিকেটর ===
            for period in [9, 21, 50, 200]:
                df[f"EMA_{period}"] = ta.trend.ema_indicator(df["Close"], window=period)
            
            df["SMA_20"] = ta.trend.sma_indicator(df["Close"], window=20)
            df["ADX"] = ta.trend.adx(df["High"], df["Low"], df["Close"], window=14)
            
            # === মোমেন্টাম ===
            df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
            
            macd = ta.trend.MACD(df["Close"])
            df["MACD"] = macd.macd()
            df["MACD_Signal"] = macd.macd_signal()
            df["MACD_Hist"] = macd.macd_diff()
            
            df["Stoch_K"] = ta.momentum.stoch(df["High"], df["Low"], df["Close"], window=14, smooth_window=3)
            df["Stoch_D"] = ta.momentum.stoch_signal(df["High"], df["Low"], df["Close"], window=14, smooth_window=3)
            
            # === ভোলাটিলিটি ===
            bb = ta.volatility.BollingerBands(df["Close"], window=20, window_dev=2)
            df["BB_High"] = bb.bollinger_hband()
            df["BB_Low"] = bb.bollinger_lband()
            df["BB_Mid"] = bb.bollinger_mavg()
            df["BB_Width"] = bb.bollinger_wband()
            df["BB_Position"] = (df["Close"] - df["BB_Low"]) / (df["BB_High"] - df["BB_Low"] + 1e-8)
            
            df["ATR"] = ta.volatility.average_true_range(df["High"], df["Low"], df["Close"], window=14)
            df["ATR_Percent"] = (df["ATR"] / df["Close"]) * 100
            
            # === ভলিউম ===
            if "Volume" in df.columns:
                df["Volume_SMA"] = df["Volume"].rolling(20).mean()
                df["Volume_Ratio"] = df["Volume"] / (df["Volume_SMA"] + 1e-8)
            
            # === ক্যান্ডেল ===
            df["Body"] = df["Close"] - df["Open"]
            df["Body_Size"] = abs(df["Body"])
            df["Upper_Wick"] = df["High"] - df[["Open", "Close"]].max(axis=1)
            df["Lower_Wick"] = df[["Open", "Close"]].min(axis=1) - df["Low"]
            df["Candle_Range"] = df["High"] - df["Low"]
            
            df["Market_Regime"] = self._detect_regime(df)
            
        except Exception as e:
            logger.error(f"Indicator calculation error: {e}")
            
        return df
    
    def _detect_regime(self, df: pd.DataFrame) -> str:
        """মার্কেট রেজিম ডিটেক্ট"""
        if "ADX" not in df.columns or len(df) < 20:
            return "Unknown"
        
        try:
            adx = df["ADX"].iloc[-1]
            bb_width = df["BB_Width"].iloc[-1]
            avg_bb = df["BB_Width"].rolling(20).mean().iloc[-1]
            
            if adx > 25 and bb_width > avg_bb:
                return "Strong_Trend"
            elif adx > 20:
                return "Weak_Trend"
            elif bb_width < avg_bb * 0.7:
                return "Ranging"
            else:
                return "Transition"
        except Exception:
            return "Unknown"
    
    def detect_patterns(self, df: pd.DataFrame) -> list:
        """ক্যান্ডেলস্টিক প্যাটার্ন ডিটেক্ট"""
        if len(df) < 5:
            return []
        
        patterns = []
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        try:
            body = curr["Body_Size"] if curr["Body_Size"] > 0 else 0.00001
            range_ = curr["Candle_Range"] if curr["Candle_Range"] > 0 else 0.00001
            
            # হ্যামার / শুটিং স্টার
            if curr["Lower_Wick"] >= (body * 2.0) and curr["Upper_Wick"] <= (body * 0.5):
                patterns.append(("Hammer", self.pattern_weights['hammer']))
            elif curr["Upper_Wick"] >= (body * 2.0) and curr["Lower_Wick"] <= (body * 0.5):
                patterns.append(("Shooting_Star", self.pattern_weights['shooting_star']))
            
            # ইঞ্জালফিং
            if prev["Body"] < 0 and curr["Body"] > 0 and curr["Close"] > prev["Open"]:
                patterns.append(("Bullish_Engulfing", self.pattern_weights['bullish_engulfing']))
            elif prev["Body"] > 0 and curr["Body"] < 0 and curr["Close"] < prev["Open"]:
                patterns.append(("Bearish_Engulfing", self.pattern_weights['bearish_engulfing']))
            
            # ডোজি
            if body <= (range_ * 0.1):
                patterns.append(("Doji", self.pattern_weights['doji']))
                
        except Exception:
            pass
            
        return patterns
    
    def detect_sr(self, df: pd.DataFrame) -> dict:
        """সাপোর্ট/রেজিস্ট্যান্স লেভেল অ্যানালাইসিস (FIXED LOGIC)"""
        if len(df) < 30:
            return {"zone": "Neutral", "score": 0}
        
        curr_close = df["Close"].iloc[-1]
        recent_low = df["Low"].tail(30).min()
        recent_high = df["High"].tail(30).max()
        
        score = 0
        zone = "Neutral"
        
        # সাপোর্ট ও রেজিস্ট্যান্স জোন ডিটেকশন
        if abs(curr_close - recent_low) / curr_close < 0.002:
            zone = "Support"
            score = 20
        elif abs(curr_close - recent_high) / curr_close < 0.002:
            zone = "Resistance"
            score = -20
        
        # dynamic EMA Dynamic Support/Resistance
        if "EMA_50" in df.columns:
            ema50 = df["EMA_50"].iloc[-1]
            if abs(curr_close - ema50) / curr_close < 0.0015:
                if zone == "Neutral":
                    zone = "EMA_50_Level"
                else:
                    zone += "_EMA"
                # প্রাইস EMA-র উপরে থাকলে বুলিশ বাউন্স, নিচে থাকলে বেয়ারিশ রিজেকশন
                score += 10 if curr_close >= ema50 else -10
        
        return {"zone": zone, "score": score}
    
    def check_mtf(self, pair: str) -> dict:
        """মাল্টি-টাইমফ্রেম অ্যানালাইসিস (OPTIMIZED)"""
        if not pair:
            return {"trends": {}, "score": 0}

        timeframes = ["15m", "1h", "4h"]
        trends = {}
        score = 0
        
        for tf in timeframes:
            try:
                df = fetch_data(pair, timeframe=tf, limit=30)
                if not df.empty and len(df) > 15:
                    ema9 = ta.trend.ema_indicator(df["Close"], window=9).iloc[-1]
                    ema21 = ta.trend.ema_indicator(df["Close"], window=21).iloc[-1]
                    
                    if ema9 > ema21:
                        trends[tf] = "Bullish"
                        score += 10
                    elif ema9 < ema21:
                        trends[tf] = "Bearish"
                        score -= 10
            except Exception as e:
                logger.warning(f"MTF error for {pair} on {tf}: {e}")
        
        return {"trends": trends, "score": score}
    
    def check_confluence(self, df: pd.DataFrame) -> dict:
        """৪-লেয়ার কনফ্লুয়েন্স চেক (FIXED LOGIC)"""
        latest = df.iloc[-1]
        confluence = {"bullish": 0, "bearish": 0, "signals": []}
        
        try:
            # ১. RSI + MACD
            if latest["RSI"] < 45 and latest["MACD_Hist"] > 0:
                confluence["bullish"] += 2
                confluence["signals"].append("RSI_MACD_Bullish")
            elif latest["RSI"] > 55 and latest["MACD_Hist"] < 0:
                confluence["bearish"] += 2
                confluence["signals"].append("RSI_MACD_Bearish")
            
            # ২. Bollinger Bands Overbought/Oversold
            if latest["Close"] <= latest["BB_Low"]:
                confluence["bullish"] += 2
                confluence["signals"].append("BB_Oversold")
            elif latest["Close"] >= latest["BB_High"]:
                confluence["bearish"] += 2
                confluence["signals"].append("BB_Overbought")
            
            # ৩. Stochastic Reversal
            if latest["Stoch_K"] < 20 and latest["Stoch_D"] < 20:
                confluence["bullish"] += 1
                confluence["signals"].append("Stoch_Oversold")
            elif latest["Stoch_K"] > 80 and latest["Stoch_D"] > 80:
                confluence["bearish"] += 1
                confluence["signals"].append("Stoch_Overbought")
                
        except Exception as e:
            logger.error(f"Confluence error: {e}")
            
        return confluence
    
    def generate_signal(self, df: pd.DataFrame, pair: str = "", timeframe: str = "5m") -> dict:
        """মেইন সিগন্যাল জেনারেশন"""
        if df.empty or len(df) < 50:
            return self._default_signal("Not enough data")
        
        df = self.add_indicators(df)
        latest = df.iloc[-1]
        
        score = 50.0  # Base Neutral Score
        reasons = []
        
        try:
            # ১. MTF অ্যানালাইসিস (ওয়েটেজ: ৩০%)
            mtf = self.check_mtf(pair)
            score += mtf["score"] * 0.3
            if mtf['trends']:
                reasons.append(f"MTF: {', '.join([f'{k}:{v}' for k,v in mtf['trends'].items()])}")
            
            # ২. ক্যান্ডেলস্টিক প্যাটার্ন (ওয়েটেজ: ২৫%)
            patterns = self.detect_patterns(df)
            if patterns:
                pattern_score = max(patterns, key=lambda x: abs(x[1]))[1]
                score += pattern_score * 0.25
                reasons.append(f"Pattern: {patterns[0][0]}")
            
            # ৩. সাপোর্ট ও রেজিস্ট্যান্স (ওয়েটেজ: ২০%)
            sr = self.detect_sr(df)
            score += sr["score"] * 0.2
            if sr["zone"] != "Neutral":
                reasons.append(f"SR: {sr['zone']}")
            
            # ৪. ইন্ডিকেটর কনফ্লুয়েন্স (ওয়েটেজ: ২৫%)
            confluence = self.check_confluence(df)
            conf_net = confluence["bullish"] - confluence["bearish"]
            score += (conf_net * 5) * 0.25
            if confluence["signals"]:
                reasons.append(f"Confluence: {', '.join(confluence['signals'][:2])}")
            
            # মার্কেট রেজিম ফিল্টার
            regime = df["Market_Regime"].iloc[-1] if "Market_Regime" in df.columns else "Unknown"
            if regime == "Ranging" and abs(score - 50) < 12:
                score = 50.0
                reasons.append("Ranging Market - High Risk")
            
            # ভলিউম কনফার্মেশন
            if "Volume_Ratio" in df.columns:
                vol = df["Volume_Ratio"].iloc[-1]
                if vol > 1.5:
                    if score > 55:
                        score += 4
                        reasons.append(f"High Vol Buy ({vol:.1f}x)")
                    elif score < 45:
                        score -= 4
                        reasons.append(f"High Vol Sell ({vol:.1f}x)")
            
        except Exception as e:
            logger.error(f"Signal calculation error: {e}")
            return self._default_signal(str(e))
        
        score = max(0, min(100, int(round(score))))
        
        # সিগন্যাল সিদ্ধান্ত
        if score >= 62:
            signal = "BUY"
            confidence = score
            entry = "Long Entry"
        elif score <= 38:
            signal = "SELL"
            confidence = 100 - score
            entry = "Short Entry"
        else:
            signal = "WAIT"
            confidence = 50
            entry = "None"
        
        return {
            "signal": signal,
            "confidence": confidence,
            "trend": "Bullish" if score > 55 else "Bearish" if score < 45 else "Neutral",
            "entry": entry,
            "reasons": reasons[:5],
            "price": round(float(latest["Close"]), 5),
            "time": get_dhaka_time(),
            "score": score,
            "regime": regime if 'regime' in locals() else "Unknown",
            "version": self.version
        }
    
    def _default_signal(self, error_msg: str) -> dict:
        return {
            "signal": "WAIT",
            "confidence": 0,
            "trend": "Unknown",
            "entry": "None",
            "reasons": [error_msg],
            "price": 0.0,
            "time": get_dhaka_time(),
            "score": 50,
            "regime": "Error",
            "version": self.version
        }

# ==================== ব্যাকওয়ার্ড কম্প্যাটিবিলিটি ====================

analyzer = ProSignalAnalyzer()

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    return analyzer.add_indicators(df)

def detect_candlestick_pattern(df: pd.DataFrame) -> tuple:
    patterns = analyzer.detect_patterns(df)
    if patterns:
        return patterns[0]
    return None, 0

def check_support_resistance(df: pd.DataFrame) -> tuple:
    sr = analyzer.detect_sr(df)
    return sr["zone"], sr["score"]

def check_multi_timeframe(pair: str) -> dict:
    return analyzer.check_mtf(pair)

def generate_signal(df: pd.DataFrame, pair: str = "", timeframe: str = "5m") -> dict:
    return analyzer.generate_signal(df, pair, timeframe)
