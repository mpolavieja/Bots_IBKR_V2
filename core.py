
'''
Crea un objeto que representa al broker o exchange.
Esta clase extiende las propiedades y metodos de la clase IB de ib_insync.
'''
import time
import ctypes
from ib_insync import *
from risk_manager import RiskManager
from datetime import datetime, timedelta
from order_id_manager import OrderIdManager
from multi_parameters import MultiParameters

# Manuel. Esto se puede eliminar, ahora ya está toda esta funcionalidad en la clase Dashboard
import logging
import telegram
from dashboard import Dashboard
from write_google_sheets import write_orders_to_google_sheets, write_fill_to_google_sheets


ctypes.windll.kernel32.SetConsoleTitleW(__file__)
#Cambia el título de la ventana de la consola en la que se está ejecutando el script de Python para que coincida con el nombre del archivo de script actual

class Core(IB):
    def __init__(self, configuration):
        '''
        Crea un objeto que representa al broker o exchange.
        Esta clase es una abstrapción para evitar que el bot baneje directamente 
        los detalles de interaccion con el broker o exchange.
        '''
        IB.__init__(self)
        self.configuration = configuration
        self.orderIdManager = OrderIdManager(self.configuration['client_tws'])
        self.parameters = MultiParameters(self.configuration)
        self.dashBoard = Dashboard(self.configuration) 
        self.riskManager = RiskManager(self.configuration)
        self.lastTimeOrder = None
        self.lastTimeActualize = time.time()
        self.log = logging.getLogger('grid')
        self.last_connection_time = time.time()
        
    
    def set_actualize_bot_status(self):
        '''
        Verifica la conexion del bot, actualiza el estado de la configuracion multiparametrica 
        y realiza las acciones indicadas en la configuración de cada estrategia.
        '''
        if 'debug_mode' in self.configuration:
            if self.configuration['debug_mode']:
                nowTime = time.time()
                seconds = round(nowTime - self.lastTimeActualize, 2)
                self.lastTimeActualize = nowTime
                if self.isConnected():
                    print('conectado...', 'seconds:', seconds)
                else:
                    print('desconectado...', 'seconds:', seconds)
        try:
            pass
            if self.isConnected():
                self.last_connection_time = time.time()   # Registra el tiempo de la ultima conexion comprobada.
                self.parameters.load(self)
                for strategy in self.parameters.strategies:
                    #print('contract_id:', self.get_contract_id(strategy))  # Esto lo utilice para probar la funcion get_contract_id
                    
                    # Si el precio es cero, solicitamos el precio al mercado
                    if float(strategy['precio_ini']) == float(0):
                        strategy['precio_ini'] = self.get_price(strategy)
                    
                    if strategy['precio_ini'] is not None:
                        if strategy['action'] == 'NEW' or strategy['action'] == 'START':
                            if strategy['active']:
                                self.dashBoard.update_dashboard(self)
                                msg = 'On contract {}, strategy {} {}'.format(strategy['contract_id'], strategy['strategy_id'], strategy['action'])
                                print(msg)
                                self.log.info(msg)
                                self.post_grid_orders(strategy)
                        elif strategy['action'] == 'STOP' or strategy['action'] == 'DELETED':
                            msg = 'Estrategia {} {}'.format(strategy['strategy_id'], strategy['action'])
                            print(msg)
                            self.log.info(msg)
                            self.cancel_orders_of_strategy(strategy['strategy_id'])
                        elif strategy['action'] == 'CONTINUE':
                            # No se reporta nada. Continua trabajando OK
                            pass
                        else:
                            self.log.warn('No se reconoce la accion "{}" de la estrategia {}'.format(strategy['action'], strategy['strategy_id']))
                            pass 
                    else:
                        self.log.warn('No se pudo obtener el precio para la estrategia: {}'.format(strategy['strategy_id']))
                    self.sleep(0)   # Garantiza el funcionamiento asyncrono
            else:
                self.log.error('No hay conexion con Interactive Brokers!!!')
                telegram.send_to_telegram(f"{datetime.now()} - {__file__} - Atencion! Error! No hay conexion con Interactive Brokers", self.configuration)   

            self.dashBoard.update_dashboard(self)          
            msg_heartbeat = f"{datetime.now()} -- {__file__} -- Heartbeat"  
            with open("heartbeat.txt", "w") as f: f.write(msg_heartbeat)
        except Exception as e:
            self.log.exception('Error: {}'.format(str(e)))            
        finally:
            self.schedule(
                callback=self.set_actualize_bot_status, 
                time=self.get_timestamp_for_seconds(self.configuration['actualize_status_seconds'])
            ) 
             

    def get_contract_id(self, contract):
        '''
        Solicitar los detalles del contrato para obtener el conId.
        contract: Objeto de contrato que puede ser Stock, Future, etc
        return: Devuelve el ID del contrato. SI ocurre error, reporta al log y devuelve None.
        '''
        try:
            self.qualifyContracts(contract)
            return contract.conId
        except Exception as e:
            self.log.exception('No se pudo obtener el ID de contrato para: {}'.format(contract))
            return None


    def get_price(self, strategy):
        '''
        Pedimos el precio y cancelamos la suscripción.
        Si no se cancela la suscripción, se produce un error.
        
        '''
        ################################
        # Esto hay que implementarlo.... ###
        ################################
        return None


    def onExecDetailsEvent(self, trade, fill):
        self.dashBoard.load_fill(fill)   #******* OJO ***** esto deberia ejecutarse despues del if (float(trade.remaining()) == 0):
        try:
            if (float(trade.remaining()) == 0):
                self.riskManager.add_executed_operation(trade, self)
                unpackedOrderId = self.orderIdManager.unpack(int(trade.order.orderRef))
                strategy = self.parameters.get_strategy(unpackedOrderId['strategyId'])
            
                if strategy is None: return
                if not strategy['active']: return
                if strategy['action'] == 'DELETED': return
                if strategy['action'] == 'STOP': return
                
                msg = 'Ejecutada la orden {} tipo {} de la estrategia {} al precio {}'.format(
                    unpackedOrderId['number'], 
                    unpackedOrderId['side'],
                    unpackedOrderId['strategyId'],
                    trade.order.lmtPrice
                )
                print('{} - {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg))
                self.log.info(msg)
                telegram.send_to_telegram(msg, self.configuration)

                if (trade.order.action == "SELL"): 
                    self.post_order(strategy, 'BUY', trade.order.lmtPrice - strategy['escalon'], prefix='Reaction ')                
                elif (trade.order.action == "BUY"):
                    self.post_order(strategy, 'SELL', trade.order.lmtPrice + strategy['escalon'], prefix='Reaction ')                
                else:
                    pass
        except Exception as e:
            text = 'Error poniendo orden contraria al trade'
            self.log.exception('{}: {} {}'.format(text, trade, fill))
            return


    def post_grid_orders(self, strategy):
        '''
        Crea las órdenes de compra y venta que componen la cuadrícula (grid).
        strategy: Esta es la configuración de la estrategia que se va a realizar con el grid.
        initialPrice: Precio central a partir del cual se calculan los niveles de comra y venta del grid.
        return: True si pudo poner las ordenes y False si ocurre algun error.
        '''
        try:
            print("{} - Insertando ordenes para crear el GRID...".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            print('   Initial price:', strategy['precio_ini'], strategy['currency'])
            initialPrice = strategy['precio_ini']
            # Manuel. 11-10-23. OJO!! en las compras podrían darse precios negativos. Hay que controlarlo.            
            for ordinal in range(1, strategy['compras'] + 1):
                self.post_order(strategy, 'BUY', initialPrice - (strategy['escalon'] * ordinal), prefix=f'Initial Low {ordinal} ')
                self.sleep(0)   # Garantiza el funcionamiento asyncrono
            for ordinal in range(1, strategy['ventas'] + 1):
                self.post_order(strategy, 'SELL', initialPrice + (strategy['escalon'] * ordinal), prefix=f'Initial Up {ordinal} ')
                self.sleep(0)   # Garantiza el funcionamiento asyncrono
            self.log.info('Se han creado las ordenes grid de la estrategia {}'.format(strategy['strategy_id']))
            return True
        except Exception as e:
            self.log.exception('Error creando ordenes grid de la estrategia {}'.format(strategy['strategy_id']))
            return False


    def post_order(self, strategy, side, price, verbose=True, prefix=''):
        '''
        Agrega una orden de compra o venta que componen la cuadrícula (grid).
        
        strategy: Esta es la configuración de la estrategia que se va a realizar.
        side: Este es el tipo de operación que se va a realizar BUY o SELL.
        price: Este es el precio en el que se va a poner la orden.
        return: Retorna True si se pudo poner la orden. De lo contrario False.
        '''           
        try:
            orderId = self.orderIdManager.create_id(strategy['contract_id'], strategy['strategy_id'], side)
            order = LimitOrder(side, strategy['cantidad_orden'], price, outsideRth=True, tif="GTC", orderRef=orderId)
            if self.validate_order(order, strategy):
                trade = self.placeOrder(strategy['contract'], order)
                self.lastTimeOrder = datetime.now()
                self.sleep(0)   # Garantiza el funcionamiento asyncrono
                msg = f"{prefix}Order: {orderId} {side} {order.totalQuantity} en {trade.contract.symbol} al precio {order.lmtPrice}"
                if verbose: print(f'   {msg}')
                self.log.info(msg)
                telegram.send_to_telegram(msg, self.configuration)
            else:
                if verbose: print('   Riesgo no aceptable. No se insertó la orden {} {} en precio {}'.format(side, strategy['symbol'], price))
        except Exception as e:
            self.log.exception('Error agregando orden {} {} en precio {}'.format(side, strategy['symbol'], price))
            return False


    def validate_order(self, order, strategy, verbose=False):
        '''
        Esta funcion analiza los datos de la orden y el contexto para validar la realización.
        
        strategy: Esta es la configuración de la estrategia que se va a realizar.
        side: Este es el tipo de operación que se va a realizar BUY o SELL.
        price: Este es el precio en el que se va a poner la orden.
        orderId: Este es el identificador con el que se va a poner la orden.
        self: En el parámetro self se va a tener acceso al resto de las funciones de la clase core.
        return: Retorna True para autorizar la realización de la operación o False para no realizarla.
        '''
        timeBegin = time.time()
        operate = self.riskManager.can_operate(order, strategy, self)
        if not operate: 
            text = f'   Order rejected at {round(time.time()-timeBegin, 2)} seconds'
            self.log.info(text)
            if verbose and not operate: 
                print(text)
        return operate


    def cancel_all_orders(self, verbose=True):
        '''
        Cancela las órdenes activas del cliente.
        verbose: Pongase en False para que no se muestren mensajes en consola.
        return: Devuelve True si se ejecuta correctamente. False si ocurre un error. 
        '''
        # Manuel. ¿Esto por qué lo hacemos al principio? No me acuerdo.
        self.dashBoard.update_dashboard(self)
        try:
            count = 0
            if verbose:
                print('{} - Buscando órdenes pendientes de todas las estrategias del cliente...'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            # Manuel.  Cambiar por self.reqAllOpenOrders() por si acaso openORders() no descarga las órdenes que no son de este cliente
            # Manuel.  Crear un parámetro global para indicar si se cancela todo o no, incluidas órdenes de otros clientes
            # Manuel.  El valor por defecto del parámetro global es que si, se cancelaría todo
            for order in self.openOrders():
                if self.orderIdManager.is_order_child_of_client(order.orderRef):
                    if verbose:
                        print('   Cancelada orden', order.orderRef)
                    self.cancel_order(order)
                    count += 1
                self.sleep(0)   # Garantiza el funcionamiento asyncrono
            msg = 'Se han cancelado {} órdenes pendientes de todas las estrategias del cliente'.format(count)
            if verbose:
                print(f'   {msg}')
            self.log.info(msg)
            return True
        except Exception as e:
            self.log.exception('Error cancelando ordenes')
            return False


    def cancel_orders_of_strategy(self, strategyId, verbose=True):
        '''
        Cancela las órdenes activas de una estrategia especifica.
        strategyId: Número identificador de la estrategia que se debe cancelar.
        verbose: Pongase en False para que no se muestren mensajes en consola.
        return: Devuelve True si se ejecuta correctamente. False si ocurre un error. 
        '''
        try:
            count = 0
            if verbose:
                print('{} - Buscando órdenes pendientes de la estrategia...'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), strategyId))
            for order in self.openOrders():
                if self.orderIdManager.is_order_child_of_strategy(order.orderRef, strategyId):
                    if verbose:
                        print('   Cancelada orden', order.orderRef)
                    self.cancel_order(order)
                    count += 1
                self.sleep(0)   # Garantiza el funcionamiento asyncrono
            msg = 'Se han cancelado {} órdenes pendientes de la estrategia {}'.format(count, strategyId)
            if verbose:
                print(f'   {msg}')
            self.log.info(msg)
            return True
        except Exception as e:
            self.log.exception('Error cancelando ordenes de estrategia {}'.format(strategyId))
            return False


    def cancel_order(self, order, awaitSeconds=10):
        '''
        Ordena cancelar una orden y espera un tiempo a que termine.
        order: Es un objeto que representa a la orden.
        awaitSeconds: Cantidad de segundos maximos que se debe esperar.
        return: Retorna True si logra cancelar antes del tiempo de espera.
        '''
        try:
            self.cancelOrder(order)
            while awaitSeconds > 0:
                if not self.order_exist(order.orderRef):
                    return True
                self.sleep(1)   # Garantiza el funcionamiento asyncrono
                awaitSeconds -= 1              
            return False
        except Exception as e:
            self.log.exception(str(e))
            return False


    def order_exist(self, orderID):
        '''Devuelve True si la orden especificada existe.'''
        try:
            return len(list(filter(lambda x: x.orderRef == orderID, self.openOrders()))[0]) > 0
        except:
            return False
        

    def get_timestamp_for_seconds(self, seconds):
        '''Devuelve el DateTime correspondiente a la fecha actual mas los segundos indicados.'''
        return datetime.now() + timedelta(seconds=seconds)


                
#print(LimitOrder('BUY', 10, 12.99, outsideRth=True, tif="GTC", orderRef='santiago'))


