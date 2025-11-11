import os
import json
import requests
import logging
from datetime import datetime
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class ProductDiscoveryAI:
    """AI service for product discovery conversations using OpenAI."""

    def __init__(self, workflow_step):
        self.workflow_step = workflow_step
        self.api_key = os.environ.get('OPENAI_API_KEY', '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')
        self.api_url = 'https://api.openai.com/v1/chat/completions'

    def get_system_prompt(self):
        """Get the system prompt based on the workflow step type."""
        prompts = {
            'vision': """You are a product management AI assistant helping to define a product vision.
Guide the user to articulate:
- Strategic goals and objectives
- Target audience and market
- Success metrics and KPIs
- Long-term vision and impact

Ask clarifying questions and help refine their vision into a clear, actionable statement.""",

            'initiative': """You are a product management AI assistant helping to define an initiative.
Guide the user to articulate:
- Specific objectives that support the vision
- Key results (OKRs)
- Timeline and milestones
- Resources needed

Help them break down the vision into actionable initiatives.""",

            'portfolio': """You are a product management AI assistant helping to define a product portfolio.
Guide the user to articulate:
- Scope of the portfolio
- Product mix and strategy
- Resource allocation across products
- Dependencies and priorities

Help them organize products that work together toward the initiative.""",

            'product': """You are a product management AI assistant helping to define a product.
Guide the user to articulate:
- Value proposition
- User personas and target users
- Market analysis and competition
- Core capabilities and features

Help them clearly define what the product is and who it serves.""",

            'feature': """You are a product management AI assistant helping to define a feature.
Guide the user to articulate:
- User story (As a... I want... So that...)
- Acceptance criteria
- Priority and dependencies
- Technical considerations

Help them create a well-defined, implementable feature specification.""",
        }
        return prompts.get(self.workflow_step.step_type, prompts['vision'])

    def send_message(self, user_message):
        """Send a message to OpenAI and get a response."""
        if not self.api_key:
            return {
                'success': False,
                'error': 'OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.'
            }

        # Add user message to conversation history
        self.workflow_step.add_message('user', user_message)

        # Build messages array for OpenAI
        messages = [
            {'role': 'system', 'content': self.get_system_prompt()}
        ]
        messages.extend(self.workflow_step.get_conversation_context())

        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }

            data = {
                'model': 'gpt-4',
                'messages': messages,
                'temperature': 0.7,
                'max_tokens': 1000,
            }

            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()

            assistant_message = result['choices'][0]['message']['content']

            # Add assistant message to conversation history
            self.workflow_step.add_message('assistant', assistant_message)

            return {
                'success': True,
                'message': assistant_message,
                'conversation_id': self.workflow_step.id
            }

        except requests.RequestException as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return {
                'success': False,
                'error': f'Error communicating with OpenAI: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error in AI service: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }

    def send_message_stream(self, user_message):
        """Send a message to OpenAI and stream the response."""
        if not self.api_key:
            yield 'data: {"error": "OpenAI API key not configured"}\n\n'
            return

        # Add user message to conversation history
        self.workflow_step.add_message('user', user_message)

        # Build messages array for OpenAI
        messages = [
            {'role': 'system', 'content': self.get_system_prompt()}
        ]
        messages.extend(self.workflow_step.get_conversation_context())

        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }

            data = {
                'model': 'gpt-4',
                'messages': messages,
                'temperature': 0.7,
                'max_tokens': 1000,
                'stream': True,
            }

            response = requests.post(self.api_url, headers=headers, json=data, stream=True, timeout=60)
            response.raise_for_status()

            full_message = ''
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str == '[DONE]':
                            break

                        try:
                            chunk_data = json.loads(data_str)
                            if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                delta = chunk_data['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    full_message += content
                                    yield f'data: {json.dumps({"content": content})}\n\n'
                        except json.JSONDecodeError:
                            continue

            # Save the complete message to conversation history
            if full_message:
                self.workflow_step.add_message('assistant', full_message)
                yield f'data: {json.dumps({"done": True, "conversation_id": self.workflow_step.id})}\n\n'

        except requests.RequestException as e:
            logger.error(f"OpenAI API error: {str(e)}")
            yield f'data: {json.dumps({"error": f"Error communicating with OpenAI: {str(e)}"})}\n\n'
        except Exception as e:
            logger.error(f"Unexpected error in AI service: {str(e)}")
            yield f'data: {json.dumps({"error": f"Unexpected error: {str(e)}"})}\n\n'

    def generate_readme(self):
        """Generate README content from the conversation history."""
        if not self.api_key:
            return {
                'success': False,
                'error': 'OpenAI API key not configured.'
            }

        if not self.workflow_step.conversation_history:
            return {
                'success': False,
                'error': 'No conversation history to generate README from.'
            }

        # Create a prompt to summarize the conversation into README format
        summary_prompt = f"""Based on the conversation above about this {self.workflow_step.get_step_type_display()},
create a comprehensive README document that captures:

1. Overview and summary
2. Key decisions and conclusions
3. Important details discussed
4. Action items or next steps

Format the README in proper Markdown with appropriate headers, lists, and formatting.
The README should be clear, professional, and useful as project documentation."""

        messages = [
            {'role': 'system', 'content': 'You are a technical writer creating project documentation.'}
        ]
        messages.extend(self.workflow_step.get_conversation_context())
        messages.append({'role': 'user', 'content': summary_prompt})

        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }

            data = {
                'model': 'gpt-4',
                'messages': messages,
                'temperature': 0.5,
                'max_tokens': 2000,
            }

            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()

            readme_content = result['choices'][0]['message']['content']

            # Save README to workflow step
            self.workflow_step.readme_content = readme_content
            self.workflow_step.readme_generated_at = timezone.now()
            self.workflow_step.save()

            return {
                'success': True,
                'readme_content': readme_content
            }

        except requests.RequestException as e:
            logger.error(f"OpenAI API error generating README: {str(e)}")
            return {
                'success': False,
                'error': f'Error generating README: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error generating README: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }

    def save_readme_to_github(self, github_connection, repository):
        """Save the generated README to GitHub repository."""
        if not self.workflow_step.readme_content:
            return {
                'success': False,
                'error': 'No README content to save.'
            }

        try:
            # Construct file path based on workflow hierarchy
            file_path = self._construct_readme_path()

            # GitHub API endpoint for creating/updating files
            api_url = f'https://api.github.com/repos/{repository.full_name}/contents/{file_path}'

            headers = {
                'Authorization': f'Bearer {github_connection.access_token}',
                'Accept': 'application/vnd.github.v3+json',
            }

            # Check if file exists first
            existing_file = None
            try:
                check_response = requests.get(api_url, headers=headers)
                if check_response.status_code == 200:
                    existing_file = check_response.json()
            except:
                pass

            # Prepare content (base64 encoded)
            import base64
            content_bytes = self.workflow_step.readme_content.encode('utf-8')
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')

            data = {
                'message': f'Add/Update {self.workflow_step.get_step_type_display()} README: {self.workflow_step.title}',
                'content': content_base64,
                'branch': repository.default_branch,
            }

            if existing_file:
                data['sha'] = existing_file['sha']

            response = requests.put(api_url, headers=headers, json=data)
            response.raise_for_status()

            return {
                'success': True,
                'file_path': file_path,
                'url': response.json().get('content', {}).get('html_url', '')
            }

        except requests.RequestException as e:
            logger.error(f"GitHub API error saving README: {str(e)}")
            return {
                'success': False,
                'error': f'Error saving to GitHub: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error saving README to GitHub: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }

    def _construct_readme_path(self):
        """Construct the file path for the README based on workflow hierarchy."""
        path_parts = ['product_discovery']

        # Build path from parent hierarchy
        current = self.workflow_step
        hierarchy = []
        while current:
            hierarchy.insert(0, current)
            current = current.parent_step

        # Create path: product_discovery/vision/initiative/portfolio/product/feature/README.md
        for step in hierarchy:
            safe_title = step.title.lower().replace(' ', '_').replace('/', '_')
            path_parts.append(f"{step.step_type}_{safe_title}")

        path_parts.append('README.md')
        return '/'.join(path_parts)
