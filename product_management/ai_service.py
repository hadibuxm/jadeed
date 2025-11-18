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

    def __init__(self, workflow_step_or_product_step):
        """Initialize with either a WorkflowStep or ProductStep."""
        self.step = workflow_step_or_product_step
        # For backward compatibility, keep workflow_step reference
        if hasattr(workflow_step_or_product_step, 'step_type'):
            self.workflow_step = workflow_step_or_product_step
        else:
            self.workflow_step = None
        self.api_key = os.environ.get('OPENAI_API_KEY', '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')
        self.api_url = 'https://api.openai.com/v1/chat/completions'

    def get_system_prompt(self):
        """Get the system prompt based on the workflow step type."""
        # Check if this is a ProductStep
        if hasattr(self.step, 'layer'):  # ProductStep has layer attribute
            return self._get_product_step_prompt()

        # Original WorkflowStep prompts
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
        return prompts.get(self.step.step_type, prompts['vision'])

    def _get_product_step_prompt(self):
        """Get the system prompt for ProductStep based on step type."""
        product_step_prompts = {
            # STRATEGIC / DISCOVERY LAYER
            'market_context': """You are a product management AI assistant helping with Market Context analysis.
Guide the user to validate alignment with:
- Market trends and dynamics
- Competitive positioning and landscape
- Customer segments and target markets
- Market opportunities and threats

Help them build a comprehensive understanding of the market context for their product.""",

            'discovery_research': """You are a product management AI assistant helping with Discovery Research.
Guide the user through:
- User interviews and insights
- Data analysis methodologies
- Support ticket mining
- Customer feedback analysis
- Research synthesis and findings

Help them gather and analyze qualitative and quantitative research.""",

            'problem_definition': """You are a product management AI assistant helping define the Problem.
Guide the user to articulate:
- Core pain points and challenges
- Affected user personas
- Impact and severity of the problem
- Current workarounds or alternatives

Help them clearly define the problem worth solving.""",

            'hypothesis_business_case': """You are a product management AI assistant helping build the Hypothesis & Business Case.
Guide the user to define:
- Hypothesis statement
- Estimated impact (revenue, cost savings, engagement, NPS)
- Estimated effort (resourcing, time, complexity)
- Strategic alignment (OKRs, company goals, roadmap themes)
- Expected ROI and business value

Help them articulate why this is worth doing and what success looks like.""",

            'success_metrics': """You are a product management AI assistant helping define Success Metrics & Guardrails.
Guide the user to establish:
- Leading indicators (early signals of success)
- Lagging indicators (outcome measures)
- North Star metric
- Guardrail metrics (what should NOT change)
- Measurement methodology and tracking

Help them define measurable success criteria.""",

            'stakeholder_buyin': """You are a product management AI assistant helping secure Stakeholder Buy-In.
Guide the user through:
- Executive alignment strategies
- Budget approval requirements
- Resource allocation needs
- Communication plan
- Risk mitigation and concerns

Help them prepare for stakeholder engagement and approval.""",

            # TACTICAL / BUILD LAYER
            'ideation_design': """You are a product management AI assistant helping with Ideation & Solution Design.
Guide the user through:
- Brainstorming potential solutions
- Design thinking approaches
- Collaboration with design team
- Solution alternatives and tradeoffs
- Conceptual designs and sketches

Help them co-create innovative solutions with design.""",

            'prd_requirements': """You are a product management AI assistant helping create PRD / Requirements Definition.
Guide the user to capture:
- Problem statement
- Goals and objectives
- User stories and scenarios
- Acceptance criteria
- Constraints and dependencies
- Technical requirements

Help them create a comprehensive PRD.""",

            'design_prototypes': """You are a product management AI assistant helping with Design Prototypes & Validation.
Guide the user through:
- Usability testing plans
- Heuristic reviews
- Mock feedback loops
- Prototype iterations
- Design validation criteria

Help them validate designs with users.""",

            'development': """You are a product management AI assistant helping with Development.
Guide the user through:
- Development approach and methodology
- Sprint planning and execution
- Technical architecture decisions
- Progress tracking
- Blocker resolution

Help them manage the development process effectively.""",

            'qa_uat': """You are a product management AI assistant helping with QA, UAT, and Staging.
Guide the user through:
- Cross-functional testing strategies
- Bug triage and prioritization
- Regression testing
- User acceptance testing
- Staging environment validation

Help them ensure quality before release.""",

            # RELEASE / IMPACT LAYER
            'gtm_planning': """You are a product management AI assistant helping with Go-to-Market Planning.
Guide the user to develop:
- Launch strategy and timeline
- Communication plan
- Internal training materials
- Marketing materials
- Customer communication
- Support preparation

Help them plan a successful product launch.""",

            'release_execution': """You are a product management AI assistant helping with Release Execution.
Guide the user through:
- Phased rollout strategies
- A/B testing setup
- Real-time data monitoring
- Incident response plan
- Feature flags and controls

Help them execute a controlled, monitored release.""",

            'post_launch': """You are a product management AI assistant helping with Post-Launch Validation.
Guide the user to:
- Confirm success metrics
- Survey users for feedback
- Monitor performance and stability
- Analyze adoption rates
- Identify issues and opportunities

Help them validate the launch impact.""",

            'retrospective': """You are a product management AI assistant helping with Retrospective & Learnings.
Guide the user to document:
- Outcomes vs. hypothesis comparison
- What went well
- What could be improved
- Key learnings and insights
- Actions for future iterations

Help them capture valuable learnings for continuous improvement.""",
        }
        return product_step_prompts.get(self.step.step_type, product_step_prompts['market_context'])

    def send_message(self, user_message):
        """Send a message to OpenAI and get a response."""
        if not self.api_key:
            return {
                'success': False,
                'error': 'OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.'
            }

        # Add user message to conversation history
        self.step.add_message('user', user_message)

        # Build messages array for OpenAI
        messages = [
            {'role': 'system', 'content': self.get_system_prompt()}
        ]
        messages.extend(self.step.get_conversation_context())

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
            self.step.add_message('assistant', assistant_message)

            return {
                'success': True,
                'message': assistant_message,
                'conversation_id': self.step.id
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
        self.step.add_message('user', user_message)

        # Build messages array for OpenAI
        messages = [
            {'role': 'system', 'content': self.get_system_prompt()}
        ]
        messages.extend(self.step.get_conversation_context())

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
                self.step.add_message('assistant', full_message)
                yield f'data: {json.dumps({"done": True, "conversation_id": self.step.id})}\n\n'

        except requests.RequestException as e:
            logger.error(f"OpenAI API error: {str(e)}")
            yield f'data: {json.dumps({"error": f"Error communicating with OpenAI: {str(e)}"})}\n\n'
        except Exception as e:
            logger.error(f"Unexpected error in AI service: {str(e)}")
            yield f'data: {json.dumps({"error": f"Unexpected error: {str(e)}"})}\n\n'

    def generate_readme(self):
        """Generate README/document content from the conversation history."""
        if not self.api_key:
            return {
                'success': False,
                'error': 'OpenAI API key not configured.'
            }

        if not self.step.conversation_history:
            return {
                'success': False,
                'error': 'No conversation history to generate document from.'
            }

        # Create a prompt to summarize the conversation into README format
        step_display = self.step.get_step_type_display()
        summary_prompt = f"""Based on the conversation above about this {step_display},
create a comprehensive document that captures:

1. Overview and summary
2. Key decisions and conclusions
3. Important details discussed
4. Action items or next steps

Format the README in proper Markdown with appropriate headers, lists, and formatting.
The README should be clear, professional, and useful as project documentation."""

        messages = [
            {'role': 'system', 'content': 'You are a technical writer creating project documentation.'}
        ]
        messages.extend(self.step.get_conversation_context())
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

            # Save content to step (works for both WorkflowStep and ProductStep)
            if hasattr(self.step, 'readme_content'):
                self.step.readme_content = readme_content
                self.step.readme_generated_at = timezone.now()
            elif hasattr(self.step, 'document_content'):
                self.step.document_content = readme_content
                self.step.document_generated_at = timezone.now()
            self.step.save()

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
        content = getattr(self.step, 'readme_content', None) or getattr(self.step, 'document_content', None)
        if not content:
            return {
                'success': False,
                'error': 'No document content to save.'
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
            content_bytes = content.encode('utf-8')
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')

            data = {
                'message': f'Add/Update {self.step.get_step_type_display()} Document: {self.step.title}',
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
        """Construct the file path for the document based on hierarchy."""
        path_parts = ['product_discovery']

        # Check if this is a ProductStep
        if hasattr(self.step, 'layer'):
            # ProductStep - create path based on product hierarchy
            product = self.step.product
            workflow_step = product.workflow_step

            # Build path from workflow hierarchy
            current = workflow_step
            hierarchy = []
            while current:
                hierarchy.insert(0, current)
                current = current.parent_step

            for step in hierarchy:
                safe_title = step.title.lower().replace(' ', '_').replace('/', '_')
                path_parts.append(f"{step.step_type}_{safe_title}")

            # Add product step
            safe_title = self.step.title.lower().replace(' ', '_').replace('/', '_')
            path_parts.append(f"{self.step.step_type}_{safe_title}")
        else:
            # WorkflowStep - original logic
            current = self.step
            hierarchy = []
            while current:
                hierarchy.insert(0, current)
                current = current.parent_step

            for step in hierarchy:
                safe_title = step.title.lower().replace(' ', '_').replace('/', '_')
                path_parts.append(f"{step.step_type}_{safe_title}")

        path_parts.append('README.md')
        return '/'.join(path_parts)
