
'''
Crea un objeto para el manejo de los ID de las ordenes.
Creado: 18-09-2023
Version de Python: 3.10'
'''

__version__ = '1.0'

import time

# Esta es la definicion de la estructura que compone al identificador de ordenes.
FIELDS = [
    {'name':'number', 'bits':64},       # Número de la orden. Puede ser el número del nivel grid.
    {'name':'side', 'bits':1},          # Tipo de operación: BUY o SELL
    {'name':'strategyId', 'bits':8},    # Número que identifica a la estrategia dentro del cliente.
    {'name':'contractId', 'bits':32},   # Número que identifica al contrato.
    {'name':'clientId', 'bits':8},      # Número del cliente.
]

class OrderIdManager():
    
    def __init__(self, clientId):
        '''
        Crea un objeto para el manejo de los ID de las ordenes.
        El ID permite relacionar una orden con una instancia del cliente
        y con una ejecucion dentro de la misma instancia del cliente. 
        clientId: Número identificador del cliente que se conecta.
        '''
        self.clientId = clientId
        self.fields = []
        self.totalBits = 0
        for field in FIELDS:
            field['displacement'] = self.totalBits
            self.fields.append(field)
            self.totalBits += field['bits']
                

    def create_id(self, contractId, strategyId, side, number=None):
        '''
        Crea un identificador para una orden                 
        Envuelve a self.pack() con los mismos parametros.
        '''
        return self.pack(self.clientId, contractId, strategyId, side, number=number)
    
    
    def create_id_from_unpacked(self, unpackedId):
        '''
        Crea un identificador para una orden a partir de otro Id desempaquetado.            
        Envuelve a self.pack() con los mismos parametros.
        '''
        return self.pack(
            unpackedId['clientId'], 
            unpackedId['contractId'],
            unpackedId['strategyId'], 
            unpackedId['side'], 
            unpackedId['number']
        )
    
    
    def is_order_child_of_client(self, orderId):
        '''Devuelve True si el orderId pertenece al cliente clientId, de lo contrario False.'''
        unpacked = self.unpack(orderId)
        if unpacked is not None:
            return self.unpack(orderId)['clientId'] == self.clientId
        else:
            return False

    
    def is_order_child_of_strategy(self, orderId, strategyId):
        '''
        True si el orderId pertenece a la ejecucion strategyId del clientId, de lo contrario False.
        Si el orderId no se puede desempaquetar, se devuelve False.
        '''
        unpacked = self.unpack(orderId)
        if unpacked is not None:
            return int(unpacked['clientId']) == int(self.clientId) and int(unpacked['strategyId']) == int(strategyId)
        else:
            return False
    

    def unpack(self, orderId):
        '''
        Decodifica un identificador de una orden  
               
        orderId: Identificador de la orden.
        return: Devuelve un objeto con los componentes del identificador.
        '''
        try:
            result = {}
            for field in self.fields:
                result[field['name']] = self._limit(
                    int(orderId) >> int(field['displacement']), 
                    int(field['bits'])
                )
            if result['side'] == 1:
                result['side'] = 'SELL'
            else:
                result['side'] = 'BUY'
            return result
        except:
            return None
    

    def pack(self, clientId, contractId, strategyId, side, number=None):
        '''
        Crea un identificador para una orden         
        
        contractId: Numero identificador del contrato.
        strategyId: Número identificador de la ejecución del algoritmo.
        side: Tipo de operacion. Puede ser "SELL" o "BUY".
        number: Número de la orden. Si se pasa None, se utiliza el timestamp en milisegundos.
        return: Devuelve un número identificador para una orden de compra o venta.
        '''
        if number is None:
            number = round(time.time() * 1000)        
        clientId = int(clientId) << int(self.fields[4]['displacement'])
        contractId = int(contractId) << int(self.fields[3]['displacement'])
        strategyId = int(strategyId) << int(self.fields[2]['displacement'])
        side = (1 if side == "SELL" else 0) << int(self.fields[1]['displacement'])
        number = int(number) << int(self.fields[0]['displacement'])
        return int(clientId | strategyId | side | number)
    

    def _mask(self, bits):
        '''
        Crea una mascara de n bits.
        bits: Cantidad de bits a la que debe ser limitado el número.
        '''
        mask = 0
        for n in range(bits):
            mask = mask | (1 << n)
        return mask
    
    
    def _limit(self, number, bits):
        '''
        Limita el valor de un número a una cantidad determinada de bits.
        number: Número que debe ser limitado.
        bits: Cantidad de bits a la que debe ser limitado el número.
        return: El número limitado a la cantidad de bits especificados.
        '''
        return number & self._mask(bits)



def test():
    '''
    Se utiliza para testear esta libreria.
    Solo hay que ejecutarlo y si hay errores, los muestra en pantalla.
    '''
    import random 
    print('test begin')
    errors = 0
    for n in range(100):
        inputData = {
            'number':random.randint(0, 0xffffffff), 
            'side':'SELL', 
            'strategyId':random.randint(0, 255), 
            'contractId':random.randint(0, 0xffffffff), 
            'clientId':random.randint(0, 255)
        }
        idManager = OrderIdManager(inputData['clientId'])
        id = idManager.create_id(inputData['strategyId'], inputData['strategyId'], inputData['side'])  # inputData['number']
        output = idManager.unpack(id)
        #if inputData['number'] != output['number']:
        #    print('error en', inputData, 'number=', output['number'])
        #    errors += 1
        if inputData['side'] != output['side']:
            print('error en', inputData, 'side=', output['side'])
            errors += 1
        if inputData['strategyId'] != output['strategyId']:
            print('error en', inputData, 'strategyId=', output['strategyId'])
            errors += 1
        if inputData['clientId'] != output['clientId']:
            print('error en', inputData, 'clientId=', output['clientId'])
            errors += 1
    if errors == 0:
        print('test end, success')
    else:
        print('test end, with error')

#test()

