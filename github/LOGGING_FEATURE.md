# Logging Feature Documentation

## Overview

A comprehensive logging system has been added to track code change requests in real-time, providing visibility into every step of the workflow from request submission to completion.

## Features

### 1. **Database Logging**
- All execution steps are logged to the database
- Logs persist after request completion
- Timestamped entries for precise tracking

### 2. **Real-Time Log Display**
- Frontend automatically polls for updates every 2 seconds
- Logs display in a monospace, scrollable text area
- Auto-scrolls to bottom as new logs arrive
- Collapsible log viewer with close button

### 3. **Python Logger Integration**
- All logs written to both database and Python logger
- Console output for server-side debugging
- Log levels: info, warning, error

### 4. **Admin Interface**
- View execution logs in Django admin
- Formatted display with monospace font
- Collapsible log section
- Searchable and filterable requests

## Components

### Backend Changes

#### 1. Model ([github/models.py](github/models.py))
```python
class CodeChangeRequest(models.Model):
    execution_log = models.TextField(blank=True, null=True)

    def add_log(self, message):
        """Add timestamped log entry"""
        # Adds timestamp and saves to database
```

#### 2. Service ([github/code_change_service.py](github/code_change_service.py))
Logs added for:
- Request initialization
- Repository cloning (with path)
- Branch creation
- Codex CLI execution
  - Installation check
  - Codex path
  - Execution status
  - Output (first 1000 chars)
  - Changed files
- Git operations (staging, committing)
- Push to GitHub
- Cleanup operations
- Errors at each step

#### 3. Views ([github/views.py](github/views.py))
- Request receipt logging
- User and repository validation logging
- Background thread start/completion logging
- Error logging with stack traces

#### 4. API Endpoint
```python
GET /github/code-change-status/<request_id>/
```
Returns:
```json
{
  "success": true,
  "status": "processing",
  "branch_name": "ai-changes-20250107-123456",
  "execution_log": "[timestamp] log entries...",
  "codex_logs": "STDOUT/STDERR from Codex CLI",
  "error_message": null,
  "created_at": "2025-01-07T12:34:56Z",
  "completed_at": null
}
```

### Frontend Changes

#### Real-Time Log Viewer
Located in [github/templates/github/index.html](github/templates/github/index.html):

**Features:**
- Collapsible card UI
- Monospace font for readability
- Max height 300px with scroll
- Auto-scroll to latest logs
- Close button to hide logs
- Polling every 2 seconds
- Status indicators:
  - Pending (spinner)
  - Cloning (spinner + message)
  - Processing (spinner + message)
  - Pushing (spinner + message)
  - Completed (green checkmark)
  - Failed (red X)

**UI Elements:**
```html
<div class="execution-log">
  <div class="card">
    <div class="card-header">
      Execution Log [X]
    </div>
    <div class="card-body">
      <pre class="log-content"></pre>
    </div>
  </div>
</div>
```

## Log Entry Format

```
[YYYY-MM-DD HH:MM:SS] Log message
[YYYY-MM-DD HH:MM:SS] Another message
...
```

## Example Log Output

```
[2025-01-07 14:30:01] Request created by user: john_doe
[2025-01-07 14:30:01] Repository: myorg/myrepo
[2025-01-07 14:30:01] Change request: Add error handling to login function
[2025-01-07 14:30:01] Starting code change request for repository: myorg/myrepo
[2025-01-07 14:30:01] Starting repository clone...
[2025-01-07 14:30:05] Repository cloned successfully to: /tmp/github_clone_xyz123
[2025-01-07 14:30:05] Creating new branch: ai-changes-20250107-143001
[2025-01-07 14:30:05] Branch 'ai-changes-20250107-143001' created and checked out
[2025-01-07 14:30:05] Starting Codex CLI execution...
[2025-01-07 14:30:05] Checking for Codex CLI installation...
[2025-01-07 14:30:05] Codex CLI found at: /usr/local/bin/codex
[2025-01-07 14:30:05] Executing Codex with task prompt (timeout: 5 minutes)...
[2025-01-07 14:30:05] Working directory: /tmp/github_clone_xyz123
[2025-01-07 14:32:15] Codex output:
Analyzed 45 files in the repository
Found login.py file
Added try-catch blocks for authentication
Updated error messages
[2025-01-07 14:32:15] Checking for file changes...
[2025-01-07 14:32:15] Modified files: src/auth/login.py, tests/test_login.py
[2025-01-07 14:32:15] New files: None
[2025-01-07 14:32:15] Staging all changes...
[2025-01-07 14:32:15] Committing changes...
[2025-01-07 14:32:16] Changes committed with message: AI-generated changes: Add error handling to login function...
[2025-01-07 14:32:16] Code changes applied successfully
[2025-01-07 14:32:16] Pushing branch 'ai-changes-20250107-143001' to remote...
[2025-01-07 14:32:20] Changes pushed successfully to GitHub
[2025-01-07 14:32:20] ✓ Workflow completed successfully! Branch: ai-changes-20250107-143001
[2025-01-07 14:32:20] Cleaning up temporary files...
[2025-01-07 14:32:20] Cleanup completed
```

