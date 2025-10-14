from django.shortcuts import render
from .devinai_api import call_devinai_endpoint,get_sessions_from_devinai, create_devin_session,get_session_details_from_devinai
from .forms import DevinSessionForm

def devinai_integration(request):
    response = None

    if request.method == 'POST':
        # Get the input data from the form
        input_data = request.POST.get('input_data')
        
        # Prepare the data for the DevinAI API
        data = {'input_data': input_data}

        # Call the DevinAI API
        response = call_devinai_endpoint('your_endpoint_here', data)

    # Render the form page and pass the response to the template
    return render(request, 'devinai_form.html', {'response': response})

def list_sessions(request):
    limit = 100  # Number of sessions to retrieve per page
    offset = 0  # Starting point for pagination
    response = get_sessions_from_devinai(limit=limit, offset=offset)
    sessions = response.get('sessions', [])
    return render(request, 'list_sessions.html', {'sessions': sessions})

def create_session(request):
    if request.method == 'POST':
        form = DevinSessionForm(request.POST)
        if form.is_valid():
            prompt = form.cleaned_data['prompt']
            title = form.cleaned_data['title']
            tags = form.cleaned_data['tags'].split(',') if form.cleaned_data['tags'] else []
            response = create_devin_session(prompt, title, tags=tags)
            return render(request, 'session_created.html', {'response': response})
    else:
        form = DevinSessionForm()
    return render(request, 'create_session.html', {'form': form})

def retrieve_session(request, session_id):
    # Call the function to get session details from DevinAI
    response = get_session_details_from_devinai(session_id)
    
    if 'error' in response:
        return render(request, 'session_error.html', {'error': response['error']})
    
    # Render the session details page with the session data
    return render(request, 'session_details.html', {'session': response})