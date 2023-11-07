#import modules
import json
import asyncio
import logging
import time
import threading
import concurrent.futures
from Ideas.DataBaseConfig import BBDDManager
from Ideas.DataDownload import Connector


config_file_path = 'Ideas/config.json'
try:
    with open(config_file_path, 'r') as config_file:
        config_data = json.load(config_file)
except FileNotFoundError:
    print(f"The config file '{config_file_path}' does not exist.")
    config_data = {}







if __name__ == "__main__":



    DataDownloader = Connector(
        host = config_data["APIDataConnection"]["host"],
        port = config_data["APIDataConnection"]["port"],
        client_TWS = config_data["APIDataConnection"]["client_TWS"],
        timeout = config_data["APIDataConnection"]["timeout"]
    )

    """
    PATH EXCEL

    """
    path_to_excel = "Data\\5000_stocks.xlsx"
    tickers = DataDownloader.read_input_excel(path_to_excel)

    for ticker in tickers:
        
        bars_for_ticker = DataDownloader.query_data(ticker)
        for data in bars_for_ticker:
            DDBB_Manager = BBDDManager(
                host= config_data["Database"]["host"],
                username = config_data["Database"]["username"],
                db_name = config_data["Database"]["db_name"]
                )
            DDBB_Manager.insert_ohlc_data_v2(
                                table_name=config_data["Database"]["table_name"],
                                symbol=data["TICKER"],
                                datetime=data["DATE"],
                                open_price=data["OPEN"],
                                high_price=data["HIGH"],
                                low_price=data["LOW"],
                                close_price=data["CLOSE"],
                                currency=data["CURRENCY"]
                                )