## Admin Panel Integration

### Viewing Logs

1. Navigate to Django admin: `/admin/github/codechangerequest/`
2. Click on any code change request
3. Expand the "Execution Log" section
4. View formatted logs with timestamps

### Log Display Features
- Monospace font for readability
- Light gray background
- Preserved whitespace and line breaks
- Wrapped long lines
- Collapsible by default

## Python Logger Output

Server console will show:
```
INFO [Request 123] Starting code change request for repository: myorg/myrepo
INFO [Request 123] Repository cloned successfully to: /tmp/github_clone_xyz123
INFO [Request 123] Codex CLI found at: /usr/local/bin/codex
...
```

## API Usage

### Poll for Status and Logs

```javascript
// Poll every 2 seconds
setInterval(() => {
  fetch(`/github/code-change-status/${requestId}/`)
    .then(response => response.json())
    .then(data => {
      console.log('Status:', data.status);
      console.log('Logs:', data.execution_log);

      if (data.status === 'completed' || data.status === 'failed') {
        // Stop polling
        clearInterval(pollInterval);
      }
    });
}, 2000);
```

## Benefits

1. **Transparency**: Users see exactly what's happening
2. **Debugging**: Detailed logs help identify issues
3. **Monitoring**: Track progress in real-time
4. **Auditing**: Complete history of all operations
5. **User Experience**: No more "black box" processing

## Performance Considerations

- **Polling Interval**: 2 seconds (configurable)
- **Log Size**: First 1000 chars of Codex output logged
- **Database Impact**: Minimal (text field, indexed by request_id)
- **Network**: Lightweight JSON responses (~1-5KB)

## Error Handling

Logs capture:
- Installation issues (Codex not found)
- Git errors (clone, push failures)
- Codex execution errors
- Timeout errors
- Network errors
- Permission errors

## Future Enhancements

Possible improvements:
- **WebSocket Integration**: Replace polling with WebSockets for real-time push
- **Log Levels**: Color-code log entries (info=blue, warning=yellow, error=red)
- **Log Search**: Search within execution logs
- **Log Export**: Download logs as text file
- **Log Retention**: Auto-delete old logs after N days
- **Metrics**: Track average execution time, success rate
- **Notifications**: Email/Slack when request completes

## Troubleshooting

### Logs Not Updating
- Check that polling is active (look for console errors)
- Verify API endpoint is accessible
- Check Django server is running
- Verify request_id is correct

### Missing Logs in Admin
- Ensure migration was run: `python manage.py migrate`
- Check that `execution_log` field exists in database
- Verify logs are being added with `add_log()` method

### Polling Stopped
- Check browser console for errors
- Verify status endpoint returns valid JSON
- Check for JavaScript errors in page

## Security

- Logs are user-specific (only creator can view)
- No sensitive data (passwords, tokens) logged
- Access token masked in clone URL logs
- Admin access required for full log viewing

## Testing

Test the logging feature:
1. Submit a code change request
2. Watch logs appear in real-time
3. Verify status updates correctly
4. Check completed request shows final logs
5. Confirm admin panel displays logs correctly
6. Test error scenarios (invalid repo, Codex not installed)

---

**Note**: Logs persist indefinitely. Consider implementing log rotation or cleanup for production deployments.
