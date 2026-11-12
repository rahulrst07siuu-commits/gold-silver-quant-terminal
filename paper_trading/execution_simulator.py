import numpy as np

# Standard MCX Contract Sizing Specifications
CONTRACT_SPECS = {
    "GOLD": {
        "commodity": "GOLD",
        "lot_multiplier": 100,  # 1 kg = 100 units of 10g
        "tick_size": 1.0,
        "spread_ticks": 1.0,
        "margin_rate": 0.12     # 12% initial margin
    },
    "GOLDM": {
        "commodity": "GOLD",
        "lot_multiplier": 10,   # 100g = 10 units of 10g
        "tick_size": 1.0,
        "spread_ticks": 1.0,
        "margin_rate": 0.12
    },
    "SILVER": {
        "commodity": "SILVER",
        "lot_multiplier": 30,   # 30 kg = 30 units of 1kg
        "tick_size": 1.0,
        "spread_ticks": 2.0,
        "margin_rate": 0.15     # 15% initial margin
    },
    "SILVERM": {
        "commodity": "SILVER",
        "lot_multiplier": 5,    # 5 kg = 5 units of 1kg
        "tick_size": 1.0,
        "spread_ticks": 2.0,
        "margin_rate": 0.15
    },
    "SILVERMIC": {
        "commodity": "SILVER",
        "lot_multiplier": 1,    # 1 kg = 1 unit of 1kg
        "tick_size": 1.0,
        "spread_ticks": 2.0,
        "margin_rate": 0.15
    }
}

class ExecutionSimulator:
    """
    Simulates realistic market order execution with bid-ask spread,
    volatility-dependent slippage, and statutory Indian MCX regulatory & broker costs.
    """
    
    def __init__(self, flat_brokerage=20.0, apply_slippage=True):
        self.flat_brokerage = flat_brokerage
        self.apply_slippage = apply_slippage
        
    @staticmethod
    def get_contract_spec(symbol):
        sym_clean = symbol.upper().split("-")[0].strip()
        if sym_clean in CONTRACT_SPECS:
            return CONTRACT_SPECS[sym_clean]
        if "GOLD" in sym_clean:
            return CONTRACT_SPECS["GOLDM"]  # Safe default for retail/paper
        return CONTRACT_SPECS["SILVERMIC"]
        
    def calculate_costs(self, symbol, side, fill_price, quantity):
        """
        Calculates all Indian commodity regulatory costs and brokerage:
        - Brokerage: flat ₹20 or 0.03% (discount broker model)
        - Exchange transaction charge: 0.0026% of turnover (MCX)
        - GST: 18% on (Brokerage + Exchange txn charges)
        - SEBI turnover fee: ₹10 per crore (0.0001% of turnover)
        - Stamp duty: 0.002% on BUY side turnover
        - CTT: 0.01% on SELL side turnover
        """
        spec = self.get_contract_spec(symbol)
        lot_multiplier = spec["lot_multiplier"]
        turnover = float(fill_price * quantity * lot_multiplier)
        
        # 1. Brokerage: flat ₹20 or 0.03% max
        brokerage = min(self.flat_brokerage, turnover * 0.0003)
        
        # 2. Exchange Transaction Charges: 0.0026%
        exchange_charges = turnover * 0.000026
        
        # 3. GST: 18% on (Brokerage + Exchange charges)
        gst = (brokerage + exchange_charges) * 0.18
        
        # 4. SEBI Charges: ₹10 per crore
        sebi_charges = turnover * 0.000001
        
        # 5. Stamp Duty: 0.002% on BUY only
        stamp_duty = (turnover * 0.00002) if side.upper() == "BUY" else 0.0
        
        # 6. Commodity Transaction Tax (CTT): 0.01% on SELL only
        ctt = (turnover * 0.0001) if side.upper() == "SELL" else 0.0
        
        total_charges = brokerage + exchange_charges + gst + sebi_charges + stamp_duty + ctt
        
        return {
            "turnover": round(turnover, 2),
            "lot_multiplier": lot_multiplier,
            "brokerage": round(brokerage, 2),
            "exchange_charges": round(exchange_charges, 2),
            "gst": round(gst, 2),
            "sebi_charges": round(sebi_charges, 2),
            "stamp_duty": round(stamp_duty, 2),
            "ctt": round(ctt, 2),
            "total_charges": round(total_charges, 2)
        }
        
    def simulate_fill(self, symbol, side, quoted_price, quantity, regime="Normal", volatility_ann=0.18):
        """
        Calculates execution price including half-spread and volatility-dependent slippage.
        """
        spec = self.get_contract_spec(symbol)
        tick_size = spec["tick_size"]
        spread_ticks = spec["spread_ticks"]
        half_spread = (spread_ticks * tick_size) * 0.5
        
        if not self.apply_slippage:
            slippage_ticks = 0.0
        else:
            # Dynamic slippage based on volatility regime
            regime_lower = str(regime).lower()
            if "crisis" in regime_lower or "extreme" in regime_lower or volatility_ann > 0.35:
                slippage_ticks = 4.0
            elif "high" in regime_lower or volatility_ann > 0.25:
                slippage_ticks = 2.0
            elif "low" in regime_lower or volatility_ann < 0.12:
                slippage_ticks = 0.5
            else:
                slippage_ticks = 1.0
                
        slippage_amount = slippage_ticks * tick_size
        
        side_upper = side.upper()
        if side_upper == "BUY":
            fill_price = quoted_price + half_spread + slippage_amount
        else:
            fill_price = quoted_price - half_spread - slippage_amount
            
        fill_price = round(fill_price, 2)
        total_slippage_cost = round((half_spread + slippage_amount) * quantity * spec["lot_multiplier"], 2)
        
        cost_breakdown = self.calculate_costs(symbol, side_upper, fill_price, quantity)
        cost_breakdown["slippage_amount"] = round(half_spread + slippage_amount, 2)
        cost_breakdown["slippage_cost"] = total_slippage_cost
        cost_breakdown["execution_price"] = fill_price
        cost_breakdown["quoted_price"] = quoted_price
        cost_breakdown["total_friction"] = round(cost_breakdown["total_charges"] + total_slippage_cost, 2)
        cost_breakdown["is_simulation"] = True
        
        return cost_breakdown
        
    def simulate_execution(self, order, quote=None):
        """
        Executes order simulation and flags result strictly as simulation.
        """
        symbol = order.get("symbol", "GOLD-DEC2026")
        side = order.get("side", "BUY")
        quantity = order.get("quantity", 1)
        quoted_price = order.get("price")
        if quoted_price is None and quote:
            quoted_price = quote.get("ltp") or quote.get("close")
        if quoted_price is None:
            quoted_price = 128500.0
            
        res = self.simulate_fill(symbol, side, float(quoted_price), quantity)
        res["status"] = "FILLED"
        res["is_simulation"] = True
        res["order_id"] = order.get("order_id", "SIM_ORD")
        return res
