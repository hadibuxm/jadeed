import requests

# Your DevinAI API key
DEVINAI_API_KEY = 'your_api_key_here'

# DevinAI API URL
DEVINAI_URL = 'https://api.devinai.com/v1/'
SESSION_URL = 'https://api.devin.ai/v1/sessions'
# Function to call the DevinAI API
def call_devinai_endpoint(endpoint, data):
    headers = {
        'Authorization': f'Bearer {DEVINAI_API_KEY}',
        'Content-Type': 'application/json',
    }
    
    url = f'{DEVINAI_URL}{endpoint}'
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 200:
        return response.json()  # Return the response from DevinAI
    else:
        return {"error": "Failed to get response", "status_code": response.status_code}

def get_sessions_from_devinai(limit=100, offset=0):
    headers = {
        'Authorization': f'Bearer {DEVINAI_API_KEY}',
        'Content-Type': 'application/json',
    }
    params = {
        'limit': limit,
        'offset': offset,
    }
    response = requests.get(SESSION_URL, headers=headers, params=params)
    print(f"session response: {response}")
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Failed to fetch sessions: {response.status_code}"}

def create_devin_session(prompt, title=None, idempotent=True, tags=None):
    headers = {
        'Authorization': f'Bearer {DEVINAI_API_KEY}',
        'Content-Type': 'application/json',
    }
    data = {
        'prompt': prompt,
        'title': title,
        'idempotent': idempotent,
        'tags': tags or [],
    }
    response = requests.post(SESSION_URL, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        return {'error': f'Failed to create session: {response.status_code}'}

def get_session_details_from_devinai(session_id):
    headers = {
        'Authorization': f'Bearer {DEVINAI_API_KEY}',
        'Content-Type': 'application/json',
    }
    url = f'{SESSION_URL}/{session_id}'
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()  # Return session details
    else:
        return {'error': f'Failed to fetch session details: {response.status_code}'}