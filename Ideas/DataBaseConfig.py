import mysql.connector


class BBDDManager():
    cursor = None
    db_connection = None
    connection_succeed = False
    host = None
    username = None
    password = None
    db_name = None

    def __init__(self, host, username, db_name) -> None:
        print("Connecting to BBDD Server ...")
        self.host = host
        self.username = username
        self.db_name = db_name
        try:
            db_connection = mysql.connector.connect(
                            host=host,    
                            user=username         
                            )
            self.cursor = db_connection.cursor()        
            self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            self.cursor.execute(f"USE {db_name}")
            self.connection_succeed = True
            print("Connection Succesful")

            table_name = "OHLC_Data_IBKR"
            create_table_query = f"""
                                CREATE TABLE IF NOT EXISTS {table_name} (
                                    id INT AUTO_INCREMENT PRIMARY KEY,
                                    symbol VARCHAR(255) NOT NULL,
                                    datetime DATETIME NOT NULL,
                                    open DECIMAL(10, 2) NOT NULL,
                                    high DECIMAL(10, 2) NOT NULL,
                                    low DECIMAL(10, 2) NOT NULL,
                                    close DECIMAL(10, 2) NOT NULL,
                                    currency VARCHAR(255) NOT NULL
                                )
                                """
            
            self.cursor.execute(create_table_query)
            print(f"Tabla creada: {table_name}")
            
        except Exception as mistake:
            print("Error connecting with BBDD Server")
            print(mistake)


    def check_connection(self):
        print("Checking Connection")
        connection = mysql.connector.connect(
                host=self.host,
                user=self.username,
                database=self.db_name
        )
        if connection.is_connected():
            print("Connected to MySQL database")
            return True
        else:
            print("Connection to BBDD Server Failed")
            self.connection_succeed = False
            return False, None
    


    def insert_ohlc_data(self, table_name, symbol, datetime, open_price, high_price, low_price, close_price, currency): 
        try:
            connection = mysql.connector.connect(
            host=self.host,
            user=self.username,
            database=self.db_name
            )
            cursor = connection.cursor()
            sql = f"INSERT INTO {table_name} (symbol,datetime, open, high, low, close, currency) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            values = (symbol, datetime, open_price, high_price, low_price, close_price, currency)
            cursor.execute(sql, values)
            connection.commit()

            print("OHLC data inserted successfully.")
        except Exception as e:
            print(f"Error: {e}")

