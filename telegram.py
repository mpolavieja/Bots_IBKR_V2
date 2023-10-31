
import requests

def send_to_telegram(message, configuration):
    if 'telegram_level' in configuration:
        if configuration['telegram_level'] == 1:
            try:
                response = requests.post(
                    'https://api.telegram.org/bot{}/sendMessage'.format(configuration["telegram_token"]), 
                    json={
                        'chat_id': configuration["telegram_chat_id"], 
                        'text': message
                    }
                )
                return response            
            except Exception as e:
                print("Error enviando mensaje por Telegram. Exception:", str(e))



