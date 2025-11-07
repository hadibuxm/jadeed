# AI-Powered Code Changes Feature (Using Codex CLI)

## Overview
This feature allows you to request code changes in natural language for your GitHub repositories. The system will:
1. Clone the repository
2. Create a new branch
3. Use Codex CLI to analyze and modify the code programmatically
4. Push changes to the new branch on GitHub

## Prerequisites

### 1. Codex CLI Installation
You need to have Codex CLI installed on your system.

**Installation:**
1. Install Codex CLI following the instructions at: https://developers.openai.com/codex/sdk
2. Ensure `codex` command is available in your PATH
3. Verify installation:
   ```bash
   which codex
   codex --version
   ```

**Why Codex CLI?**
Codex CLI is specifically designed for programmatic code editing tasks and provides:
- Direct file system access for code modifications
- Better understanding of code structure and context
- Non-interactive mode for automated workflows
- Built-in sandboxing and safety features

### 2. GitHub Connection
- Connect your GitHub account with the appropriate scopes (the default `repo user` scopes are sufficient)
- Ensure your GitHub OAuth app has `repo` scope to allow pushing changes

## How to Use

1. **Navigate to GitHub Integration Page**
   - Go to `/github/` in your application
   - Connect your GitHub account if not already connected

2. **Fetch Your Repositories**
   - Click "Fetch Repositories" to load your GitHub repos

3. **Request Code Changes**
   - Find the repository you want to modify
   - In the "AI Code Assistant" section at the bottom of each repository card, enter your change request in natural language
   - Examples:
     - "Add error handling to the login function"
     - "Refactor the user controller to use async/await"
     - "Add input validation for email fields"
     - "Add unit tests for the authentication module"

4. **Submit and Wait**
   - Click "Generate Code Changes"
   - The system will process your request in the background
   - You'll see status updates as the process progresses

5. **Review Changes on GitHub**
   - Once completed, a new branch will be created with your changes
   - The branch name will be in the format: `ai-changes-YYYYMMDD-HHMMSS`
   - Go to your GitHub repository to review the changes
   - Create a pull request if you want to merge the changes

## Technical Architecture

### Components

1. **Frontend (HTML + JavaScript)**
   - `github/templates/github/index.html` - UI with text input for each repository
   - AJAX form submission with real-time status updates

2. **Backend (Django)**
   - `github/views.py::request_code_change` - Handles API requests
   - `github/models.py::CodeChangeRequest` - Tracks request status
   - `github/code_change_service.py::CodeChangeService` - Core service class

3. **Service Layer**
   - **Repository Cloning**: Uses GitPython to clone repositories with OAuth token authentication
   - **Branch Management**: Creates new branches for each change request
   - **AI Integration**: Uses Codex CLI (`codex exec --full-auto`) to understand code and make modifications
   - **Git Operations**: Commits and pushes changes to GitHub
   - **Non-interactive Mode**: Runs Codex programmatically without user interaction

### Workflow

```
User Request
    ↓
Create CodeChangeRequest record
    ↓
Background Thread Execution
    ↓
1. Clone Repository (with access token)
    ↓
2. Create New Branch
    ↓
3. Execute Codex CLI (codex exec --full-auto)
    ↓
4. Codex analyzes codebase and applies changes
    ↓
5. Stage all modified files
    ↓
6. Commit Changes with Codex output
    ↓
7. Push to GitHub
    ↓
Update Status (completed/failed)
```

### Database Models

**CodeChangeRequest**
- `repository` - ForeignKey to GitHubRepository
- `user` - ForeignKey to User
- `change_request` - Text description of requested changes
- `status` - Current status (pending, cloning, processing, pushing, completed, failed)
- `branch_name` - Name of the created branch
- `error_message` - Error details if failed
- `created_at` - Timestamp
- `completed_at` - Completion timestamp

## Security Considerations

1. **Access Token Storage**: GitHub access tokens are stored encrypted in the database
2. **Scope Validation**: Only repositories the user owns or has access to can be modified
3. **Background Processing**: Code changes run in background threads to avoid blocking
4. **Error Handling**: Comprehensive error handling and status tracking

## Limitations

1. **Repository Size**: Very large repositories may take longer to process (5 minute timeout)
2. **AI Accuracy**: Codex may not always understand complex or ambiguous change requests
3. **Manual Review**: Always review AI-generated changes before merging
4. **Codex Availability**: Requires Codex CLI to be installed on the server

## Troubleshooting

### "Codex CLI is not installed"
- Install Codex CLI from https://developers.openai.com/codex/sdk
- Ensure the `codex` command is in your system PATH
- Verify with: `which codex`
- Restart your Django development server after installation

### "Failed to clone repository"
- Check that your GitHub access token has `repo` scope
- Ensure the repository exists and you have access

### "Failed to push changes"
- Verify your GitHub access token is still valid
- Check that you have write permissions to the repository

### Changes Not Appearing
- The process runs in the background, give it a few minutes (up to 5 minutes)
- Check the Django admin panel under "Code Change Requests" to see the status
- Check error messages in the request record
- Look for Codex execution logs in your Django server console

### "Codex execution timed out"
- The repository may be too large or the task too complex
- Try breaking down the request into smaller, more specific tasks
- Consider increasing the timeout in `code_change_service.py` if needed

## Admin Interface

Track all code change requests in the Django admin:
- Navigate to `/admin/github/codechangerequest/`
- View status, branch names, and error messages
- Filter by status and date

## Codex CLI Command Details

The service executes Codex with the following command:
```bash
codex exec --full-auto "<task description>"
```

**Flags used:**
- `--full-auto`: Allows Codex to edit files without requiring approval
- Runs in the cloned repository directory
- Captures stdout and stderr for logging
- 5-minute timeout to prevent infinite execution

**Task Prompt Format:**
```
Repository: <repo_name>
Language: <primary_language>

Task: <user's change request>

Please analyze the codebase and make the necessary code changes to implement this request.
Make sure to:
1. Understand the existing code structure
2. Make minimal but effective changes
3. Follow the existing code style and conventions
4. Ensure the changes are production-ready

After making changes, git add all modified files.
```

## Future Enhancements

Possible improvements:
- Real-time status updates using WebSockets
- Pull request auto-creation with GitHub API
- Code review integration
- Multi-file diff preview before pushing
- Rollback functionality
- Configurable Codex timeout and sandbox settings
- Streaming Codex output to the UI
- Support for custom Codex flags per repository

## API Response Format

**Success Response:**
```json
{
  "success": true,
  "message": "Code change request submitted. Processing in background...",
  "request_id": 123
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Error message here"
}
```
