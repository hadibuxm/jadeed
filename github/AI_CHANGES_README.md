# AI-Powered Code Changes Feature

This feature allows users to request code changes in natural language, and the system will automatically:
1. Analyze the request using OpenAI GPT-4
2. Clone the repository locally
3. Apply the changes
4. Create a new branch
5. Push the changes to GitHub

## Setup Instructions

### 1. Install Required Dependencies

```bash
pip install openai
```

### 2. Configure Environment Variables

Add the following to your `.env` file:

```bash
# OpenAI API Key (required)
OPENAI_API_KEY=your_openai_api_key_here

# GitHub OAuth Credentials (already configured)
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
```

### 3. Obtain API Keys

#### OpenAI API Key:
1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key to your `.env` file

#### GitHub OAuth App (if not already set up):
1. Go to GitHub Settings > Developer settings > OAuth Apps
2. Click "New OAuth App"
3. Fill in the details:
   - Application name: Jadeed
   - Homepage URL: http://localhost:8000
   - Authorization callback URL: http://localhost:8000/github/callback/
4. Copy the Client ID and Client Secret to your `.env` file

### 4. Grant Repository Access

The GitHub OAuth token needs `repo` scope to:
- Clone repositories
- Create branches
- Push changes

This is already configured in the `GITHUB_SCOPES` setting.

## How It Works

### User Flow:

1. **Connect GitHub Account**
   - User clicks "Connect GitHub" button
   - Authorizes the application
   - GitHub access token is stored securely

2. **Fetch Repositories**
   - User clicks "Fetch Repositories"
   - System retrieves all accessible repositories

3. **Request Code Changes**
   - User enters natural language description in the input field on any repository card
   - Examples:
     - "Add error handling to the login function"
     - "Create a new API endpoint for user profile"
     - "Fix the bug in the payment processing module"
     - "Refactor the database connection code"

4. **AI Processing** (Automated):
   - System creates a change request record
   - Background process starts:
     - Clones the repository to a temporary directory
     - Sends request to OpenAI GPT-4 for analysis
     - AI generates code changes
     - Creates a new branch with timestamp
     - Commits and pushes changes
     - Records the results

5. **View Results**
   - User clicks "View AI Requests" button
   - See status of all requests (pending, processing, completed, failed)
   - View branch names, AI analysis, files changed
   - Access links to the new branches on GitHub

## Technical Architecture

### Models:

1. **GitHubConnection**
   - Stores OAuth token and user info
   - One-to-one relationship with User

2. **GitHubRepository**
   - Cached repository metadata
   - Linked to GitHubConnection

3. **CodeChangeRequest**
   - Tracks each AI change request
   - Status: pending → processing → cloning → analyzing → applying → pushing → completed/failed
   - Stores: request text, AI response, branch name, files changed, errors

### Services:

**AICodeChangeService** ([github/ai_service.py](github/ai_service.py)):
- `clone_repository()`: Clones repo using GitHub token
- `analyze_request()`: Uses GPT-4 to understand the request
- `apply_changes()`: Generates and applies code changes
- `create_and_push_branch()`: Git operations for branch creation and push
- `cleanup()`: Removes temporary files

### Views:

1. `request_changes()`: Handles form submission, creates request, starts background processing
2. `view_requests()`: Lists all user's change requests
3. `request_status()`: AJAX endpoint for real-time status updates

## Important Notes

### Security Considerations:

1. **Access Tokens**: GitHub access tokens are stored encrypted in the database
2. **Temporary Files**: Repositories are cloned to temporary directories and cleaned up after processing
3. **User Isolation**: Each user can only access their own repositories and requests

### Limitations:

1. **Complex Changes**: AI-generated code may require manual review and adjustments
2. **Large Repositories**: Very large repos may take longer to process
3. **Context Window**: GPT-4 has token limits, so very large files may be truncated
4. **Cost**: Each request uses OpenAI API tokens (approximately $0.01-0.10 per request)

### Best Practices:

1. **Be Specific**: Provide clear, detailed descriptions of desired changes
2. **Small Changes**: Break large features into smaller, focused requests
3. **Review Changes**: Always review the generated branch before merging
4. **Iterative**: Use multiple requests to refine changes if needed

## Troubleshooting

### Common Issues:

1. **"No OpenAI API key found"**
   - Solution: Add `OPENAI_API_KEY` to your `.env` file

2. **"Authentication failed"**
   - Solution: Reconnect your GitHub account to refresh the token

3. **"Failed to clone repository"**
   - Solution: Ensure the GitHub token has `repo` scope
   - Check that the repository exists and you have access

4. **"Request timed out"**
   - Solution: For large repos, the process may take several minutes
   - Check the "View AI Requests" page for status updates

## Future Enhancements

Potential improvements:
- Automatic pull request creation
- Real-time progress updates via WebSockets
- Support for multiple file modifications
- Code review suggestions
- Integration with CI/CD pipelines
- Custom AI prompts and templates
- Rollback functionality

## API Endpoints

- `POST /github/request-changes/<repo_id>/` - Submit a change request
- `GET /github/requests/` - View all change requests
- `GET /github/request-status/<request_id>/` - Get request status (AJAX)

## Database Schema

See [github/models.py](github/models.py) for complete model definitions.

## License

This feature is part of the Jadeed project.
