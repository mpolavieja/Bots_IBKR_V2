import os
from datetime import datetime
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow,Flow
from google.auth.transport.requests import Request
import ib_insync
from real_time_utils import request_real_time
import order_id_manager
import logging


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class Dashboard():
    
    def __init__(self, configuration):
        '''
        Crea un objeto Dashboard que representa el cuadro de mandos de Google Sheets. 
        '''
        self.configuration = configuration
        self.spreadSheetId = configuration['dashboard_document_id']
        self.realTimeLevel = configuration['dashboard_realtime_level']
        self.pendingFills = []
        self.liveOrders = []
        self.portfolio = []
        
        self.ordersChange = 0
        self.updateOrders = False    
        self.log = logging.getLogger('grid')
    
    
    def load_active_orders(self, ib):
        '''
            Extract relevant information from each trade and create rows for the orders.  
        '''
        try:
            all_orders = ib.reqAllOpenOrders()
            live_orders = []                 
            order_id = order_id_manager.OrderIdManager(7)
            order_change_control = 0 
            for trade in all_orders:                    
                # Continue loop if order is not alive
                if trade.remaining == 0 or trade.orderStatus == "Inactive":
                    continue
                # Process alive orders and get submit time from orderRef
                order_ref = trade.order.orderRef
                if order_ref != "" and order_ref != "ActivityMonitor":                    
                    order_submit_time = datetime.fromtimestamp(order_id.unpack(order_ref)["number"]/1000).strftime("%Y-%m-%d %H:%M:%S")                                                   
                else:
                    order_submit_time = " - No disponible - "
                    if order_ref == "": order_ref = "ORDEN MANUAL" 
                symbol = trade.contract.localSymbol 
                if symbol == "": symbol = trade.contract.symbol
                row = [symbol, trade.order.action, trade.order.lmtPrice, trade.order.totalQuantity, trade.remaining(), order_ref, order_submit_time]
                order_change_control += trade.order.lmtPrice 
                live_orders.append(row)        
            # Update change flags to later update Dashboard only if orders have changed
            self.updateOrders = order_change_control != self.ordersChange
            self.ordersChange = order_change_control   
            # Sort the list of live orders based on specified criteria, and then insert headers.
            live_orders = sorted(live_orders, key=lambda item: (item[0], -ord(item[1][0]), -item[2]))
            # Insert headers
            live_orders.insert(0, ["Symbol", "Direction", "Price", "Total Qty", "Remaining Qty","Estrategia", "Hora UTC", "Ultimo refresh: " + datetime.now().strftime('%H:%M:%S  --  %Y-%m-%d')])
            self.liveOrders = live_orders
            return live_orders
        except Exception as e:
            self.log.error(f"Dashboard Error: {e}")
            return None

    def load_fill(self, fill):
        """
            Inserts one execution into the 'pendingFills' list.

            Args:
                trade (object): The trade object.
                fill (object): The fill object.

            Returns: None
        """
        try:
            symbol = fill.contract.localSymbol
            if symbol == "": symbol = fill.contract.symbol
            side = "BUY" if fill.execution.side == "BOT" else "SELL" 
            row = [symbol, side, fill.execution.shares, fill.execution.avgPrice, fill.execution.time.strftime('%Y-%m-%d %H:%M:%S'), fill.execution.price, fill.execution.orderRef, fill.execution.orderId, fill.execution.execId]
            self.pendingFills.append(row)
        except Exception as e:
            self.log.exception(f"Dashboard Error: {e}")
    
    
    def load_portfolio(self, ib):
        """
        Writes all open positions associated with the account for which the API session is opened
        in the 'Cartera' tab of our Google Sheets dashboard.

        Args:
            ib (object): The IB API session object.

        Returns: None
        """
        try:
            # Retrieve the list of open positions. 
            all_positions = ib.portfolio()        
            open_positions = []

            # Extract relevant information from each position and append to portolio (Cartera)
            for position in all_positions:        
                symbol = position.contract.localSymbol
                if symbol == "": symbol = position.contract.symbol
                average_cost = position.averageCost
                if position.contract.multiplier:
                    average_cost = int(position.marketValue) / int(position.contract.multiplier) / int(position.position)
                row = [symbol, position.position, position.marketValue, average_cost, position.unrealizedPNL, position.realizedPNL]
                open_positions.append(row)
            # Insert headers
            open_positions.insert(0, ["Symbol", "Position", "Value", "Avg Cost", "Unrealized PNL","Realized PNL"])
            self.portfolio = open_positions
        except Exception as e:
            self.log.exception(f"Dashboard Error: {e}")

    def update_QGX3_data(self, ib, contract = None):
        '''
          !!!!!!!!!!!!!!! Esta es una función provisional que solo devuelve datos del futuro del Gas Natural para Control
          !!!!!!!!!!!!!!! No pide portfolio a IB, necesita que self.portfolio esté actualizado
        '''
        try:
            if contract == None:
                contract= ib_insync.Future(symbol='QG', lastTradeDateOrContractMonth='20231127', exchange='NYMEX', localSymbol='QGZ3', multiplier='2500',currency='USD')
                        
            symbol = contract.localSymbol
            price = request_real_time(ib, contract)
            pf = self.portfolio
            for stock in pf:
                if stock[0] == symbol:
                    posicion = stock[1]
            range=[[price[0]], [price[1]], [posicion]] 
            return range
        except Exception as e:
            return False 

    def update_dashboard(self, ib):
        try:
            
            # Update orders in GSheets Dashboard
            self.load_active_orders(ib)
            empty_rows = [[""] * len(self.liveOrders[0])] * 50
            self.liveOrders.extend(empty_rows)
            #Temporalmente ponemos a True para probar (esto luego funcionará solo cuanda haya cambios en órdenes)
            self.updateOrders = True #!!!!! OJOOOOOOOO!!!!!
            if self.updateOrders:
                service = self.get_google_service()
                self.write_data_to_sheet("Ordenes", self.liveOrders, service)
            
            # Update Control sheet in Dashboard. This must be always executed in this function
            self.load_portfolio(ib)
            if self.realTimeLevel > 0:
                QGX3data = self.update_QGX3_data(ib)
                if QGX3data:
                    self.write_data_to_sheet("Control", QGX3data, service, "B", 8)
            
            # Update Fills and portfolio (Cartera) in Dashboard
            if self.pendingFills:
                # Update Fills
                service = self.get_google_service()
                for row in self.pendingFills:
                    self.insert_data("Fills", row, service)
                self.pendingFills = []                
                # Update Cartera
                empty_rows = [[""] * len(self.portfolio[0])] * 10
                self.portfolio.extend(empty_rows)
                self.write_data_to_sheet("Cartera", self.portfolio, service)
        
        except Exception as e:
            # !!!!PENDIENTE DE PASAR A LOGGING
            self.log.exception(f"Dashboard. Error actualizando Google Sheets: {e}")



    # # # # # # # # # # # # # ## # # # # # # # # # # # # ## # # # # # # # # # # # # #
    # Las siguientes funciones tendrían que ir a google_sheets_interface
    # # # # # # ## # # # # # # # # # # # # ## # # # # # # # # # # # # ## # # # # # #

    # Request a service handler for google sheets using credentials or pickle token
    def get_google_service(self):
        """
        Authenticates and obtains a Google Sheets service instance for interaction.

        Returns:
            object or None: A Google Sheets service instance or None if there's an error.
        """
        token = None
        try:
            creds = None
            tokenFile = './token.pickle' if token is None else token
            if os.path.exists(tokenFile):
                with open(tokenFile, 'rb') as token:
                    creds = pickle.load(token)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(self.configuration['dashboard_credentials'], SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(tokenFile, 'wb') as token:
                    pickle.dump(creds, token)
            service = build('sheets', 'v4', credentials=creds)
            return service 
        except Exception as e:
            # Capture and display any exceptions that occur
            self.log.exception(f'Error authenticating with Google Sheets: {str(e)}')
            return None


    def write_data_to_sheet(self, sheet_name, data, service = None, start_column = "A", start_row = 1):
        """
        Writes data to a specified sheet in Google Sheets begining in column A row 1 (default).

        Args:
            table (str): The range in R1C1 notation where the data should be written.
            data (list): The data to be written.
            service (object): The Google Sheets service object.
            start_column (str): The initial column (e.g., 'A', 'B', 'C').
            start_row (int): The initial row (e.g., 1, 2, 3).        

        Returns:
            dict or None: The response from the Google Sheets API or None if there's an error.
        """
        table = self.get_R1C1_Notation (sheet_name, start_column, start_row, data)
        
        try:
            response = service.spreadsheets().values().update(
                spreadsheetId= self.spreadSheetId,
                range=table,
                body={'values': data},
                valueInputOption='RAW'
            ).execute()
            return response

        except Exception as e:
            # Capture and display any exceptions that occur
            self.log.exception(f'Dashboard Error: {str(e)}')
            return None


    def insert_data(self, sheet_name, data, service = None, begin_row = 1):
        """
        Inserts rows with data into the given sheet of a Google Sheets document,
        starting on begin_row.
        Args:
            sheet_name (str): The name of the target sheet.
            begin_row: row in which data is inserted (default is 1 to leave headers at the top)
            data (list): The data to be inserted as a list of lists.
            service (object): The Google Sheets service object.
        Returns:
            dict or None: The response from the Google Sheets API or None if there's an error.
        """
        
        try:
            # core.dashBoard.isUpdating = True
            # Get the sheet ID based on the sheet name
            data = [data]
            if not service: service = self.get_google_service()
            spreadsheet = service.spreadsheets().get(spreadsheetId=self.spreadSheetId).execute()
            sheet_id = None
            for sheet in spreadsheet['sheets']:
                if sheet['properties']['title'] == sheet_name:
                    sheet_id = sheet['properties']['sheetId']
                    break
            if sheet_id is None:
                self.log.error(f'Sheet "{sheet_name}" not found in the spreadsheet.')
                return
            # Insert rows with data into the sheet
            start_index = begin_row + 1  # Start inserting rows below header row
            end_index = start_index + len(data) - 1
            request_body = {
                "requests": [
                    {
                        "insertDimension": {
                            "range": {
                                "sheetId": sheet_id,
                                "dimension": "ROWS",
                                "startIndex": start_index - 1,  # Adjust for 0-indexed sheet
                                "endIndex": end_index
                            },
                            "inheritFromBefore": False
                        }
                    },
                    {
                        "pasteData": {
                            "coordinate": {
                                "sheetId": sheet_id,
                                "rowIndex": start_index - 1,  # Adjust for 0-indexed sheet
                                "columnIndex": 0
                            },
                            "data": "\n".join(["\t".join(map(str, fila)) for fila in data]),        
                            "type": "PASTE_NORMAL",
                            "delimiter": "\t"
                        }
                    }
                ]
            }
            response = service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadSheetId,
                body=request_body
            ).execute()
            return response
        except Exception as e:
            # Capture and display any exceptions that occur
            self.log.exception(f'Dashboard Error: {str(e)}')
            return None


    # Translates a column number into shett letters like  AZ or CB
    def _column_number_to_excel_letters(self, column_number):
        letters = ""
        while column_number > 0:
            remainder = (column_number - 1) % 26
            letters = chr(ord("A") + remainder) + letters
            column_number = (column_number - 1) // 26
        return letters


    # Returns range in excel notation
    def get_R1C1_Notation(self, sheet_name, start_column, start_row, data):
        """
        Returns a range in the format "Sheet!A1:B2" based on the sheet name, starting
        column, starting row, and a two-dimensional table.

        Args:
            sheet_name (str): The name of the sheet.
            start_column (str): The initial column (e.g., 'A', 'B', 'C').
            start_row (int): The initial row (e.g., 1, 2, 3).
            data (list of lists): A two-dimensional table.

        Returns:
            str: The range in R1C1 notation.
        """
        
        try:
            # Calculate the ending row and column based on the data dimensions
            end_row = start_row + len(data) - 1
            end_column = self._column_number_to_excel_letters(ord(start_column) - 65 + len(data[0]))
            
            # Construct the R1C1 notation
            range_notation = f"{sheet_name}!{start_column}{start_row}:{end_column}{end_row}"

            return range_notation
        except Exception as e:
            self.log.exception(f"get_R1C1_Notation Error: {e}")


