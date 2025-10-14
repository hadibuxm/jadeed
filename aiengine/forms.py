from django import forms

class DevinSessionForm(forms.Form):
    prompt = forms.CharField(widget=forms.Textarea, label='Task Description')
    title = forms.CharField(max_length=255, required=False, label='Session Title')
    tags = forms.CharField(max_length=255, required=False, label='Tags (comma-separated)')