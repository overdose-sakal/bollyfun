import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BF.settings')
django.setup()

import requests
from django.conf import settings

def test_shrink_api():
    api_key = settings.SHRINK_EARN_API_KEY
    test_url = "https://www.google.com"
    
    api_url = "https://shrinkearn.com/api"
    params = {
        'api': api_key,
        'url': test_url
    }
    
    print(f"Testing ShrinkEarn API...")
    print(f"API Key: {api_key[:10]}...")
    print(f"Test URL: {test_url}")
    
    try:
        response = requests.get(api_url, params=params, timeout=10)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print(f"\n✅ SUCCESS!")
                print(f"Shortened URL: {data.get('shortenedUrl')}")
            else:
                print(f"\n❌ API returned error: {data}")
        else:
            print(f"\n❌ HTTP Error: {response.status_code}")
    
    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == '__main__':
    test_shrink_api()