
import json
import time
import regex 
import logging
from core import Core
from ib_insync import *
from datetime import datetime

from logging.handlers import TimedRotatingFileHandler

# Identificador del google sheet Desarrollo (BotsIBKR): 
#   '1JOe2rzWEkciQasrhjsVFVesUCMIe5BuQXaeRWD-0QV4'
# Identificador del google sheet Paper (BotsIBKR_Paper):
#   '14PfzhKAYBoM9wPeHl6CYPI7G7hmNU47PLADXH6Bh_-g'


# Aquí se ponen todos los parámetros que definen el funcionamiento básico.
CONFIGURATION = {
    'client_tws': 19,
    'reconnection_seconds': 100,        # Tiempo para reintentar reconectar con el API.
    'actualize_status_seconds': 5,      # Actualizacion de la configuracion del google sheets.
    'max_conection_loss_seconds': 15,   # Tiempo maximo que se puede estar sin coneccion para no reiniciar la estrategia.
    'debug_mode': True,                 # Poner en False para que salgan menos lineas en el CMD.

    'google_sheets_document_id': '1JOe2rzWEkciQasrhjsVFVesUCMIe5BuQXaeRWD-0QV4', 
    'google_sheets_credentials': 'C:/New Frontier/credentials.json',

    'dashboard_document_id': '1JOe2rzWEkciQasrhjsVFVesUCMIe5BuQXaeRWD-0QV4',   
    'dashboard_credentials': 'C:/New Frontier/credentials.json',
    'dashboard_realtime_level': 0,

    'telegram_level': 0,
    'telegram_token': '6092797629:AAGEIBIYhrprAQJkeiOTs3YOuwzg0pK-Jqg',
    'telegram_chat_id': '-928805835',
}

    

def create_logger(name, fileName, filesCount, debugMode):
    '''Prepara la configuracion del logging para guardar mensajes en fichero.'''
    LOG_FORMAT = '%(asctime)s %(levelname)s %(module)s:%(funcName)s:%(lineno)04d - %(message)s'
    handler = TimedRotatingFileHandler(fileName, when="midnight", backupCount=filesCount) 
    handler.setLevel(logging.DEBUG if debugMode else logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)
    handler.suffix = "%Y%m%d"       # Este es el sufijo del nombre de ficehro.
    handler.extMatch = regex.compile(r"^\d{8}$")   
    log = logging.getLogger(name)
    logging.root.setLevel(logging.NOTSET)
    log.addHandler(handler)
    return log




def _connect_to_brocker():
    ''' Intenta conectarse al broker y solo sale de la funcion cuando se logra. '''
    global log
    global core
    global configurationBase
    core.disconnect()
    currentReconnect = 1
    while True:
        try:
            print('Intentando conectar...')
            log.info('Intentando conectar...')
            conection_loss_seconds = time.time() - core.last_connection_time
            core.connect("127.0.0.1", port=7497, clientId=configurationBase['client_tws'], timeout=5)
            if core.isConnected():
                text = 'BOT CONECTADO! Se ha logrado conectar'
                print('{} {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), text))
                log.info(text)
                core.last_connection_time = time.time()
                if conection_loss_seconds > configurationBase['max_conection_loss_seconds']:  
                    text = 'BOT REINICIANDO ESTRATEGIAS. Estuvo desconectado {} segundos.'.format(round(conection_loss_seconds))
                    print(text)
                    log.info(text)
                    core.cancel_all_orders()
                    core.parameters.reset()        # Elimina historial de estrategias para lanzarlas nuevamente.
                break
        except Exception as e:
            text = 'No se pudo conectar en el intento {}. Próximo intento en {} segundos.'.format(
                currentReconnect, configurationBase['reconnection_seconds']
            )
            print(text)
            log.error(text)
            currentReconnect += 1
            core.sleep(configurationBase['reconnection_seconds'])        
    

def _onDisconnected():
    global log
    '''Si se desconecta el Grid Bot Multiple, lo informa y vuelve a intentar la conexion.'''
    text = 'BOT DESCONECTADO! Se ha perdido la conexión...'
    print('{} {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), text))
    log.critical(text)
    core.sleep(configurationBase['reconnection_seconds'])
    _connect_to_brocker()       # Intenta reconectar.

    
def _onError(reqId, errorCode, errorString, contract):
    '''Pone en el log los errores que reporta el TWS por su API.'''
    global log
    log.error('code {}: {}'.format(errorCode, errorString))


def update_configuration(configFilePath):
    ''' Loads a configuration file given in the parameter config_file_path'''
    global log
    global configurationBase
    try:
        with open(configFilePath, 'r') as file:
            configData = json.load(file)
        configurationBase.update(configData)    # Merge the loaded JSON with the existing global configuration
        text = f'Global configuration updated successfully from: "{configFilePath}"'
        print(text)
        log.error(text)
    except FileNotFoundError:
        text = f'The configuration file does not exist: {configFilePath}'
        print(text)   
        log.error(text)         
    except Exception as e:
        text = f'Error updating configuration file: {e}'
        print(text)   
        log.error(text) 



# Crea el objeto Grid Bot Multiple que ejecuta multiples estrategias a la vez.
configurationBase = CONFIGURATION
log = create_logger('grid', './logs/grid_multiple.log', 7, configurationBase['debug_mode'])
print('{} BOT INICIADO! Se ha creado el Grid Bot Multiple'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
log.info('BOT INICIADO! Se ha creado el Grid Bot Multiple')
update_configuration("config.json") 
core = Core(configurationBase)        
util.patchAsyncio()
print('Intentando conectar...')
log.info('Intentando conectar...')        
_connect_to_brocker()
core.cancel_all_orders()
core.disconnectedEvent += _onDisconnected
core.errorEvent += _onError
core.execDetailsEvent += core.onExecDetailsEvent
core.set_actualize_bot_status()
core.run()

