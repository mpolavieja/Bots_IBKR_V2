from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow,Flow
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
import os
import pickle
import ib_insync
from real_time_utils import request_real_time

CREDENTIALS = 'C:/NF_IBKR_Paper/credentials.json'

# Identificador del google sheet Desarrollo (BotsIBKR): '1JOe2rzWEkciQasrhjsVFVesUCMIe5BuQXaeRWD-0QV4'
# DOCUMENT_ID = '1JOe2rzWEkciQasrhjsVFVesUCMIe5BuQXaeRWD-0QV4'
# Identificador del google sheet Paper (BotsIBKR_Paper): '14PfzhKAYBoM9wPeHl6CYPI7G7hmNU47PLADXH6Bh_-g'
DOCUMENT_ID = '14PfzhKAYBoM9wPeHl6CYPI7G7hmNU47PLADXH6Bh_-g'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class DashboardSheets:
    #Class constructor
    def __init__(self):
        self.isUpdating = False    


def get_google_service():
    """
    Authenticates and obtains a Google Sheets service instance for interaction.

    Returns:
        object or None: A Google Sheets service instance or None if there's an error.
    """
    token = None
    try:
        creds = None
        tokenFile = './token_paper.pickle' if token is None else token
        if os.path.exists(tokenFile):
            with open(tokenFile, 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(tokenFile, 'wb') as token:
                pickle.dump(creds, token)
        service = build('sheets', 'v4', credentials=creds)
        return service 
    except Exception as e:
        # Capture and display any exceptions that occur
        print(f'Error authenticating with Google Sheets: {str(e)}')
        return None



def _insert_blank_rows_to_sheet(sheet_name, num_rows_to_insert, service):
    """
    Inserts a specified number of blank rows into the given sheet of a Google Sheets document,
    starting on the second row (to leave headers untouched).

    Args:
        sheet_name (str): The name of the target sheet.
        num_rows_to_insert (int): The number of blank rows to insert.
        service (object): The Google Sheets service object.
        document_id (str): The ID of the Google Sheets document.

    Returns:
        dict or None: The response from the Google Sheets API or None if there's an error.
    """
    HEADER_ROW = 1
    
    try:
        # Get the sheet ID based on the sheet name
        spreadsheet = service.spreadsheets().get(spreadsheetId=DOCUMENT_ID).execute()
        sheet_id = None
        for sheet in spreadsheet['sheets']:
            if sheet['properties']['title'] == sheet_name:
                sheet_id = sheet['properties']['sheetId']
                break

        if sheet_id is None:
            print(f'Sheet "{sheet_name}" not found in the spreadsheet.')
            return

        # Insert blank rows into the sheet
        start_index = HEADER_ROW + 1  # Start inserting rows below header row
        end_index = start_index + num_rows_to_insert - 1
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
                }
            ]
        }
        response = service.spreadsheets().batchUpdate(
            spreadsheetId= DOCUMENT_ID,
            body=request_body
        ).execute()

        return response

    except Exception as e:
        # Capture and display any exceptions that occur
        print(f'Error inserting blank rows: {str(e)}')
        return None


def delete_sheet_contents_google_sheets(service, sheet_name):
    """
    Deletes all content within a specified sheet in Google Sheets.

    Args:
        service (object): The Google Sheets service object.
        sheet_name (str): The name of the sheet to clear.
        document_id (str): The ID of the Google Sheets document.

    Returns:
        dict or None: The response from the Google Sheets API or None if there's an error.
    """
    try:
        # Prepare data to clear the sheet
        clear_values = [['' for _ in range(26)]] * 1000
        body = {'values': clear_values}
        clear_range = f"{sheet_name}!A1:Z1000"

        response = service.spreadsheets().values().update(
            spreadsheetId= DOCUMENT_ID,
            range= clear_range,
            valueInputOption= 'RAW',
            body= body
        ).execute()
        return response

    except Exception as e:
        # Capture and display any exceptions that occur
        print(f'Error clearing the sheet contents: {str(e)}')
        return None


def write_range_to_google_sheets(table, data, service):
    """
    Writes data to a specified range in Google Sheets.

    Args:
        table (str): The range in R1C1 notation where the data should be written.
        data (list): The data to be written.
        service (object): The Google Sheets service object.        

    Returns:
        dict or None: The response from the Google Sheets API or None if there's an error.
    """
    try:
        response = service.spreadsheets().values().update(
            spreadsheetId= DOCUMENT_ID,
            range=table,
            body={'values': data},
            valueInputOption='RAW'
        ).execute()
        return response

    except Exception as e:
        # Capture and display any exceptions that occur
        print(f'Error updating the spreadsheet: {str(e)}')
        return None


