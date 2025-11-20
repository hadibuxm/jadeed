"""
Service for handling AI-powered code changes to GitHub repositories using Codex CLI.
"""
import os
import shutil
import subprocess
import tempfile
import logging
from datetime import datetime
from git import Repo, GitCommandError
from django.conf import settings
from django.utils import timezone

# Set up logger
logger = logging.getLogger(__name__)


class CodeChangeService:
    """Service to clone repos, make AI-powered code changes using Codex CLI, and push to GitHub."""

    def __init__(self, github_connection, repository, change_request_obj):
        """
        Initialize the service.

        Args:
            github_connection: GitHubConnection model instance
            repository: GitHubRepository model instance
            change_request_obj: CodeChangeRequest model instance
        """
        self.github_connection = github_connection
        self.repository = repository
        self.change_request_obj = change_request_obj
        self.repo_path = None
        self.git_repo = None

    def _log(self, message, level='info'):
        """Add a log entry to both the database and Python logger."""
        # Log to database
        self.change_request_obj.add_log(message)

        # Log to Python logger
        log_method = getattr(logger, level, logger.info)
        log_method(f"[Request {self.change_request_obj.id}] {message}")

    def _record_codex_logs(self, stdout=None, stderr=None):
        """Persist raw stdout/stderr from Codex CLI for troubleshooting."""
        if stdout or stderr:
            self.change_request_obj.set_codex_logs(stdout, stderr)

    def execute(self):
        """
        Execute the complete workflow:
        1. Clone repository
        2. Create new branch
        3. Apply AI-powered code changes
        4. Push to GitHub

        Returns:
            dict: Result with success status and message
        """
        try:
            self._log(f"Starting code change request for repository: {self.repository.full_name}")
            self._log(f"Change request: {self.change_request_obj.change_request}")

            # Step 1: Clone repository
            self._update_status('cloning', 'Cloning repository...')
            self._log("Starting repository clone...")
            self._clone_repository()
            self._log(f"Repository cloned successfully to: {self.repo_path}")

            # Step 2: Create new branch
            branch_name = f"ai-changes-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            self._log(f"Creating new branch: {branch_name}")
            self._create_branch(branch_name)
            self.change_request_obj.branch_name = branch_name
            self.change_request_obj.save()
            self._log(f"Branch '{branch_name}' created and checked out")

            # Step 3: Apply code changes using AI
            self._update_status('processing', 'Processing code changes with AI...')
            self._log("Starting Codex CLI execution...")
            self._apply_code_changes()
            self._log("Code changes applied successfully")

            # Step 4: Push to GitHub
            self._update_status('pushing', 'Pushing changes to GitHub...')
            self._log(f"Pushing branch '{branch_name}' to remote...")
            self._push_changes(branch_name)
            self._log("Changes pushed successfully to GitHub")

            # Mark as completed
            self._update_status('completed', 'Code changes completed successfully!')
            self.change_request_obj.completed_at = timezone.now()
            self.change_request_obj.save()
            self._log(f"✓ Workflow completed successfully! Branch: {branch_name}")

            return {
                'success': True,
                'message': f'Code changes pushed to branch: {branch_name}',
                'branch_name': branch_name
            }

        except Exception as e:
            error_msg = str(e)
            self._log(f"✗ Error occurred: {error_msg}", level='error')
            self._update_status('failed', f'Error: {error_msg}')
            return {
                'success': False,
                'error': error_msg
            }

        finally:
            # Clean up temporary directory
            self._log("Cleaning up temporary files...")
            self._cleanup()
            self._log("Cleanup completed")

    def _clone_repository(self):
        """Clone the repository to a temporary directory."""
        # Create temporary directory
        self.repo_path = tempfile.mkdtemp(prefix='github_clone_')

        # Build clone URL with access token for authentication
        clone_url = self.repository.clone_url.replace(
            'https://',
            f'https://{self.github_connection.access_token}@'
        )

        # Clone the repository
        try:
            self.git_repo = Repo.clone_from(clone_url, self.repo_path)
        except GitCommandError as e:
            raise Exception(f"Failed to clone repository: {str(e)}")

    def _create_branch(self, branch_name):
        """Create a new branch for the changes."""
        try:
            # Create and checkout new branch
            new_branch = self.git_repo.create_head(branch_name)
            new_branch.checkout()
        except GitCommandError as e:
            raise Exception(f"Failed to create branch: {str(e)}")

    def _apply_code_changes(self):
        """Use Codex CLI to analyze the codebase and apply requested changes."""
        try:
            # Check if codex is installed
            self._log("Checking for Codex CLI installation...")
            check_codex = subprocess.run(
                ['which', 'codex'],
                capture_output=True,
                text=True
            )

            if check_codex.returncode != 0:
                raise Exception(
                    "Codex CLI is not installed. Please install it from https://developers.openai.com/codex/sdk"
                )

            codex_path = check_codex.stdout.strip()
            self._log(f"Codex CLI found at: {codex_path}")

            # Prepare the task prompt for Codex
            task_prompt = f"""Repository: {self.repository.full_name}
                Language: {self.repository.language}

                Task: {self.change_request_obj.change_request}

            """

            self._log(f"Executing Codex with task prompt (timeout: 5 minutes)...")
            self._log(f"Working directory: {self.repo_path}")

            # Run Codex CLI in non-interactive mode with full file editing access
            # Using --full-auto to allow file edits and --sandbox danger-full-access if network needed
            process = subprocess.run(
                ['codex', 'exec', '--full-auto', task_prompt],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=1800  # 5 minute timeout
            )

            self._record_codex_logs(process.stdout, process.stderr)

            # Check if Codex execution was successful
            if process.returncode != 0:
                error_output = process.stderr if process.stderr else process.stdout
                self._log(f"Codex execution failed with return code {process.returncode}", level='error')
                self._log(f"Error output: {error_output}", level='error')
                raise Exception(f"Codex execution failed: {error_output}")

            # Log the Codex output for debugging
            codex_output = process.stdout.strip()
            if codex_output:
                self._log(f"Codex output:\n{codex_output[:1000]}")  # Log first 1000 chars

            # Check stderr for warnings
            if process.stderr:
                self._log(f"Codex stderr: {process.stderr[:500]}", level='warning')

            # Check if there are any changes made
            self._log("Checking for file changes...")
            if self.git_repo.is_dirty(untracked_files=True):
                # Get list of changed files
                changed_files = [item.a_path for item in self.git_repo.index.diff(None)]
                untracked_files = self.git_repo.untracked_files

                self._log(f"Modified files: {', '.join(changed_files) if changed_files else 'None'}")
                self._log(f"New files: {', '.join(untracked_files) if untracked_files else 'None'}")

                # Stage all changes
                self._log("Staging all changes...")
                self.git_repo.git.add(A=True)

                # Commit the changes
                commit_message = f"AI-generated changes: {self.change_request_obj.change_request[:80]}"
                if codex_output:
                    commit_message += f"\n\nCodex output:\n{codex_output[:500]}"

                self._log("Committing changes...")
                self.git_repo.index.commit(commit_message)
                self._log(f"Changes committed with message: {commit_message[:100]}...")
            else:
                self._log("No file changes detected", level='warning')
                raise Exception("No changes were made by Codex. The task may not have been understood or applicable.")

        except subprocess.TimeoutExpired as exc:
            self._log("Codex execution timed out after 5 minutes", level='error')
            self._record_codex_logs(getattr(exc, 'output', None), getattr(exc, 'stderr', None))
            raise Exception("Codex execution timed out after 5 minutes")
        except Exception as e:
            self._log(f"Failed to apply code changes: {str(e)}", level='error')
            raise Exception(f"Failed to apply code changes: {str(e)}")

    def _push_changes(self, branch_name):
        """Push the changes to GitHub."""
        try:
            # Push to remote
            origin = self.git_repo.remote(name='origin')
            origin.push(refspec=f'{branch_name}:{branch_name}')
        except GitCommandError as e:
            raise Exception(f"Failed to push changes: {str(e)}")

    def _update_status(self, status, message=None):
        """Update the status of the code change request."""
        self.change_request_obj.status = status
        if message:
            if status == 'failed':
                self.change_request_obj.error_message = message
        self.change_request_obj.save()

    def _cleanup(self):
        """Clean up temporary files."""
        if self.repo_path and os.path.exists(self.repo_path):
            try:
                shutil.rmtree(self.repo_path)
            except Exception:
                pass  # Best effort cleanup
