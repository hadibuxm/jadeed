from django.test import TestCase
from dotenv import load_dotenv
import os
load_dotenv()
# Create your tests here.
import requests
secret = os.getenv("DEVIN_AI_SECRET")
print(secret)
url = "https://api.devin.ai/v1/sessions"

headers = {"Authorization": f"Bearer {secret}"}

response = requests.get(url, headers=headers)

print(response.json())