# Returns range in excel notation
def get_R1C1_Notation(sheet_name, start_column, start_row, data):
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
    def column_number_to_excel_letters(column_number):
      letters = ""
      while column_number > 0:
        remainder = (column_number - 1) % 26
        letters = chr(ord("A") + remainder) + letters
        column_number = (column_number - 1) // 26
      return letters

    # Calculate the ending row and column based on the data dimensions
    end_row = start_row + len(data) - 1
    end_column = column_number_to_excel_letters(ord(start_column) - 65 + len(data[0]))
    
    # Construct the R1C1 notation
    range_notation = f"{sheet_name}!{start_column}{start_row}:{end_column}{end_row}"

    return range_notation


# Inserts a single row in a sheet
def insert_single_row_google_sheets(sheet_name, row_data, position):
    """
    Inserts a single row represented by 'row' into the specified sheet at the given 'position'.

    Args:
        sheet_name (str): The name of the target sheet.
        row (list): The data to be inserted as a single row.
        position (int): The position (row number) where the row should be inserted.

    Returns:
        dict: The response from the Google Sheets API or None if there's an error.
    """
    service = get_google_service()
    range_notation = get_R1C1_Notation(sheet_name, "A", position, row_data)
        
    # Insert a blank row to make space
    _insert_blank_rows_to_sheet(sheet_name, 1, service) 
        
    # Write the row data to the specified position
    response = write_range_to_google_sheets(range_notation, row_data, service)
        
    return response
 

# Updates live orders into sheet
def write_orders_to_google_sheets(ib):
    """
    Writes all live orders associated with the account for which the API session is opened
    in the 'Orders' tab of our Google Sheets dashboard.

    Args:
        ib (object): The IB API session object.

    Returns:
        None
    """
    
    # Retrieve the list of open trades (live orders). 
    all_orders = ib.openTrades()
    live_orders = []

    # Extract relevant information from each trade and create rows for the orders.    
    for trade in all_orders:        
        symbol = trade.contract.localSymbol
        if symbol == "": symbol = trade.contract.symbol
        if trade.remaining != 0 and trade.orderStatus != "Inactive":                    
          row = [symbol, trade.order.action, trade.order.lmtPrice, trade.order.totalQuantity, trade.remaining(), trade.order.orderRef, trade.log[-1].time.strftime('%H:%M:%S %Y-%m-%d')]
        live_orders.append(row)
       

    # Sort the list of live orders based on specified criteria, and then insert headers.
    live_orders = sorted(live_orders, key=lambda item: (item[0], -ord(item[1][0]), -item[2]))
    live_orders.insert(0, ["Symbol", "Direction", "Price", "Total Qty", "Remaining Qty","Estrategia", "Hora UTC", "Ultimo refresh: " + datetime.now().strftime('%H:%M:%S  --  %Y-%m-%d')])

    # Build the range based on the size of the live orders list starting from cell A1.
    range_notation = get_R1C1_Notation("Ordenes", "A", 1, live_orders)

    # Obtain the Google Sheets service and delete the existing 'Ordenes' sheet.
    service = get_google_service()
    delete_sheet_contents_google_sheets(service, "Ordenes")

    # Write the live orders data to the specified range.
    write_range_to_google_sheets(range_notation, live_orders, service)
    
    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    #Provisionalmente, aprovechamos aqu� para actualizar portfolio y control
    write_portfolio_to_google_sheets(ib)
    update_QGX3_data(ib)
    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

# write portfolio to google sheets
def write_portfolio_to_google_sheets(ib):
    """
    Writes all open positions associated with the account for which the API session is opened
    in the 'Cartera' tab of our Google Sheets dashboard.

    Args:
        ib (object): The IB API session object.

    Returns:
        None
    """
    
    # Retrieve the list of open positions. 
    all_positions = ib.portfolio()
    
    open_positions = []

    # Extract relevant information from each trade and create rows for the orders.
    for position in all_positions:        
        symbol = position.contract.localSymbol
        if symbol == "": symbol = position.contract.symbol
        average_cost = position.averageCost
        if position.contract.multiplier:
            average_cost = int(position.marketValue) / int(position.contract.multiplier) / int(position.position)
        row = [symbol, position.position, position.marketValue, average_cost, position.unrealizedPNL, position.realizedPNL]
        open_positions.append(row)

    #print(all_positions)
    
    open_positions.insert(0, ["Symbol", "Position", "Value", "Avg Cost", "Unrealized PNL","Realized PNL"])

    # Build the range based on the size of the positions list starting from cell A1.
    range = get_R1C1_Notation("Cartera", "A", 1, open_positions)

    # Obtain the Google Sheets service and delete the existing 'Ordenes' sheet.
    service = get_google_service()
    delete_sheet_contents_google_sheets(service, "Cartera")

    # Write the live orders data to the specified range.
    write_range_to_google_sheets(range, open_positions, service)    


