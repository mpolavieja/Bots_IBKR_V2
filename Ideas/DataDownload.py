import time
import logging
import pandas as pd
from ib_insync import *
from Ideas.DataBaseConfig import BBDDManager


#API Connector
class Connector():
    ib_client = ""
    def __init__(self, host, port, client_TWS, timeout) -> None:
        print("Connecting to API ...")
        while True:
            try:
                self.ib_client = IB()
                print("Conectando...")
                self.ib_client.connect(host, port=port, clientId=client_TWS, timeout=timeout)
                if self.ib_client.isConnected():
                    print("Bot esta conectado")
                    break
            except Exception as mistake:
                print(mistake)
    """
    Function: Query Data
    Queries Data via API given a stock, and returns data.

    Input: One stock
    Output: List of bars 
    """
    def query_data(self, stock):
        barsList = []
        dt = ""
        try:
            contract =  Stock(stock, 'SMART', 'USD')#cambiar
            self.ib_client.reqMarketDataType(4)
            bars_from_api = self.ib_client.reqHistoricalData(
                    contract,
                    endDateTime=dt,
                    durationStr='30 D',
                    barSizeSetting='1 hour',
                    whatToShow='MIDPOINT',
                    useRTH=False,
                    formatDate=1
            )
            if not bars_from_api:
                print(f"No data found with {str(contract.symbol)}") 
            else:
                print("Downloading data...")
                for data in range(len(bars_from_api)):
                    bars_data ={}
                    bars_data["TICKER"] = contract.symbol
                    bars_data["DATE"] = bars_from_api[data].date
                    bars_data["OPEN"] = bars_from_api[data].open
                    bars_data["HIGH"] = bars_from_api[data].high
                    bars_data["LOW"] = bars_from_api[data].low
                    bars_data["CLOSE"] = bars_from_api[data].close
                    bars_data["CURRENCY"] = contract.currency
                    barsList.append(bars_data)
        except Exception as e:
            print(e)
        
        return barsList

    """
    Function: Read Input Excel
    Given a excel path, will return a list of tickers.
    
    Input: Excel Path 
    Output: List of Tickers

    """
    def read_input_excel(self, route_excel):
        stocks_ticker = []
        try:
            df = pd.read_excel(route_excel)
            stocks_ticker = df["Ticker"]
            return stocks_ticker        
        except Exception as e:
            print("Error reading input data")
            print(e)
            return stocks_ticker






