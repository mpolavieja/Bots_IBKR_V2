
'''
Crea un objeto para manejar los parametros de funcionamiento del bot.
Esta clase es una abstrapción para evitar que el bot baneje directamente 
el almacanamiento de datos.
Creado: 17-09-2023
Version de Python: 3.10'
'''
__version__ = '1.0'

from google_sheets_interface import GoogleSheetsInterface
from ib_insync import *
import logging
import time


class MultiParameters():
    
    def __init__(self, configuration, page=None, beginColumn=1, beginRow=1, columns=2, rows=300):
        '''
        Crea un objeto para manejar los parametros de funcionamiento del bot.
        Esta clase es una abstrapción para evitar que el bot maneje directamente 
        el almacanamiento de datos, además que facilita el filtrado de los parámetros.
        '''
        self.configuration = configuration
        self.multiTable = GoogleSheetsInterface(
            self.configuration['google_sheets_credentials'], 
            self.configuration['google_sheets_document_id']
        )
        self.page = page
        self.beginColumn = beginColumn
        self.beginRow = beginRow
        self.columns = columns
        self.rows = rows
        self.strategies = []
        self.log = logging.getLogger('grid')
        

    def reset(self):
        '''
        Elimina el historial de las estrategias, lo cual hace que todas 
        las estrategias activas se etiqueten como NEW.
        '''
        self.strategies = []


    def load(self, ib, verbose=False):
        '''
        Carga los parámetros desde el almacenamiento y devuelve      
        True: Si se pudieron leer los parámetros desde el almacenamiento.
        False: Si ocurrieron errores durante la lectura de los parámetros. 
        '''
        timeBegin = time.time()
        if verbose:
            print('\nLeyendo estrategias desde la configuracion...')
        tables = self.multiTable.read_tables(self.page, self.beginColumn, self.beginRow, self.columns, self.rows)
        tables = self._process_and_filter_strategy_params(tables)
        tables = self._add_contract_parameters(ib, tables)
        tables = self._add_action_parameter(tables, self.strategies)
        deletedList = self._create_deleted_list(tables, self.strategies)
        tables.extend(deletedList)
        self.strategies = tables
        if verbose:
            for strategy in self.strategies:
                print('   Estrategia: {} Acción: {}'.format(strategy['strategy_id'], strategy['action']))
            print('   Tiempo de lectura:', round(time.time()-timeBegin, 2), 'segundos')


    def get_strategy(self, strategyId):
        '''Devuelve la estrategia indicada mediante Id o devuelve None si no existe'''
        try:
            return list(filter(lambda x: int(x['strategy_id']) == int(strategyId), self.strategies))[0]
        except:
            return None    


    def _add_contract_parameters(self, ib, newStrategiesList):
        '''Devuelve la lista de estrategias, pero con los parametros contract y contract_id establecidos.'''
        result = []
        for strategy in newStrategiesList:
            contract = self._create_contract_parameters(strategy)
            strategy['contract'] = contract
            strategy['contract_id'] = ib.get_contract_id(contract)
            result.append(strategy)
        return result


    def _add_action_parameter(self, newStrategiesList, previousStrategiesList):
        '''Devuelve la lista de las estrategias con el parámetro action establecido.'''
        result = []
        for newStrategy in newStrategiesList:
            previousStrategy = list(filter(   # Busca el estado anterior de la estrategia.
                lambda x: x['strategy_id'] == newStrategy['strategy_id'], 
                previousStrategiesList
            ))
            previousStrategy = previousStrategy[0] if len(previousStrategy) > 0 else None
            strategy = self._set_strategy_action(newStrategy, previousStrategy)
            if strategy is not None:
                result.append(strategy)
        return result


    def _create_deleted_list(self, newStrategiesList, previousStrategiesList):
        '''Devuelve la lista de las estrategias eliminadas con el parametro action establecido.'''
        result = []
        for previousStrategy in previousStrategiesList:
            if previousStrategy['action'] != 'DELETED':
                newStrategy = list(filter(   # Busca el estado actual de la estrategia.
                    lambda x: x['strategy_id'] == previousStrategy['strategy_id'], 
                    newStrategiesList
                ))
                if len(newStrategy) == 0:
                    strategy = self._set_strategy_action(None, previousStrategy)
                    if strategy is not None:
                        result.append(strategy)
        return result


    def _set_strategy_action(self, newStrategyParam, previousStrategyParam):
        '''
        Agrega el parámetro action a la configuracion de una estrategia.
        Compara los parámetros actuales de la estrategia con los parámetros anteriores.
        
        newStrategyParam: Es el objeto con los nuevos parámetros de de la estrategia.
        previousStrategyParam: Contiene los parámetros anteriores de de la estrategia.
        return: 
        Devuelve la configuración nueva de la estrategia con el parámetro
        action establecido a uno de los siguiente valores:
            NEW = La configuración es de una estrategia nueva que se ha agregado.
            STOP = La configuración indica que se debe detener la estrategia.
            START = La configuración indica que se debe lanzar la estrategia.
            CONTINUE = La configuración indica que la estrategia debe continuar.
            DELETED = Indica que se debe eliminar la estrategia.
        Devuelve None si no se debe agregar la estrategia.
        Si previousStrategyParam es None, se devuelve la estrategia newStrategyParam 
        con el parametro "action" igual a "NEW", solo si el parametro "active" es True.
        De lo contrario devuelve None.
        '''
        if previousStrategyParam is None and newStrategyParam is None:
            return None
        if previousStrategyParam is None:
            newStrategyParam['action'] = 'NEW'
            return newStrategyParam if newStrategyParam['active'] else None
        elif newStrategyParam is None:
            previousStrategyParam['action'] = 'DELETED'
            return previousStrategyParam
        else:
            if previousStrategyParam['active'] and not newStrategyParam['active']:
                newStrategyParam['action'] = 'STOP'
                return newStrategyParam
            elif not previousStrategyParam['active'] and newStrategyParam['active']:
                newStrategyParam['action'] = 'START'
                return newStrategyParam
            else:
                # Importante: Si no hay cambios en el parametro 'active' se deben 
                # mantener los mismos datos que ya estan en el bot aunque ya existan 
                # datos nuevos puestos por el usuario en el FrontEnd.
                previousStrategyParam['action'] = 'CONTINUE'
                return previousStrategyParam


    def _create_contract_parameters(self, strategyParams):
        '''Crea el parametro contract (Stock, Future) que se necesita para lanzar las ordenes.'''
        if strategyParams is None or strategyParams == {}:
            return None
        if strategyParams['mode'] == 'FUTURE':
            return Future(
                symbol = strategyParams['symbol'], 
                lastTradeDateOrContractMonth = strategyParams['future_last_trade_date_or_contract_month'], 
                exchange = strategyParams['exchange'], 
                localSymbol = strategyParams['future_local_symbol'], 
                multiplier = strategyParams['future_multiplier'],
                currency = strategyParams['currency']
            )
        elif strategyParams['mode'] == 'STOCK':
            return Stock(
                strategyParams['symbol'],
                strategyParams['exchange'],
                strategyParams['currency'] 
            )
        else:
            return None
        

    def _process_strategy_params(self, strategy, debugMode=False):
        '''
        Transforma los parametros de la estrategia y los convierte al tipo de datos que se necesita.
        strategy: Es un diccionario con los parametros de la estrategia.
        return: Retorna la misma strategy pero con los tipos de datos 
                establecidos segun la necesidad del algoritmo del Bot.
				Si ocurre un error procesando la estrategia, devuelve None.
        '''
        if strategy is None or strategy == {}:
            if debugMode:
                self.log.error('La estrategia no puede ser un valor None.')
            return None

        if strategy['strategy_id'] is None:
            if debugMode:
                self.log.error('Falta el identificador de la estrategia.')
            return None
        prefix = 'En la estrategia {}'.format(strategy['strategy_id'])
        try:
            # Intenta convertir los valores al tipo de dato requerido.
            strategy['active'] = self.multiTable.is_active(strategy['active'])
            if not strategy['active']: 
                return None
            
            # Intenta convertir los valores al tipo de dato requerido.
            strategy['strategy_id'] = int(strategy['strategy_id'])
            strategy['precio_ini'] = self.multiTable.string_to_float(strategy['precio_ini'])
            strategy['cantidad_orden'] = int(strategy['cantidad_orden'])
            strategy['escalon'] = self.multiTable.string_to_float(strategy['escalon'])
            strategy['compras'] = int(strategy['compras'])
            strategy['ventas'] = int(strategy['ventas'])
            strategy['max_long_risk'] = float(strategy['max_long_risk'])
            strategy['max_short_risk'] = float(strategy['max_short_risk'])

            # Verifica que los valores numericos esten en los rangos aceptables.
            if strategy['precio_ini'] < 0: 
                if debugMode:
                    self.log.error('{}, el parámetro "precio_ini" no puede ser negativo.'.format(prefix))
                return None
            if strategy['cantidad_orden'] < 0: 
                if debugMode:
                    self.log.error('{}, el parámetro "cantidad_orden" no puede ser negativo.'.format(prefix))
                return None
            if strategy['escalon'] < 0: 
                if debugMode:
                    self.log.error('{} el parámetro "escalon" no puede ser negativo.'.format(prefix))
                return None
            if strategy['compras'] < 0: 
                if debugMode:
                    self.log.error('{} el parámetro "compras" no puede ser negativo.'.format(prefix))
                return None
            if strategy['ventas'] < 0: 
                if debugMode:
                    self.log.error('{} el parámetro "ventas" no puede ser negativo.'.format(prefix))
                return None
            if strategy['max_long_risk'] < 0: 
                if debugMode:
                    self.log.error('{} el parámetro "max_long_risk" no puede ser negativo.'.format(prefix))
                return None
            if strategy['max_short_risk'] < 0: 
                if debugMode:
                    self.log.error('{} el parámetro "max_short_risk" no puede ser negativo.'.format(prefix))
                return None

            # Comprueba si existen los parametros comunes
            if strategy['mode'] is None: 
                if debugMode:
                    self.log.error('{} falta el valor del parámetro "mode"'.format(prefix))
                return None
            if strategy['symbol'] is None: 
                if debugMode:
                    self.log.error('{} falta el valor del parámetro "symbol"'.format(prefix))
                return None
            if strategy['exchange'] is None: 
                if debugMode:
                    self.log.error('{} falta el valor del parámetro "exchange"'.format(prefix))
                return None
            if strategy['currency'] is None: 
                if debugMode:
                    self.log.error('{} falta el valor del parámetro "currency"'.format(prefix))
                return None

            # Comprueba si existen los parametros del modo FUTURE
            if strategy['mode'] == 'FUTURE':
                if strategy['future_last_trade_date_or_contract_month'] is None: 
                    if debugMode:
                        self.log.error('{} falta el valor del parámetro "future_last_trade_date_or_contract_month"'.format(prefix))
                    return None
                if strategy['future_local_symbol'] is None: 
                    if debugMode:
                        self.log.error('{} falta el valor del parámetro "future_local_symbol"'.format(prefix))
                    return None
                if strategy['future_multiplier'] is None: 
                    if debugMode:
                        self.log.error('{} falta el valor del parámetro "future_multiplier"'.format(prefix))
                    return None   
            return strategy
        except Exception as e:
            if debugMode:
                self.log.exception('{}, ocurrio un error leyendo los parámetros...'.format(prefix))
            return None


    def _process_and_filter_strategy_params(self, strategies):
        '''
        Transforma los parametros de la lista al tipo de datos que se necesita.

        parameters: Es un array que contiene las tablas leidas.
        return: Retorna la misma lista de tablas (parametros) pero con los tipos
                de datos establecidos segun la necesidad del algoritmo del Bot.
        '''
        result = []
        for strategy in strategies:
            strategyTyped = self._process_strategy_params(strategy, False)
            if strategyTyped is not None:
                result.append(strategyTyped)
            else:
                #self.log.error('No se pudo agregar la estrategia: {}'.format(strategy))
                pass
        return result



def test():
    '''Muestra como utilizar la librería y permite probarla.'''
    print('Presione Ctrl+C si desea abortar la prueba')
    print('Haga los cambios en la hoja Google Sheet y los verá aquí:')
    parameters = MultiParameters()
    while True:
        parameters.load(True)
        time.sleep(5)

#test()