import mysql.connector
import logging


class BBDDManager():
    cursor = None
    db_connection = None
    connection_succeed = False
    host = None
    username = None
    password = None
    db_name = None

    def __init__(self, host, username, db_name) -> None:
        logging.info("Connecting to BBDD Server ...")
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
            logging.info("Connection Succesful")

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
            logging.info(f"Tabla creada: {table_name}")
            
        except  mysql.connector.Error as e:
            logging.info("Error connecting with BBDD Server")
            logging.info(e)
    

    """
    Function: Insert OHCL DATA

        # This function is used to insert OHLC (Open, High, Low, Close) data for a financial symbol into a MySQL database table.
        # Inputs:
        #   - table_name: The name of the database table where the data should be inserted.
        #   - symbol: The financial symbol for which the OHLC data is recorded.
        #   - datetime: The date and time of the OHLC data entry.
        #   - open_price: The opening price for the symbol at the specified datetime.
        #   - high_price: The highest price for the symbol within the specified datetime.
        #   - low_price: The lowest price for the symbol within the specified datetime.
        #   - close_price: The closing price for the symbol at the specified datetime.
        #   - currency: The currency in which the prices are recorded.

        # Outputs:
        #   - If the data insertion is successful, the function prints a success message: "OHLC data inserted successfully."
        #   - If any errors occur during the data insertion process, the function prints an error message with details of the error.


    """
    def insert_ohlc_data(self, table_name, symbol, datetime, open_price, high_price, low_price, close_price, currency):  
        connection = mysql.connector.connect(
            host=self.host,
            user=self.username,
            database=self.db_name
            )
        if not connection:
            return
        try:
            with connection:
                cursor = connection.cursor()
                sql = f"INSERT INTO {table_name} (symbol,datetime, open, high, low, close, currency) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                values = (symbol, datetime, open_price, high_price, low_price, close_price, currency)
                cursor.execute(sql, values)
                connection.commit()
                logging.info("OHLC data inserted successfully.")
        except mysql.connector.Error as e:
            logging.error(f"Error inserting OHLC data: {e}")
                