# Inserts executions into sheet
def write_fill_to_google_sheets(core, trade, fill, sheet="Fills"):
    """
    Inserts executions into the 'Fills' sheet.

    Args:
        trade (object): The trade object.
        fill (object): The fill object.

    Returns:
        None
    """
    core.dashBoard.isUpdating = True

    fills = []
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    symbol = fill.contract.localSymbol
    if symbol == "": symbol = fill.contract.symbol
    side = "BUY" if fill.execution.side == "BOT" else "SELL" 
    row = [symbol, side, fill.execution.shares, fill.execution.avgPrice, fill.execution.time.strftime('%Y-%m-%d %H:%M:%S'), fill.execution.price, fill.execution.orderRef, fill.execution.orderId, fill.execution.execId]
    fills.append(row)

    # Insert the single row into the 'Fills' sheet starting at position 2
    insert_single_row_google_sheets(sheet , fills, 2)
        

def overwrite_sheet(sheet, table):
    range = get_R1C1_Notation(sheet,"A",1,table)
    service = get_google_service()
    delete_sheet_contents_google_sheets(service, sheet)
    write_range_to_google_sheets(range, table, service)



def test_R1C1():
    tabla = [
      [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33],
      ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG'],
      ['Apple', 'Banana', 'Cherry', 'Date', 'Elderberry', 'Fig', 'Grape', 'Honeydew', 'Iguana', 'Jackfruit', 'Kiwi', 'Lemon', 'Mango', 'Nectarine', 'Orange', 'Papaya', 'Quince', 'Raspberry', 'Strawberry', 'Tangerine', 'Ugli fruit', 'Vineapple', 'Watermelon', 'Xigua', 'Yellow passion fruit', 'Zucchini', 'Almond', 'Blueberry', 'Cranberry', 'Dragon fruit', 'Eggplant', 'Figs'],
      [True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False]
    ]    
    rango = get_R1C1_Notation("Prueba", "C", 3, tabla)
    print (rango)


def update_QGX3_data(ib):
    
    contract= ib_insync.Future(symbol='QG', lastTradeDateOrContractMonth='20231026', exchange='NYMEX', localSymbol='QGX3', multiplier='2500',currency='USD')
    price = request_real_time(ib, contract)
    pf = ib.portfolio()
    for stock in pf:
        if stock.contract.localSymbol == "QGX3":
            posicion = stock.position
    range=[[price[0]], [price[1]], [posicion]]    
    service = get_google_service()
    write_range_to_google_sheets("Control!B8:B10", range, service)

def refresh_orders():
  ib = ib_insync.IB()
  ib.connect('127.0.0.1', 7497, clientId=888)    
  write_orders_to_google_sheets(ib)
  ib.disconnect()

def refresh_portfolio():
  ib = ib_insync.IB()
  ib.connect('127.0.0.1', 7497, clientId=888)    
  write_portfolio_to_google_sheets(ib)
  ib.disconnect()

def test_fills():
  ib = ib_insync.IB()
  ib.connect('127.0.0.1', 7497, clientId=888)    
  service = get_google_service()
  fills = ib.reqExecutions()
  print(fills[0])
  for fill in fills:       
      write_fill_to_google_sheets(None, fill, "Prueba")
  ib.disconnect()

def refresh_control():
  ib = ib_insync.IB()
  ib.connect('127.0.0.1', 7497, clientId=888)    
  update_QGX3_data(ib)
  ib.disconnect()

def test_name():
  import inspect
  print (f"Nombre de esta funci�n: {inspect.currentframe().f_code.co_name}" )
  print(f"Nombre de este m�dulo: {__name__}")

def test_exception()  :
  import logging  

  try:
    raise ValueError ('error fatal')
  except Exception as e:
    logging.log(30,"An exception was thrown!", exc_info=True)
    # print_exc()
    

if __name__ == "__main__":
  
  test_exception()
  #refresh_control()
