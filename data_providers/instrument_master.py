from datetime import datetime, date
import pandas as pd

MCX_COMMODITY_SPECS = {
    "GOLD": {
        "name": "Gold Standard",
        "exchange": "MCX",
        "segment": "MCX_COMM",
        "base_symbol": "GOLD",
        "quotation_unit": "INR / 10g",
        "trading_lot": "1 kg (100 units of 10g)",
        "tick_size": 1.0,
        "max_order_qty": 100,
        "tender_days": 5
    },
    "GOLDM": {
        "name": "Gold Mini",
        "exchange": "MCX",
        "segment": "MCX_COMM",
        "base_symbol": "GOLDM",
        "quotation_unit": "INR / 10g",
        "trading_lot": "100g (10 units of 10g)",
        "tick_size": 1.0,
        "max_order_qty": 500,
        "tender_days": 5
    },
    "SILVER": {
        "name": "Silver Standard",
        "exchange": "MCX",
        "segment": "MCX_COMM",
        "base_symbol": "SILVER",
        "quotation_unit": "INR / kg",
        "trading_lot": "30 kg",
        "tick_size": 1.0,
        "max_order_qty": 600,
        "tender_days": 5
    },
    "SILVERM": {
        "name": "Silver Mini",
        "exchange": "MCX",
        "segment": "MCX_COMM",
        "base_symbol": "SILVERM",
        "quotation_unit": "INR / kg",
        "trading_lot": "5 kg",
        "tick_size": 1.0,
        "max_order_qty": 1200,
        "tender_days": 5
    }
}

class InstrumentMaster:
    """
    Manages active MCX Gold and Silver futures contracts, specifications,
    expiry calendars, and continuous-contract rollover rules.
    """
    def __init__(self):
        # Default mock / active contracts schedule for 2026/2027
        self.contracts = {
            "GOLD": [
                {"symbol": "GOLD-DEC2026", "token": "MCX_43501", "expiry": "2026-12-05", "is_active": True},
                {"symbol": "GOLD-FEB2027", "token": "MCX_43502", "expiry": "2027-02-05", "is_active": False},
                {"symbol": "GOLD-APR2027", "token": "MCX_43503", "expiry": "2027-04-05", "is_active": False}
            ],
            "SILVER": [
                {"symbol": "SILVER-DEC2026", "token": "MCX_54801", "expiry": "2026-12-05", "is_active": True},
                {"symbol": "SILVER-MAR2027", "token": "MCX_54802", "expiry": "2027-03-05", "is_active": False},
                {"symbol": "SILVER-MAY2027", "token": "MCX_54803", "expiry": "2027-05-05", "is_active": False}
            ]
        }
        
    def get_spec(self, base_symbol="GOLD"):
        return MCX_COMMODITY_SPECS.get(base_symbol.upper(), {})

    def get_active_contract(self, commodity="GOLD", current_date=None):
        """
        Returns the active front-month contract, days to expiry, and next rollover target.
        """
        if current_date is None:
            current_date = date.today()
        elif isinstance(current_date, str):
            current_date = datetime.strptime(current_date, "%Y-%m-%d").date()
            
        contracts = self.contracts.get(commodity.upper(), [])
        if not contracts:
            return None
            
        for idx, c in enumerate(contracts):
            exp_date = datetime.strptime(c["expiry"], "%Y-%m-%d").date()
            dte = (exp_date - current_date).days
            if dte >= 0:
                spec = self.get_spec(commodity)
                next_c = contracts[idx + 1] if idx + 1 < len(contracts) else None
                
                rollover_warning = dte <= spec.get("tender_days", 5)
                
                return {
                    "commodity": commodity.upper(),
                    "symbol": c["symbol"],
                    "token": c["token"],
                    "expiry_date": c["expiry"],
                    "days_to_expiry": dte,
                    "quotation_unit": spec.get("quotation_unit", ""),
                    "lot_size": spec.get("trading_lot", ""),
                    "tick_size": spec.get("tick_size", 1.0),
                    "rollover_warning": rollover_warning,
                    "status": "EXPIRY_WARNING: ROLLOVER_REQUIRED" if rollover_warning else "ACTIVE",
                    "next_contract": next_c["symbol"] if next_c else "N/A",
                    "next_expiry": next_c["expiry"] if next_c else "N/A"
                }
        return contracts[0]

    def continuous_contract_rules(self):
        """
        Documents rules for generating continuous futures series.
        """
        return {
            "rollover_trigger": "Volume / Open Interest Cross",
            "condition": "Roll when Next-Month Volume > Front-Month Volume OR 5 trading days prior to expiry.",
            "price_adjustment": "Panama Canal (Back-adjusted by cumulative price difference at roll timestamp).",
            "volume_handling": "Summed or front-month volume retained."
        }
