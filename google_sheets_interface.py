
'''
Crea un objeto para leer o escribir datos en una hoja de calculo Google Sheets.
Creado: 16-09-2023
Version de Python: 3.10'
'''
__version__ = '1.0'

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow,Flow
from google.auth.transport.requests import Request
import os
import pickle


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Este es el nombre del primer parametros de la tabla.
# Cada vez que el objeto lea un parametro con este nombre, va a asumir que se 
# ha empezado a leer una tabla. SI ya se estaba leyendo una tabla va a asumir 
# que la tabla anterior se termino y que ha comenzado otra tabla.
# Este sistema permite crear tablas con diferentes estructuras y longitudes
# de manera que cada estrategia puede tener su propia cantidad de parametros.
TABLE_BEGIN = 'strategy_id'


class GoogleSheetsInterface:
    
    def __init__(self, credentials, sheetID, token=None):
        '''
        Crea un objeto para leer o escribir datos en una hoja de calculo Google Sheets.

        Parametros:
        credentials: Ruta completa del fichero de credenciales de Google. 
                     Ejemplo 'C:/New Frontier/credentials.json'
        sheetID: Es el ID de la hoja de calculo de la quie se deben leer los datos.
                 Ejemplo '1JOe2rzWEkciQasrhjsVFVesUCMIe5BuQXaeRWD-0QV4'
        beginRow: Número de fila donde empieza a leer las tablas.
        beginColumn: Número de columna donde empieza a leer las tablas.
        token: Establece la ruta donde se debe guardar el fichero token de acceso a
            la hoja de calculo. Debe ser una ruta terminada en el simbolo '/'.
            Ejemplo 'C:/New Frontier/'
            Si no se especifica este parametro, por defecto el fichero de token
            sera guardado en el directorio actual del script.
        '''
        self.credentials = credentials
        self.sheetID = sheetID
        self.token = './token.pickle' if token is None else token


    def read_tables(self, page=None, beginColumn=1, beginRow=1, columns=2, rows=300):
        '''Lee las tablas de parametros desde la hoja actual de calculo Google Sheets'''
        return self.read_params_table(self.create_range(page, beginColumn, beginRow, columns, rows))


    def read_params_table(self, table):
        '''
        Lee las tablas de parametros desde la hoja actual de calculo Google Sheets
        
        Contexto: Se conecta a la hoja de calculo Google Sheets y lee en la pagina
        indicada las tablas que se encuentran en el rango especificado.
        Las tablas estan compuesta por dos columnas sin cabeceras.
        La primera columna de las tablas de la hoja de calculo deben contener los nombres
        de las variables y la segunda columna debe contener los valores. Los nombres
        de variables de la primera columna de la tabla, deben empezar con caracteres
        alfabeticos. 

        table: Es la pagina y el rango de celdas donde esta la tabla dentro de la primera hoja.
               Ejemplo 'Estrategias!A1:B7' donde Estrategias es el nombre de la pagina, A es la 
               primera columna de la tabla, B es la ultima columna de la tabla. Se empieza a 
               leer en la fila 1 y se termina de leer en la fila 7.
        return: Devuelve una lista de diccionarios, donde cada uno contiene la tabla 
                de parametros como una coleccion llave:valor. 
                Si ocurre un error, devuelve None.
                Las llaves de los pares del diccionario seran nombradas con los nombres de
                la primera columna de la tabla de la oja de calculo, pero los espacios 
                seran sustituidos por guion bajo '_'. No se tendrán en cuenta los espacios
                que están al inicio o al final.
        '''
        try:
            creds = None
            if os.path.exists(self.token):
                with open(self.token, 'rb') as token:
                    creds = pickle.load(token)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials, SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(self.token, 'wb') as token:
                    pickle.dump(creds, token)
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()
            sheetExecuteResult = sheet.values().get(spreadsheetId=self.sheetID, range=table).execute()
            tableData = sheetExecuteResult.get('values', [])        

            tables = []   
            parametersAsDictionary = {}
            for param in tableData:
                try:
                    paramName = self.create_param_name(param[0])
                    if paramName == TABLE_BEGIN and len(parametersAsDictionary) > 0:
                        tables.append(parametersAsDictionary)
                        parametersAsDictionary = {}
                    if len(param) > 1:
                        parametersAsDictionary[paramName] = param[1]
                    else:
                        parametersAsDictionary[paramName] = None
                except:
                    continue
            if len(parametersAsDictionary) > 0:
                tables.append(parametersAsDictionary)
            return tables    
        except Exception as err:
            return None


    def create_param_name(self, inputString):
        '''
        Recibe una cadena de caracteres de una o mas palabras y los
        unifica para conformar un nombre de parametro sin espacios.
        '''
        return inputString.strip().replace(' ', '_')


    def string_to_float(self, inputString):
        '''
        Convierte un float de Google Sheet en un float de Python.
        Recibe una cadena de caracteres que representa un numero floatante,
        que utiliza como separador de decimales una coma en vez de un punto.
        Devuelve un float con el valor representado por la cadena o devuelve
        None si ocurre un error.
        '''
        try:
            return float(inputString.replace(',', '.'))
        except:
            return None


    def create_range(self, page=None, beginColumn=1, beginRow=1, columns=2, rows=300):
        '''
        Devuelve un rango de celdas como cadena
        
        Parametros
        beginColumn:  Número de columna (mayor que cero) donde comienza la tabla en la hoja de cálculo.
        beginRow: Número de fila (mayor que cero) donde comienza la tabla en la hoja de cálculo.
        columns: Cantidad de columnas que tiene la tabla.
        rows: Cantidad de filas que tiene la tabla.
        
        Resultado
        Devuelve el rango de celdas correspondientes en la hoja de cálculo
        de Google Sheets. Ejemplo "A2:C8"
        Si alguno de los valores es menor o igual que cero, devuelve None.
        Si beginColumn+columns >= 130, devuelve None, pues solo se permite hasta la columna 130.
        '''
        columnsLabels = [
            'A','B','C','D','E','F','G','H','I','J','K','L','M',
            'N','O','P','Q','R','S','T','U','V','W','X','Y','Z',
            'AA','AB','AC','AD','AE','AF','AG','AH','AI','AJ','AK','AL','AM',
            'AN','AO','AP','AQ','AR','AS','AT','AU','AV','AW','AX','AY','AZ',
            'BA','BB','BC','BD','BE','BF','BG','BH','BI','BJ','BK','BL','BM',
            'BN','BO','BP','BQ','BR','BS','BT','BU','BV','BW','BX','BY','BZ',
            'CA','CB','CC','CD','CE','CF','CG','CH','CI','CJ','CK','CL','CM',
            'CN','CO','CP','CQ','CR','CS','CT','CU','CV','CW','CX','CY','CZ',
            'CA','CB','CC','CD','CE','CF','CG','CH','CI','CJ','CK','CL','CM',
            'CN','CO','CP','CQ','CR','CS','CT','CU','CV','CW','CX','CY','CZ'
        ]
        if beginRow > 0 and beginColumn > 0 and rows > 0 and columns > 0 and beginColumn + columns < len(columnsLabels):
            beginColumn -= 1
            page = '' if page is None else page+'!'
            return '{}{}:{}{}'.format(
                str(columnsLabels[beginColumn]), 
                int(beginRow), 
                str(columnsLabels[beginColumn + columns - 1]), 
                int(beginRow + rows - 1)
            )
        else:
            return None


    def is_active(self, value): 
        if value == 'SI':
            return True
        elif value == 'NO':
            return False
        else:
            return False




def test():    
    '''Para probar el funcionamiento de esta libreria'''
    import json
    CREDENTIALS = 'C:/New Frontier/credentials.json'
    DOCUMENT_ID = '1JOe2rzWEkciQasrhjsVFVesUCMIe5BuQXaeRWD-0QV4'
    multitables = GoogleSheetsInterface(CREDENTIALS, DOCUMENT_ID)
    result = multitables.read_tables('Estrategias')
    print(json.dumps(result, indent=2))

#test()



