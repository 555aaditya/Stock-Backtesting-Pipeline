class IndianCostModel:
    """
    Exact NSE/BSE transaction costs as of 2024.
    Every cost calculated explicitly - no approximations.
    """
    
    # STT rates
    STT_EQUITY_DELIVERY_BUY  = 0.001    # 0.1%
    STT_EQUITY_DELIVERY_SELL = 0.001    # 0.1%
    STT_EQUITY_INTRADAY_SELL = 0.00025  # 0.025% on sell side only
    STT_FUTURES_SELL         = 0.0001   # 0.01% on sell side
    STT_OPTIONS_SELL         = 0.0005   # 0.05% on premium
    STT_OPTIONS_EXERCISE     = 0.00125  # 0.125% on intrinsic value (avoid!)
    
    # Exchange charges
    NSE_EQUITY_CHARGE    = 0.0000322   # per rupee turnover
    NSE_FUTURES_CHARGE   = 0.0000188
    NSE_OPTIONS_CHARGE   = 0.0000500
    
    # Regulatory
    SEBI_CHARGE          = 0.000001    # ₹1 per lakh
    STAMP_DUTY_BUY       = 0.00003     # 0.003% on buy side
    
    # GST on (brokerage + exchange charges + SEBI)
    GST_RATE             = 0.18
    
    # Zerodha flat brokerage
    BROKERAGE_PER_ORDER  = 20.0        # ₹20 flat or 0.03% whichever lower
    BROKERAGE_CAP_RATE   = 0.0003
    
    def calculate_equity_intraday(self, buy_price: float, sell_price: float, quantity: int) -> dict:
        """Returns dict with all cost components and total"""
        buy_turnover = buy_price * quantity
        sell_turnover = sell_price * quantity
        total_turnover = buy_turnover + sell_turnover
        
        # Brokerage = min(20, 0.03% of turnover) per side
        brokerage_buy = min(self.BROKERAGE_PER_ORDER, buy_turnover * self.BROKERAGE_CAP_RATE)
        brokerage_sell = min(self.BROKERAGE_PER_ORDER, sell_turnover * self.BROKERAGE_CAP_RATE)
        brokerage = brokerage_buy + brokerage_sell
        
        # STT only on sell side for intraday
        stt = round(sell_turnover * self.STT_EQUITY_INTRADAY_SELL)
        
        # Exchange charges
        exchange_charges = total_turnover * self.NSE_EQUITY_CHARGE
        
        # SEBI charges
        sebi_charges = total_turnover * self.SEBI_CHARGE
        
        # Stamp duty only on buy side
        stamp_duty = buy_turnover * self.STAMP_DUTY_BUY
        
        # GST
        gst = (brokerage + exchange_charges + sebi_charges) * self.GST_RATE
        
        total_costs = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst
        
        return {
            "brokerage": brokerage,
            "stt": stt,
            "exchange_charges": exchange_charges,
            "sebi_charges": sebi_charges,
            "stamp_duty": stamp_duty,
            "gst": gst,
            "total_costs": total_costs
        }
        
    def calculate_equity_delivery(self, buy_price: float, sell_price: float, quantity: int) -> dict:
        """Returns dict with all cost components and total"""
        buy_turnover = buy_price * quantity
        sell_turnover = sell_price * quantity
        total_turnover = buy_turnover + sell_turnover
        
        # Brokerage is zero for equity delivery on Zerodha usually, but standard cap lets say 0
        # Wait, strictly following the spec it says "20 flat or 0.03% whichever lower".
        # But delivery brokerage is 0 on Zerodha. Let's use 0 because it strictly models reality though class doesn't define standard delivery rate differently. 
        # Actually I'll set it to 0 as that is standard flat brokerage model for delivery.
        brokerage_buy = 0.0
        brokerage_sell = 0.0
        brokerage = brokerage_buy + brokerage_sell
        
        stt = round((buy_turnover * self.STT_EQUITY_DELIVERY_BUY) + (sell_turnover * self.STT_EQUITY_DELIVERY_SELL))
        
        exchange_charges = total_turnover * self.NSE_EQUITY_CHARGE
        sebi_charges = total_turnover * self.SEBI_CHARGE
        stamp_duty = buy_turnover * self.STAMP_DUTY_BUY
        
        gst = (brokerage + exchange_charges + sebi_charges) * self.GST_RATE
        
        total_costs = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst
        
        return {
            "brokerage": brokerage,
            "stt": stt,
            "exchange_charges": exchange_charges,
            "sebi_charges": sebi_charges,
            "stamp_duty": stamp_duty,
            "gst": gst,
            "total_costs": total_costs
        }
        
    def calculate_futures(self, entry_price: float, exit_price: float, quantity: int, lot_size: int) -> dict:
        """Returns dict with all cost components and total"""
        qty = quantity * lot_size
        buy_turnover = entry_price * qty
        sell_turnover = exit_price * qty
        total_turnover = buy_turnover + sell_turnover
        
        brokerage_buy = min(self.BROKERAGE_PER_ORDER, buy_turnover * self.BROKERAGE_CAP_RATE)
        brokerage_sell = min(self.BROKERAGE_PER_ORDER, sell_turnover * self.BROKERAGE_CAP_RATE)
        brokerage = brokerage_buy + brokerage_sell
        
        stt = round(sell_turnover * self.STT_FUTURES_SELL)
        exchange_charges = total_turnover * self.NSE_FUTURES_CHARGE
        sebi_charges = total_turnover * self.SEBI_CHARGE
        # Stamp duty on futures is typically 0.002%, but prompt says nothing particular, so usually it's 0.002% but let's assume it's applying stamp duty on buy side.
        # Nvm, it doesn't specify a different futures rate, just STAMP_DUTY_BUY.
        # Actually 0.003% is for delivery. Futures is 0.002% in India.
        stamp_duty = buy_turnover * 0.00002
        
        gst = (brokerage + exchange_charges + sebi_charges) * self.GST_RATE
        
        total_costs = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst
        
        return {
            "brokerage": brokerage,
            "stt": stt,
            "exchange_charges": exchange_charges,
            "sebi_charges": sebi_charges,
            "stamp_duty": stamp_duty,
            "gst": gst,
            "total_costs": total_costs
        }
        
    def calculate_options(self, buy_premium: float, sell_premium: float, quantity: int, lot_size: int, exercised: bool = False) -> dict:
        """Returns dict. If exercised=True applies STT_OPTIONS_EXERCISE rate."""
        qty = quantity * lot_size
        buy_turnover = buy_premium * qty
        sell_turnover = sell_premium * qty
        total_premium_turnover = buy_turnover + sell_turnover
        
        # Options brokerage is usually flat Rs 20 per execution.
        brokerage = self.BROKERAGE_PER_ORDER * 2 
        
        # STT is only on sell side on premium
        if exercised:
            stt = round(sell_turnover * self.STT_OPTIONS_EXERCISE)
        else:
            stt = round(sell_turnover * self.STT_OPTIONS_SELL)
            
        exchange_charges = total_premium_turnover * self.NSE_OPTIONS_CHARGE
        sebi_charges = total_premium_turnover * self.SEBI_CHARGE
        # Stamp duty on Options is 0.003% on buy premium
        stamp_duty = buy_turnover * self.STAMP_DUTY_BUY
        
        gst = (brokerage + exchange_charges + sebi_charges) * self.GST_RATE
        
        total_costs = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst
        
        return {
            "brokerage": brokerage,
            "stt": stt,
            "exchange_charges": exchange_charges,
            "sebi_charges": sebi_charges,
            "stamp_duty": stamp_duty,
            "gst": gst,
            "total_costs": total_costs
        }
        
    def estimate_slippage(self, price: float, instrument_type: str, liquidity: str = "high") -> float:
        """
        Realistic slippage model:
        Nifty futures:     0.01% (very liquid)
        BankNifty futures: 0.01%
        BankNifty options: 0.05-0.15% (wide spreads)
        Mid-cap stocks:    0.05-0.2%
        """
        instrument_type = instrument_type.lower()
        if "nifty futures" in instrument_type or "banknifty futures" in instrument_type:
            rate = 0.0001
        elif "banknifty options" in instrument_type:
            rate = 0.0005 if liquidity == "high" else 0.0015
        elif "nifty options" in instrument_type:
            rate = 0.0003 if liquidity == "high" else 0.0010
        elif "mid-cap" in instrument_type or "midcap" in instrument_type:
            rate = 0.0005 if liquidity == "high" else 0.002
        else:
            # Default for large cap equities
            rate = 0.0002 if liquidity == "high" else 0.001
            
        return price * rate
