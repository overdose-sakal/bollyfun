# movies/telegram_utils.py

import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class TelegramFileManager:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.channel_id = settings.TELEGRAM_CHANNEL_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def upload_file(self, file_path, caption=""):
        """
        Uploads a document to the private Telegram channel.
        
        Returns: A tuple (file_id, message_id) if successful, 
                 or (None, None) if the upload fails.
        """
        url = f"{self.base_url}/sendDocument"
        
        try:
            with open(file_path, 'rb') as file:
                files = {'document': file}
                data = {
                    'chat_id': self.channel_id,
                    'caption': caption
                }
                
                response = requests.post(url, files=files, data=data)
                result = response.json()
                
                if result.get('ok'):
                    file_id = result['result']['document']['file_id']
                    message_id = result['result']['message_id']
                    
                    logger.info(f"File uploaded successfully. File ID: {file_id}, Message ID: {message_id}")
                    return file_id, message_id
                else:
                    logger.error(f"Upload failed: {result.get('description')}")
                    return None, None
                    
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            return None, None

    
    def get_file_url(self, file_id):
        """
        Get file download URL from Telegram (only works for files < 20MB)
        Returns: download URL if successful, None if failed
        """
        url = f"{self.base_url}/getFile"
        
        try:
            response = requests.post(url, data={'file_id': file_id})
            result = response.json()
            
            if result.get('ok'):
                file_path = result['result']['file_path']
                download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                return download_url
            else:
                logger.error(f"Get file failed: {result.get('description')}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting file URL: {str(e)}")
            return None

    def forward_message(self, target_chat_id, message_id):
        """
        Forwards a message from the source channel to the target chat ID (user).
        Returns True if successful, False otherwise.
        """
        url = f"{self.base_url}/forwardMessage"
        
        try:
            data = {
                'chat_id': target_chat_id,
                'from_chat_id': self.channel_id,
                'message_id': message_id
            }
            
            response = requests.post(url, data=data)
            result = response.json()
            
            if result.get('ok'):
                logger.info(f"Message ID {message_id} successfully forwarded to {target_chat_id}")
                return True
            else:
                logger.error(f"Forward message failed: {result.get('description')}")
                return False
                
        except Exception as e:
            logger.error(f"Error forwarding message: {str(e)}")
            return False
            
    def delete_file(self, message_id):
        """
        Delete a file from the channel
        """
        url = f"{self.base_url}/deleteMessage"
        
        try:
            data = {
                'chat_id': self.channel_id,
                'message_id': message_id
            }
            
            response = requests.post(url, data=data)
            result = response.json()
            
            return result.get('ok', False)
            
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False