import ib_insync
import math

def request_mkt_data(ib,stock):
  ib.reqMarketDataType(1)
  price = ib.reqMktData(stock, '', False, False)
  intentos = 0
  wait_seconds = 6
  while math.isnan(price.last) and intentos < 2:
    print(f"Esperando {wait_seconds} segundos para asegurar la recepcion de TR....")
    ib.sleep(wait_seconds)
    intentos += 1
    wait_seconds= 6 * intentos
  print(f"Precios TR para   {stock.symbol} ** Bid:{price.bid}  Ask:{price.ask}  Open:{price.open}  --Last:{price.last}--  PrevLast:{price.prevLast}  MktPrice (MidPrice): {price.marketPrice()} Close:{price.close} ")    
  ib.cancelMktData(stock)
  return price

def request_ticker(ib,stock):
  ib.reqMarketDataType(1)
  tickers = ib.reqTickers(stock)
  price = tickers[0]
  ib.sleep(1)
  if math.isnan(price.last):
    print("Esperando 6 segundos para asegurar la recepcion de Datos Ticker...")
    ib.sleep(6)
  print(f"Precios Tick para {stock.symbol} ** Bid:{price.bid}  Ask:{price.ask}  Open:{price.open}  --Last:{price.last}--  PrevLast:{price.prevLast}  Mark:{price.markPrice}  Close:{price.close} ")    
  
  return price

def request_historical (ib, contract, retry = False, verbose = False):
  '''
  Esta función recibe un objeto "ib" con la sesión de interactive brokers (para
  no tener que abrir otra nueva) y un contrato. Solicita las dos últimas barras
  diaras.  Al pedir "TRADES" en whatToShow pedimos que los datos de la barra sean 
  las ejecuciones. Y al poner useRTH a False, la ultima barra estará actualizada a 
  cualquier hora (pre, oficial, after.  En principio no registra prcios overnight?)

  Args:
      ib (object): The IBKR session object.
      stock (object): A contract object.

  Returns:
      None
  '''
  price = None
  ib.reqMarketDataType(1)
  bars = ib.reqHistoricalData(
        contract, 
        endDateTime='', 
        durationStr='2 D', 
        barSizeSetting='1 day',
        whatToShow='TRADES', 
        useRTH=False,
        formatDate=1,
        keepUpToDate=False,
        )  
  if len(bars) > 0: price = bars[len(bars)-1]
  symbol = contract.localSymbol if contract.localSymbol else contract.symbol
  if retry and math.isnan(price.close):
      print("Esperando 6 segundos para asegurar la recepcion Datos Bar....")
      ib.sleep(6)
  if price.close == None or math.isnan(price.close):
    print (f"Error al obtener el precio para {symbol}")
    verbose = True
  if verbose: 
     print(f"Precios Barra 1D  {symbol} ** High:{price.high} Low:{price.low}  Open:{price.open} --Close:{price.close}--")    
  
  return price
 

def request_real_time(ib, stock, verbose = False):
  price = request_historical(ib, stock)
  if math.isnan(price.close):
    return False
  
  if verbose: 
      print(f"Obtenido precio para {stock.symbol}. Close barra actual: {price.close}, con fecha {price.date.strftime('%d-%m-%Y')}")
      print("Datos de precio solicitando ticker (informativo)")
      request_ticker(ib, stock)
      print("Datos de precio solicitando mktData (informativo)")
      request_mkt_data(ib,stock)
  
  return [price.close, price.volume]
    
  
  
def test_request_real_time():
  print("comenzando")
  ib= ib_insync.IB()
  ib.connect("127.0.0.1", port=7497, clientId=888, timeout=5)
  print("solicitando TR")
  ib.reqMarketDataType(1)
  symbols = ["QG"]
  for symbol in symbols:
    contract= ib_insync.Future(symbol='QG', lastTradeDateOrContractMonth='20231026', exchange='NYMEX', localSymbol='QGX3', multiplier='2500',currency='USD')
    contract = ib_insync.Stock("FUBO", 'SMART', 'USD')
    print(f"{symbol} :")  
    request_real_time (ib, contract)
    # bars = request_historical(ib, contract)
    # print (bars)
  ib.disconnect()


def test_historical():
  print("comenzando")
  ib= ib_insync.IB()
  ib.connect("127.0.0.1", port=7497, clientId=888, timeout=5)
  print("solicitando TR")
  
  symbols = ["QG"]
  for symbol in symbols:
    contract= ib_insync.Future(symbol='QG', lastTradeDateOrContractMonth='20231026', exchange='NYMEX', localSymbol='QGX3', multiplier='2500',currency='USD')
    #contract = ib_insync.Stock("FUBO", 'SMART', 'USD')
    print(f"{symbol} :")  
    request_historical (ib, contract, True, True)
    # bars = request_historical(ib, contract)
    # print (bars)
  ib.disconnect()


if __name__ == "__main__":
  test_historical()