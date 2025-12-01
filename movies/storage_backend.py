# # myapp/storage_backends.py
# import requests
# from django.core.files.storage import Storage
# from django.conf import settings
# from django.core.files.base import ContentFile

# class GoFileStorage(Storage):
#     # ... (implement necessary methods like _save, _open, exists, url, etc.)
#     # The core logic is in the _save method.

#     def _save(self, name, content):
#         # 1. Get the best server for upload from GoFile API
#         server_response = requests.get("api.gofile.io").json()
#         if server_response['status'] != 'ok':
#             raise Exception("Could not get GoFile server")
#         server = server_response['data']['servers'][0]['name']
#         upload_url = f"https://upload.gofile.io/uploadfile"

#         # 2. Upload the file
#         files = {'file': (name, content.file.read())}
#         upload_response = requests.post(upload_url, files=files).json()

#         if upload_response['status'] == 'ok':
#             # 3. Extract the download link/URL
#             download_url = upload_response['data']['downloadPage']
#             # Store this URL in the model instance (this part needs to be handled in the model's save method or signal)
#             # Note: The _save method returns the file path used internally by Django
#             return name # return the name/path
#         else:
#             raise Exception(f"GoFile upload failed: {upload_response['status']}")

#     def url(self, name):
#         # This should ideally return the stored GoFile URL
#         # Accessing the model instance here is tricky. 
#         # The direct URL should be stored in a separate model field after a successful upload.
#         return self.gofile_url if hasattr(self, 'gofile_url') else 'Temporary URL'

#     # ... (other required methods: _open, exists, delete, listdir, size, etc.)
