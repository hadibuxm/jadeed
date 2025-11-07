# Codex CLI Setup Guide

## Quick Start

This document provides instructions for setting up Codex CLI to enable AI-powered code changes in your GitHub repositories.

## Installation

### Option 1: Using npm (Recommended)
```bash
npm install -g @openai/codex-cli
```

### Option 2: Using pip
```bash
pip install openai-codex-cli
```

### Option 3: From Source
```bash
git clone https://github.com/openai/codex-cli
cd codex-cli
npm install
npm link
```

## Verification

After installation, verify that Codex CLI is properly installed:

```bash
which codex
# Should output: /usr/local/bin/codex or similar

codex --version
# Should output the version number

codex --help
# Should display help information
```

## Configuration

Codex CLI requires authentication with OpenAI. Run the following to set up:

```bash
codex auth login
```

This will:
1. Open your browser for authentication
2. Save your credentials locally
3. Enable Codex CLI to run programmatically

## Testing the Setup

Test Codex CLI with a simple command:

```bash
# Create a test directory
mkdir test-codex
cd test-codex

# Create a simple file
echo "def hello():\n    pass" > test.py

# Run Codex to add a docstring
codex exec --full-auto "Add a docstring to the hello function in test.py"

# Check the result
cat test.py
```

## Integration with Django App

Once Codex CLI is installed and configured:

1. **Restart your Django development server**:
   ```bash
   python manage.py runserver
   ```

2. **Navigate to GitHub Integration**:
   - Go to http://localhost:8000/github/
   - Connect your GitHub account
   - Fetch your repositories

3. **Test with a simple request**:
   - Find a test repository
   - In the "AI Code Assistant" section, enter:
     ```
     Add a comment at the top of the main file explaining what this project does
     ```
   - Click "Generate Code Changes"
   - Wait for the process to complete (check Django admin for status)
   - Review the new branch on GitHub

## Command Reference

### Basic Usage
```bash
# Read-only analysis
codex exec "find all TODO comments"

# With file editing (what our app uses)
codex exec --full-auto "add error handling to the login function"

# With network access (if needed)
codex exec --sandbox danger-full-access "fetch data and update config"
```

### Flags
- `--full-auto`: Allow file edits without approval
- `--sandbox danger-full-access`: Allow network access and system commands
- `--help`: Show all available options

## Troubleshooting

### "command not found: codex"
- Codex CLI is not in your PATH
- Try: `npm config get prefix` to find npm global bin directory
- Add it to PATH: `export PATH="$PATH:$(npm config get prefix)/bin"`

### Authentication Issues
- Run: `codex auth logout` then `codex auth login`
- Check your OpenAI account has Codex access
- Verify credentials: `codex auth status`

### Permission Errors
- Ensure your user has write permissions to the repository directory
- On Unix/Linux, check: `ls -la` in the repo directory

### Execution Timeouts
- Default timeout is 5 minutes (set in `code_change_service.py`)
- For large repos, increase the timeout:
  ```python
  # In github/code_change_service.py
  timeout=600  # 10 minutes
  ```

## Security Considerations

When running in production:

1. **Sandbox Settings**: The app uses `--full-auto` which allows file edits
2. **Timeout Protection**: 5-minute timeout prevents infinite execution
3. **Isolated Execution**: Each request runs in a temporary directory
4. **User Validation**: Only authenticated users with GitHub access can make requests

## System Requirements

- **Node.js**: v14 or higher (for npm installation)
- **Python**: 3.8+ (if using pip)
- **Git**: For repository operations
- **Disk Space**: Temporary directories for cloned repositories
- **Memory**: At least 2GB free for large repositories

## Cost Considerations

Codex CLI usage may incur costs depending on your OpenAI plan:
- Check current pricing: https://openai.com/pricing
- Monitor usage in your OpenAI dashboard
- Consider setting usage limits for production deployments

## Advanced Configuration

### Custom Codex Settings

Edit `github/code_change_service.py` to customize:

```python
# Adjust timeout
timeout=300  # 5 minutes (default)

# Add additional flags
['codex', 'exec', '--full-auto', '--model', 'codex-davinci-002', task_prompt]

# Change sandbox settings
['codex', 'exec', '--sandbox', 'read-only', task_prompt]
```

### Environment Variables

You can set Codex-specific environment variables:

```bash
# In your .env file
CODEX_MODEL=codex-davinci-002
CODEX_TIMEOUT=600
```

Then update the service to read these values.

## Monitoring and Logging

To monitor Codex execution:

1. **Django Admin**: Check code change request status
2. **Server Logs**: Watch Django console for Codex output
3. **Git History**: Review commits in the created branches

## Support and Resources

- **Codex Documentation**: https://developers.openai.com/codex/sdk
- **OpenAI Community**: https://community.openai.com/
- **GitHub Issues**: Report issues in your repository
- **Django Logs**: Check server logs for detailed error messages

## Next Steps

After setup:
1. Test with simple requests first
2. Gradually try more complex code changes
3. Always review changes before merging
4. Monitor costs and usage
5. Set up proper error handling and notifications

Happy coding with AI! 🤖
