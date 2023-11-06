import json
import time
import telegram
import logging
from ib_insync import *
import write_google_sheets



#Global Vars
MAX_POSITION_GLOBAL = 600000 
MAX_POSITION_CONTRACT = 300000
MAX_POSITION_STRATEGY = 100000   # este numero me lo invente, debe ser cambiado OJO
MAX_POSITION_SYMBOL = 300000    # este numero me lo invente, debe ser cambiado OJO
MAX_ORDER = 10000
WARNING_PERCENTAGE = 90    # Establishes the percentage of the limit from which a warning is triggered


class RiskManager:
    def __init__(self, configuration):
        self.configuration = configuration
        self.warningPercentage = WARNING_PERCENTAGE
        self.warningRatio = self.warningPercentage / 100
        self.max = {
            "order": MAX_ORDER,
            "position":{
                "symbol": MAX_POSITION_SYMBOL,
                "strategy": MAX_POSITION_STRATEGY,
                "contract": MAX_POSITION_CONTRACT,
                "global": MAX_POSITION_GLOBAL
            }
        }
        self.dynamicPortfolio = {}
        self.orders = self._empty_orders_data()
        self.risk = self._empty_risk_data()
        self.log = logging.getLogger('grid')
        
        
    def add_executed_operation(self, trade, core):
        '''
        Maintains one account per position strategy
        Every time a buy or sell order is executed, it adds the quantity 
        and the nominal to the total position of the strategy.
        '''
        contractId, symbol, strategyId, side, quantity, multiplied, nominal = self._common_data_from_trade(trade, core)
        #if strategyId not in self.dynamicPortfolio:
        #    self.dynamicPortfolio[strategyId] = self._initialize_dynamic_position_item(contractId, symbol, strategyId)
        #self.dynamicPortfolio[strategyId]["value"] = nominal + self.dynamicPortfolio[strategyId].get("value")
        pass


    def can_operate(self, order, strategy, core):
        '''
        This function receives the data of an order and checks if it is close to or exceeds the Risk Limits.  
        side: Operation type ['BUY' or 'SELL']
        price: Price at which the order is intended to be executed.
        strategy: Object that contains strategy parameters.
        core: It is the Core type object that is started and correctly connected.
        return: True if the order does not exceed the limits. Otherwise it returns False.
        '''
        #print('dynamicPortfolio:', self.dynamicPortfolio)
        #print('orders:', self.orders)
        #print('risk:', self.risk)
        try:
            # Gets the incoming order data.
            contractId, symbol, strategyId, side, quantity, multiplied, nominal = self._common_data_from_order(order, strategy)
            
            # Calculates the current risk taking into account active orders.
            if not self._calculate_risks(order, strategy, core):
                return False
                                                
            quantityLong = self.risk['contract'][contractId]["virtual"]["long"]["quantity"] 
            quantityShort = self.risk['contract'][contractId]["virtual"]["short"]["quantity"] 
            if not self.order_increases_position(quantityLong, quantityShort, order.action):
                if self.configuration['debug_mode']:
                    self.log.critical(self._inform(f"   Order does not increase position."))
                return True
            
            potencialPositionGlobal = self.risk["total"]["max"]["nominal"]
            #potencialPositionContract = self.risk['contract'][contractId]["virtual"]["max"]["nominal"] 
            potencialPositionContract = abs(self.risk['contract'][contractId]["virtual"]['long']["nominal"] if order.action == "BUY" else self.risk['contract'][contractId]["virtual"]['short']["nominal"])
            potencialPositionStrategy = 0   #self.risk['strategy'][strategyId]["virtual"]["max"]["nominal"] 
            print('potencialPositionContract:', potencialPositionContract)
                                                           
            if self.configuration['debug_mode']:
                print('   _____________________________________')
                print('   Risk calculation:')
                report = {
                    "contract": self.risk['contract'][contractId]["virtual"],
                    "total": self.risk['total']
                }
                print(json.dumps(report, indent=3))
            
            strPrefix = f"Order to {order.action} {strategy['cantidad_orden']} {symbol} @ {order.lmtPrice} exceeds"
            strRejected = 'ORDER MUST BE REJECTED!!'                        
  
            # Checks maximun thresolds and returns False if any is exceeded.
            print('potencialPositionContract:', potencialPositionContract)
            if nominal > self.max['order']:
                self.log.critical(self._inform(f"{strPrefix} single order limit of {MAX_ORDER}. {strRejected}"))
                return False        
            elif potencialPositionGlobal > self.max['position']['global']:              
                self.log.critical(self._inform(f"{strPrefix} global position limit. {strRejected}"))
                return False
            elif potencialPositionContract > self.max['position']['contract']:
                self.log.critical(self._inform(f"{strPrefix} max position limit for the instrument. {strRejected}"))
                return False
            #elif potencialPositionStrategy > self.max['position']['strategy']:  
            #    self.log.critical(self._inform(f"{strPrefix} max position limit of {self.max['position']['strategy']} for the strategy. {strRejected}"))
            #    return False

            # Checks warnings thresolds and inform if any are exceeded.
            if potencialPositionGlobal > self.warningRatio * self.max['position']['global']:
                self.log.critical(self._inform(f"{strPrefix} {self.warningPercentage}% of global position limit"))
            if potencialPositionContract > self.warningRatio * self.max['position']['contract']:
                self.log.critical(self._inform(f"{strPrefix} {self.warningPercentage}% of max position limit for the instrument"))
            #if potencialPositionStrategy > self.warningRatio * self.max['position']['strategy']:
            #    self.log.critical(self._inform(f"{strPrefix} {self.warningPercentage}% of max position limit for the strategy"))
            return True    
        except Exception as e:
            self.log.exception(self._inform(f"   The order could not be validated. Exception: {str(e)}"))
            return False
    

    def order_increases_position(self, positionCountLong, positionCountShort, side):
        positionCountVirtual = positionCountLong if side == "BUY" else positionCountShort
        if positionCountVirtual == 0: return False
        sign = int(positionCountVirtual / abs(positionCountVirtual))
        return sign == int(self._side_as_sign(side)) 


    def get_risks(self):
        '''Method to get the complete estimated risk.'''
        return self.risk

    
    def _calculate_risks(self, order, strategy, core):
        '''
        This method calculates the global risk values, per contract and per strategy:
        You should always be called before consulting and using risk information.
        
        core: It is the Core type object that is started and correctly connected.
        return: True if I can correctly calculate the risk. Otherwise it returns False. 
                Risk data is stored in the self.risk data structure.
        '''
        try:
            # 1 - The structure is initialized before processing.
            self.risk = self._empty_risk_data()                     
            # 2 - For contracts and strategies: Places orders data in the self.risk structure.
            if not self._load_order_data(order, strategy, core, False):  
                return False
            # 3 - For contracts: Places portfolio data in the 
            # self.risk structure and calculate virtual values.
            for position in core.portfolio():
                print('contractID:', position.contract.conId, position.contract.symbol, '  position.marketValue:', position.marketValue)
                self._set_risk_data_item("contract", str(position.contract.conId), 
                    position.contract.localSymbol if position.contract.localSymbol else position.contract.symbol, 
                    None, position.position, position.marketValue)
            # 4 - For strategies: Places dynamic portfolio data in the 
            # self.risk structure and calculate virtual values.
            for key in self.dynamicPortfolio.keys():
                position = self.dynamicPortfolio[key]
                self._set_risk_data_item("strategy", position["contractId"], position["symbol"], 
                    position["strategyId"], 0, position["value"])
            # 5 - For contracts: Establishes the calculated totals values.
            for key in self.risk['contract'].keys():
                contract = self.risk['contract'][key]
                print('INCREMENTO', contract["virtual"]["max"]["nominal"] )
                self.risk["total"]['long']["quantity"] += contract["virtual"]["long"]["quantity"] 
                self.risk["total"]['long']["multiplied"] += contract["virtual"]["long"]["multiplied"] 
                self.risk["total"]['long']["nominal"] += contract["virtual"]["long"]["nominal"] 
                self.risk["total"]['short']["quantity"] += contract["virtual"]["short"]["quantity"] 
                self.risk["total"]['short']["multiplied"] += contract["virtual"]["short"]["multiplied"] 
                self.risk["total"]['short']["nominal"] += contract["virtual"]["short"]["nominal"] 
                self.risk["total"]['net']["quantity"] += contract["virtual"]["net"]["quantity"] 
                self.risk["total"]['net']["multiplied"] += contract["virtual"]["net"]["multiplied"] 
                self.risk["total"]['net']["nominal"] += contract["virtual"]["net"]["nominal"] 
                self.risk["total"]["max"]["quantity"] += contract["virtual"]["max"]["quantity"] 
                self.risk["total"]["max"]["multiplied"] += contract["virtual"]["max"]["multiplied"] 
                self.risk["total"]["max"]["nominal"] += contract["virtual"]["max"]["nominal"] 
            return True
        except Exception as e:
            self.log.exception(self._inform(f'Risk could not be calculated correctly. Exception: {str(e)}'))
            return False
                    

    def _load_order_data(self, order, strategy, core, allClients=False):
        '''
        This method loads data of all our open orders from the brokers:
        The data of interest is loaded, calculated and stored in a structure,
        separated according to the contract, strategy or symbol to which they 
        belong, so that it is easier to access them using keys.        
        
        core: It is the Core type object that is started and correctly connected.
        allClients: True to get data from all TWS clients. False to get only the current client data.
        return: True if I manage to obtain and process the order data. Otherwise it returns False. 
                The processed order data is stored in the self.orders data structure
        '''
        self.orders = self._empty_orders_data()
        try:
            if allClients:
                openOrders = core.reqAllOpenOrders()    # Call the method to obtain all open orders on all clients.
                time.sleep(5)                           # It pauses with "time" so that no other code is executed during the pause.
                #print('result of reqAllOpenOrders():\n', openOrders)
                #print('result of openTrades():\n', core.openTrades())
            else:
                openOrders = core.openTrades()          # Call the method to obtain all open orders on this client.
            for trade in openOrders:
                contractId, symbol, strategyId, side, quantity, multiplied, nominal = self._common_data_from_trade(trade, core)
                # Updates the open order data structure.
                self._common_data_change(side, "quantity", contractId, symbol, strategyId, quantity)
                self._common_data_change(side, "multiplied", contractId, symbol, strategyId, multiplied)
                self._common_data_change(side, "nominal", contractId, symbol, strategyId, nominal)
                # Updates the risk data structures.
                self._set_risk_data_item("contract", contractId, symbol, strategyId)
                self._set_risk_data_item("strategy", contractId, symbol, strategyId)
            # Add the data of the new order that you intend to place.
            if order is not None and strategy is not None:                
                contractId, symbol, strategyId, side, quantity, multiplied, nominal = self._common_data_from_order(order, strategy)
                # Updates the open order data structure.
                self._common_data_change(side, "quantity", contractId, symbol, strategyId, quantity)
                self._common_data_change(side, "multiplied", contractId, symbol, strategyId, multiplied)
                self._common_data_change(side, "nominal", contractId, symbol, strategyId, nominal)
                # Updates the risk data structures.
                self._set_risk_data_item("contract", contractId, symbol, strategyId)
                self._set_risk_data_item("strategy", contractId, symbol, strategyId)
            return True
        except Exception as e:
            self.log.exception(self._inform(f'Order data could not be processed correctly. Exception: {str(e)}'))
            return False


    def _common_data_from_order(self, order, strategy):
        contractId = str(strategy['contract_id'])
        symbol = strategy['contract'].localSymbol if strategy['mode'] == 'FUTURE' else strategy['contract'].symbol 
        strategyId = strategy['strategy_id']
        side = order.action
        multiplier = int(strategy['contract'].multiplier) if strategy['mode'] == 'FUTURE' else 1
        quantity = self._side_as_sign(side, order.totalQuantity)
        multiplied = self._side_as_sign(side, order.totalQuantity * multiplier)
        nominal = self._side_as_sign(side, order.totalQuantity * multiplier * order.lmtPrice)
        return contractId, symbol, strategyId, side, quantity, multiplied, nominal


    def _common_data_from_trade(self, trade, core):
        contractId = str(trade.contract.conId)
        symbol = trade.contract.localSymbol if trade.contract.localSymbol else trade.contract.symbol
        try:
            strategyId = core.orderIdManager.unpack(trade.order.orderRef)["strategyId"]  
        except:
            strategyId = 'others' 
        side = trade.order.action 
        multiplier = int(trade.contract.multiplier) if trade.contract.multiplier else 1
        quantity = self._side_as_sign(side, trade.order.totalQuantity)
        multiplied = self._side_as_sign(side, trade.order.totalQuantity * multiplier)
        nominal = self._side_as_sign(side, trade.order.totalQuantity * trade.order.lmtPrice * multiplier)
        return contractId, symbol, strategyId, side, quantity, multiplied, nominal


    def _common_data_change(self, side, part, contractId, symbol, strategyId, value):
        '''Make a common change to the data that can be reused.'''
        self.orders[side][part]["contract"][contractId] = value + self.orders[side][part]["contract"].get(contractId, 0)
        self.orders[side][part]["strategy"][strategyId] = value + self.orders[side][part]["strategy"].get(strategyId, 0)
        self.orders[side][part]["symbol"][symbol] = value + self.orders[side][part]["symbol"].get(symbol, 0)
        self.orders[side][part]["total"] = value + self.orders[side][part].get("total", 0)


    def _set_risk_data_item(self, part, contractId, symbol, strategyId, positionQuantity=0, positionNominal=0):
        '''
        Adds or updates an instrument from the self.risk structure.
        part: Part of the data structure to be referred to. "contract" or "strategy"
        contractId: Identifier of the contract to be added or modified.
        symbol: Symbol associated with the contract to be added or modified.
        strategyId: Identifier of the strategy associated with the contract to be added or modified.
        positionQuantity: Quantity of the position in the contract that is to be added or modified. 
        positionNominal: Nominal value of the position in the contract that is to be added or modified.
        '''
        # Determines the part of the structure to update.
        itemId = contractId if part == "contract" else strategyId
        if itemId not in self.risk[part]:
            self.risk[part][itemId] = self._initial_risk_data_item()
        self.risk[part][itemId]["contractId"] = contractId
        self.risk[part][itemId]["symbol"] = symbol
        if strategyId is not None:
            if strategyId not in self.risk[part][itemId]["strategies"]:
                self.risk[part][itemId]["strategies"].append(strategyId)
                
        # Establishes the values ​​obtained from the orders.
        quantityBuy = self.orders["BUY"]["quantity"][part].get(itemId, 0)
        multipliedBuy = self.orders["BUY"]["multiplied"][part].get(itemId, 0)
        nominalBuy = self.orders["BUY"]["nominal"][part].get(itemId, 0)
        quantitySell = self.orders["SELL"]["quantity"][part].get(itemId, 0)
        multipliedSell = self.orders["SELL"]["multiplied"][part].get(itemId, 0)
        nominalSell = self.orders["SELL"]["nominal"][part].get(itemId, 0)
        self.risk[part][itemId]["orders"]["buy"]["quantity"] = quantityBuy
        self.risk[part][itemId]["orders"]["buy"]["multiplied"] = multipliedBuy
        self.risk[part][itemId]["orders"]["buy"]["nominal"] = nominalBuy
        self.risk[part][itemId]["orders"]["sell"]["quantity"] = quantitySell
        self.risk[part][itemId]["orders"]["sell"]["multiplied"] = multipliedSell
        self.risk[part][itemId]["orders"]["sell"]["nominal"] = nominalSell
        self.risk[part][itemId]["orders"]["net"]["quantity"] = quantityBuy + quantitySell
        self.risk[part][itemId]["orders"]["net"]["multiplied"] = multipliedBuy + multipliedSell
        self.risk[part][itemId]["orders"]["net"]["nominal"] = nominalBuy + nominalSell
        
        # Establishes the values ​​obtained from the portfolio.
        self.risk[part][itemId]["position"]["net"]["quantity"] = positionQuantity
        self.risk[part][itemId]["position"]["net"]["nominal"] = positionNominal
        
        # Establishes the calculated virtual values.
        quantityLong = positionQuantity + quantityBuy 
        quantityShort = positionQuantity + quantitySell
        multipliedLong = positionQuantity + multipliedBuy 
        multipliedShort = positionQuantity + multipliedSell
        nominalLong = positionNominal + nominalBuy
        nominalShort = positionNominal + nominalSell
        self.risk[part][itemId]["virtual"]["long"]["quantity"] = quantityLong
        self.risk[part][itemId]["virtual"]["long"]["multiplied"] = multipliedLong
        self.risk[part][itemId]["virtual"]["long"]["nominal"] = nominalLong
        self.risk[part][itemId]["virtual"]["short"]["quantity"] = quantityShort
        self.risk[part][itemId]["virtual"]["short"]["multiplied"] = multipliedShort
        self.risk[part][itemId]["virtual"]["short"]["nominal"] = nominalShort
        self.risk[part][itemId]["virtual"]["net"]["quantity"] = positionQuantity + quantityBuy + quantitySell
        self.risk[part][itemId]["virtual"]["net"]["multiplied"] = positionQuantity + multipliedBuy + multipliedSell
        self.risk[part][itemId]["virtual"]["net"]["nominal"] = positionQuantity + nominalBuy + nominalSell
        self.risk[part][itemId]["virtual"]["max"]["quantity"] = max(abs(quantityLong), abs(quantityShort))
        self.risk[part][itemId]["virtual"]["max"]["multiplied"] = max(abs(multipliedLong), abs(multipliedShort))
        self.risk[part][itemId]["virtual"]["max"]["nominal"] = max(abs(nominalLong), abs(nominalShort))        
        

    def _initial_risk_data_item(self):
        '''
        Returns an initialized risk data item structure.
        The way to calculate the multiplications and nominals of each order is as follows
        multiplier = order1.quantity * order1.multiplier
        nominal = order1.quantity * order1.multiplier * market.price
        '''
        return {
            "contractId": None,         
            "symbol": None,     
            "strategies": [],           # Save the IDs of the strategy on this item.            
            "orders": {                 # These are the open order data.
                "buy": {                # Must be positive values:
                    "quantity": 0,      # Sum of buy order quantities
                    "multiplied": 0,    # Sum of buy orders quantities after applying their multiplier
                    "nominal": 0        # Sum of buy order nominals
                }, 
                "sell": {               # Must be negative values:
                    "quantity": 0,      # Sum of buy order quantities
                    "multiplied": 0,    # Sum of buy orders quantities after applying their multiplier
                    "nominal": 0        # Sum of buy order nominals
                }, 
                "net": {                # They can be positive or negative values:
                    "quantity": 0,      # Net value of quantities
                    "multiplied": 0,    # Net value of multiplied
                    "nominal": 0        # Net value of nominals
                }
            },
            "position": {               # They are data obtained from the broker or dynamically calculated
                "net": {                # They can be positive or negative values:
                    "quantity": 0,      # Current position amount in the broker
                    "nominal": 0        # Current nominal value of position in the broker
                }
            },
            "virtual": {                # Risk calculation by counting the position and open orders
                "long": {               # They can be positive or negative values:
                    "quantity": 0,      # Position quantity plus the quantity of open buy orders.
                    "multiplied": 0,    # Position quantity plus the open buys, taking into account the multiplier
                    "nominal": 0        # Position nominal plus the nominal of open buy orders.
                }, 
                "short": {              # They can be positive or negative values:
                    "quantity": 0,      # Position quantity plus the quantity of open sell orders.
                    "multiplied": 0,    # Position quantity plus the open sells, taking into account the multiplier
                    "nominal": 0        # Position nominal plus the nominal of open sell orders.
                }, 
                "net": {                # They can be positive or negative values:
                    "quantity": 0,      # Position quantity plus the net of open orders.
                    "multiplied": 0,    # Position quantity plus the net of open orders, taking into account the multiplier
                    "nominal": 0        # Position nominal plus the net nominal of open orders.
                },
                "max": {                # Must be positive values:
                    "quantity": 0,      # Max quantity between long quantity and short quantity.
                    "multiplied": 0,    # Max multiplied between long multiplied and short multiplied.
                    "nominal": 0        # Max nominal between long nominal and short nominal.
                }
            }
        }


    def _side_as_sign(self, side, value=1):
        '''
        Converts the string side to an operation direction sign
        side: "BUY" for 1 or "SELL" for -1
        value: Value to which the sign should be applied.
        '''
        return value if side == 'BUY' else -value 


    def _inform(self, text, cmd=True, chat=True):
        '''It allows you to put a message in CMD, LOG and send it to CHAT Telegram.'''
        if cmd: print(str(text))
        text = str(text).lstrip()
        if chat: telegram.send_to_telegram(text, self.configuration)
        return text 


    def _empty_orders_data(self):
        '''Create empty orders data structure.'''
        return {
            "BUY": {
                "quantity": self._empty_orders_data_portions(),
                "multiplied": self._empty_orders_data_portions(),
                "nominal": self._empty_orders_data_portions()
            }, 
            "SELL": {
                "quantity": self._empty_orders_data_portions(),
                "multiplied": self._empty_orders_data_portions(),
                "nominal": self._empty_orders_data_portions()
            }
        }
    

    def _empty_orders_data_portions(self):
        '''Create the portions of the data structure.'''
        return {
            "contract": {},     # Store the values by contracts.
            "strategy": {},     # Store the values by strategies.
            "symbol": {},       # Store the values by symbols.
            "total": 0          # Store total of nominals buys.
        }


    def _empty_risk_data(self):
        '''Create empty risk data structure.'''
        return {
            "contract": {},     # Store the risk data by instruments.
            "strategy": {},     # Store the risk data by strategies.
            "total": {
                "long": {
                    "quantity": 0,
                    "multiplied": 0,
                    "nominal": 0
                }, 
                "short": { 
                    "quantity": 0,
                    "multiplied": 0,
                    "nominal": 0 
                }, 
                "net": { 
                    "quantity": 0, 
                    "multiplied": 0, 
                    "nominal": 0
                },
                "max": { 
                    "quantity": 0, 
                    "multiplied": 0,
                    "nominal": 0
                }
            }
        }

    
    def _initialize_dynamic_position_item(self, contractId, symbol, strategyId, value=0):
        '''Create empty dynamic position item structure.'''
        return {
            "contractId": contractId,
            "symbol": symbol,
            "strategyId": strategyId,
            "value": value
        }
    
    
    
    