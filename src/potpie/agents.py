from langchain.agents.agent_types import AgentType
from langchain.agents import initialize_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
from typing import List, Dict
from potpie.config import settings
from potpie.models import CodeIssue, FileAnalysis, AnalysisSummary, AnalysisResults
import logging
import json
import re

logger = logging.getLogger(__name__)


class CodeAnalysisTool:
    """Custom tools for code analysis"""

    @staticmethod
    def analyze_code_style(code: str, language: str, filename: str) -> str:
        """Analyze code for style and formatting issues."""
        issues = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append(
                    {
                        "type": "style",
                        "line": i,
                        "description": f"Line too long ({len(line)} characters)",
                        "suggestion": "Break line into multiple lines or refactor",
                        "severity": "low",
                    }
                )

            if line.endswith(" ") or line.endswith("\t"):
                issues.append(
                    {
                        "type": "style",
                        "line": i,
                        "description": "Trailing whitespace detected",
                        "suggestion": "Remove trailing whitespace",
                        "severity": "low",
                    }
                )

            if language == "python":
                if line.strip().startswith("def ") and i < len(lines) - 1:
                    next_line = lines[i].strip() if i < len(lines) else ""
                    if not next_line.startswith('"""') and not next_line.startswith(
                        "'''"
                    ):
                        issues.append(
                            {
                                "type": "style",
                                "line": i,
                                "description": "Function missing docstring",
                                "suggestion": "Add docstring to document function purpose",
                                "severity": "medium",
                            }
                        )

        return json.dumps(issues)

    @staticmethod
    def detect_potential_bugs(code: str, language: str, filename: str) -> str:
        """Detect potential bugs and errors."""
        issues = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()

            if language == "python":
                if ".get(" in line and "if" not in line and "assert" not in line:
                    issues.append(
                        {
                            "type": "bug",
                            "line": i,
                            "description": "Potential None value from dict.get() without null check",
                            "suggestion": "Add null check or provide default value",
                            "severity": "medium",
                        }
                    )

                if line_stripped == "except:":
                    issues.append(
                        {
                            "type": "bug",
                            "line": i,
                            "description": "Bare except clause catches all exceptions",
                            "suggestion": "Specify exception types to catch",
                            "severity": "high",
                        }
                    )

            elif language == "javascript" or language == "typescript":
                if " == " in line and " === " not in line:
                    issues.append(
                        {
                            "type": "bug",
                            "line": i,
                            "description": "Using == instead of === for comparison",
                            "suggestion": "Use === for strict equality comparison",
                            "severity": "medium",
                        }
                    )

                if ".length" in line and "if" not in line:
                    issues.append(
                        {
                            "type": "bug",
                            "line": i,
                            "description": "Accessing .length without null/undefined check",
                            "suggestion": "Add null/undefined check before accessing length",
                            "severity": "medium",
                        }
                    )

        return json.dumps(issues)

    @staticmethod
    def analyze_performance(code: str, language: str, filename: str) -> str:
        """Analyze code for performance issues."""
        issues = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            if "for " in line and any(
                "for " in lines[j] for j in range(max(0, i - 5), min(len(lines), i + 5))
            ):
                issues.append(
                    {
                        "type": "performance",
                        "line": i,
                        "description": "Nested loops detected - potential O(n²) complexity",
                        "suggestion": "Consider optimizing algorithm or using more efficient data structures",
                        "severity": "medium",
                    }
                )

            if language == "python":
                if (
                    ("for " in line or "while " in line)
                    and "+=" in line
                    and "str" in line
                ):
                    issues.append(
                        {
                            "type": "performance",
                            "line": i,
                            "description": "String concatenation in loop is inefficient",
                            "suggestion": "Use list.join() or f-strings for better performance",
                            "severity": "medium",
                        }
                    )

            elif language == "javascript":
                if ".push(" in line and "for" in line:
                    issues.append(
                        {
                            "type": "performance",
                            "line": i,
                            "description": "Array.push() in loop may be inefficient",
                            "suggestion": "Consider pre-allocating array size or using other methods",
                            "severity": "low",
                        }
                    )

        return json.dumps(issues)

    @staticmethod
    def analyze_security(code: str, language: str, filename: str) -> str:
        """Analyze code for security vulnerabilities."""
        issues = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            line_stripped = line.strip().lower()

            if "select" in line_stripped and (
                "format" in line_stripped
                or "%" in line_stripped
                or "+" in line_stripped
            ):
                issues.append(
                    {
                        "type": "security",
                        "line": i,
                        "description": "Potential SQL injection vulnerability",
                        "suggestion": "Use parameterized queries or prepared statements",
                        "severity": "critical",
                    }
                )

            secret_patterns = ["password", "secret", "key", "token", "api_key"]
            for pattern in secret_patterns:
                if (
                    pattern in line_stripped
                    and "=" in line_stripped
                    and ('"' in line or "'" in line)
                ):
                    issues.append(
                        {
                            "type": "security",
                            "line": i,
                            "description": f"Potential hardcoded {pattern} detected",
                            "suggestion": "Move sensitive data to environment variables or secure configuration",
                            "severity": "high",
                        }
                    )

            if "eval(" in line_stripped:
                issues.append(
                    {
                        "type": "security",
                        "line": i,
                        "description": "Use of eval() function is dangerous",
                        "suggestion": "Avoid eval() and use safer alternatives",
                        "severity": "critical",
                    }
                )

        return json.dumps(issues)


class CodeReviewAgent:
    def __init__(self):
        self.llm = self._initialize_llm()
        self.tools = self._create_tools()
        self.agent = self._create_agent()

    def _initialize_llm(self):
        """Initialize the language model based on configuration."""
        logger.info("Initializing Gemini LLM")
        return ChatGoogleGenerativeAI(
            google_api_key=settings.google_api_key,
            model=settings.gemini_model,
            temperature=0.1,
            convert_system_message_to_human=True,  # Gemini doesn't support system messages
        )

    def _create_tools(self):
        """Create tools for the agent to use."""
        tools = [
            Tool(
                name="analyze_code_style",
                description="Analyze code for style and formatting issues. Input should be: code, language, filename",
                func=lambda x: CodeAnalysisTool.analyze_code_style(*x.split("|||")),
            ),
            Tool(
                name="detect_potential_bugs",
                description="Detect potential bugs and errors in code. Input should be: code, language, filename",
                func=lambda x: CodeAnalysisTool.detect_potential_bugs(*x.split("|||")),
            ),
            Tool(
                name="analyze_performance",
                description="Analyze code for performance issues. Input should be: code, language, filename",
                func=lambda x: CodeAnalysisTool.analyze_performance(*x.split("|||")),
            ),
            Tool(
                name="analyze_security",
                description="Analyze code for security vulnerabilities. Input should be: code, language, filename",
                func=lambda x: CodeAnalysisTool.analyze_security(*x.split("|||")),
            ),
        ]
        return tools

    def _create_agent(self):
        """Create the main code review agent."""
        system_message = """You are an expert code reviewer with extensive experience in multiple programming languages.
        Your job is to analyze code files and provide comprehensive feedback on:
        
        1. Code style and formatting
        2. Potential bugs and errors
        3. Performance optimizations
        4. Security vulnerabilities
        
        You have access to specialized analysis tools. Use them to thoroughly examine the code and provide detailed,
        actionable feedback. Always be constructive and provide specific suggestions for improvement.
        
        When analyzing code, consider:
        - Language-specific best practices
        - Common pitfalls and anti-patterns
        - Security implications
        - Performance considerations
        - Code maintainability and readability
        
        Format your final response as a JSON object with the structure:
        {
            "issues": [
                {
                    "type": "style|bug|performance|security",
                    "line": <line_number>,
                    "description": "<detailed description>",
                    "suggestion": "<specific suggestion>",
                    "severity": "low|medium|high|critical"
                }
            ],
            "summary": "<overall assessment>",
            "recommendations": ["<recommendation1>", "<recommendation2>"]
        }
        """

        memory = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )

        agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            memory=memory,
            verbose=True,
            system_message=system_message,
        )

        return agent

    def analyze_file(
        self,
        file_content: str,
        filename: str,
        language: str,
        diff: str | None = None,
        patch: str | None = None,
    ) -> FileAnalysis:
        """Analyze a single file focusing on the diff/changes made."""
        logger.info(f"Analyzing file: {filename} (language: {language})")

        try:
            analysis_content = diff or patch or file_content
            analysis_type = "diff" if (diff or patch) else "full_file"

            if analysis_type == "diff":
                analysis_prompt = f"""
                Please analyze the following code changes (diff/patch) for issues:
                
                Filename: {filename}
                Language: {language}
                Analysis Type: Code Diff/Changes Only
                
                Changes Made:
                ```diff
                {analysis_content}
                ```
                
                Focus your analysis ONLY on the changed lines (+ additions, - deletions).
                Ignore unchanged context lines unless they're directly related to the changes.
                
                Please analyze for:
                1. Code style and formatting issues in the NEW code
                2. Potential bugs introduced by the changes
                3. Performance implications of the changes
                4. Security vulnerabilities in the new/modified code
                
                For each issue found, provide:
                - The approximate line number in the diff
                - Issue type (style/bug/performance/security)
                - Clear description of the problem
                - Specific suggestion for improvement
                - Severity level (low/medium/high/critical)
                
                Focus on actionable feedback for the code changes only.
                """
            else:
                analysis_prompt = f"""
                Please analyze the following {language} code file for issues:
                
                Filename: {filename}
                Language: {language}
                Analysis Type: Full File
                
                Code:
                ```{language}
                {analysis_content}
                ```
                
                Please use your available tools to perform a comprehensive analysis covering:
                1. Code style and formatting
                2. Potential bugs and errors
                3. Performance issues
                4. Security vulnerabilities
                
                Provide a detailed analysis with specific line numbers and actionable suggestions.
                """

            result = self.agent.run(analysis_prompt)

            issues = self._parse_agent_result(result, analysis_content, analysis_type)

            return FileAnalysis(
                name=filename.split("/")[-1],
                path=filename,
                issues=issues,
                lines_analyzed=len(analysis_content.split("\n")),
            )

        except Exception as e:
            logger.error(f"Error analyzing file {filename}: {e}")
            return FileAnalysis(
                name=filename.split("/")[-1],
                path=filename,
                issues=[
                    CodeIssue(
                        type="error",
                        line=1,
                        description=f"Analysis failed: {str(e)}",
                        suggestion="Manual review required",
                        severity="medium",
                    )
                ],
                lines_analyzed=len((diff or patch or file_content).split("\n")),
            )

    def _parse_agent_result(
        self, result: str, content: str, analysis_type: str = "full_file"
    ) -> List[CodeIssue]:
        """Parse the agent's result and convert to CodeIssue objects."""
        issues = []

        try:
            json_match = re.search(r"\{.*\}", result, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())

                if "issues" in result_data:
                    for issue_data in result_data["issues"]:
                        line_number = issue_data.get("line", 1)
                        if analysis_type == "diff":
                            line_number = self._map_diff_line_to_file_line(
                                line_number, content
                            )

                        issue = CodeIssue(
                            type=issue_data.get("type", "unknown"),
                            line=line_number,
                            description=issue_data.get("description", "No description"),
                            suggestion=issue_data.get("suggestion", "No suggestion"),
                            severity=issue_data.get("severity", "medium"),
                        )
                        issues.append(issue)

            if not issues:
                issues = self._extract_issues_from_text(result, content, analysis_type)

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse agent result: {e}")
            issues = self._extract_issues_from_text(result, content, analysis_type)

        return issues

    def _map_diff_line_to_file_line(self, diff_line: int, diff_content: str) -> int:
        """Map a line number from diff to actual file line number."""
        try:
            lines = diff_content.split("\n")
            current_file_line = 0
            diff_line_count = 0

            for line in lines:
                if line.startswith("@@"):
                    match = re.search(r"\+(\d+)", line)
                    if match:
                        current_file_line = int(match.group(1)) - 1
                elif line.startswith("+"):
                    current_file_line += 1
                    diff_line_count += 1
                    if diff_line_count == diff_line:
                        return current_file_line
                elif line.startswith("-"):
                    # Deleted line - don't increment file line
                    diff_line_count += 1
                    if diff_line_count == diff_line:
                        return current_file_line
                elif not line.startswith("\\"):
                    current_file_line += 1
                    diff_line_count += 1
                    if diff_line_count == diff_line:
                        return current_file_line

            return diff_line
        except Exception:
            return diff_line

    def _extract_issues_from_text(
        self, text: str, content: str, analysis_type: str = "full_file"
    ) -> List[CodeIssue]:
        """Extract issues from plain text response."""
        issues = []
        lines = text.split("\n")

        current_issue = {}  # type: ignore[var-annotated]
        for line in lines:
            line = line.strip()

            if any(
                keyword in line.lower()
                for keyword in ["issue", "problem", "warning", "error"]
            ):
                if current_issue:
                    issues.append(
                        self._create_issue_from_dict(
                            current_issue, content, analysis_type
                        )
                    )
                    current_issue = {}

                current_issue["description"] = line
                current_issue["type"] = self._determine_issue_type(line)
                current_issue["severity"] = self._determine_severity(line)

            elif line.startswith("Line") and ":" in line:
                try:
                    match = re.search(r"Line (\d+)", line)
                    if match:
                        line_num = int(match.group(1))
                        if analysis_type == "diff":
                            line_num = self._map_diff_line_to_file_line(
                                line_num, content
                            )
                        current_issue["line"] = line_num  # type: ignore[assignment]
                    else:
                        current_issue["line"] = 1  # type: ignore[assignment]
                except (AttributeError, ValueError):
                    current_issue["line"] = 1  # type: ignore[assignment]

            elif line.lower().startswith("suggestion") or line.lower().startswith(
                "fix"
            ):
                current_issue["suggestion"] = line

        if current_issue:
            issues.append(
                self._create_issue_from_dict(current_issue, content, analysis_type)
            )

        if not issues:
            description = f"Code {'diff' if analysis_type == 'diff' else 'file'} analysis completed"
            issues.append(
                CodeIssue(
                    type="analysis",
                    line=1,
                    description=description,
                    suggestion="Review the detailed analysis provided",
                    severity="low",
                )
            )

        return issues

    def _create_issue_from_dict(
        self, issue_dict: dict, content: str = "", analysis_type: str = "full_file"
    ) -> CodeIssue:
        """Create a CodeIssue from a dictionary."""
        line_number = issue_dict.get("line", 1)
        if analysis_type == "diff" and content:
            line_number = self._map_diff_line_to_file_line(line_number, content)

        return CodeIssue(
            type=issue_dict.get("type", "unknown"),
            line=line_number,
            description=issue_dict.get("description", "No description"),
            suggestion=issue_dict.get("suggestion", "No suggestion"),
            severity=issue_dict.get("severity", "medium"),
        )

    def _determine_issue_type(self, text: str) -> str:
        """Determine issue type from text."""
        text_lower = text.lower()
        if any(
            word in text_lower for word in ["security", "vulnerability", "injection"]
        ):
            return "security"
        elif any(word in text_lower for word in ["performance", "slow", "inefficient"]):
            return "performance"
        elif any(word in text_lower for word in ["bug", "error", "exception"]):
            return "bug"
        elif any(word in text_lower for word in ["style", "format", "convention"]):
            return "style"
        else:
            return "general"

    def _determine_severity(self, text: str) -> str:
        """Determine severity from text."""
        text_lower = text.lower()
        if any(word in text_lower for word in ["critical", "severe", "dangerous"]):
            return "critical"
        elif any(word in text_lower for word in ["high", "important", "major"]):
            return "high"
        elif any(word in text_lower for word in ["low", "minor", "trivial"]):
            return "low"
        else:
            return "medium"

    def analyze_pull_request(
        self, files_data: List[Dict], pr_info: Dict
    ) -> AnalysisResults:
        """Analyze all files in a pull request, focusing on diffs/changes."""
        logger.info(f"Starting analysis of PR #{pr_info.get('number', 'unknown')}")

        file_analyses = []
        languages_detected = set()

        for file_data in files_data:
            filename = file_data.get("filename", "")
            content = file_data.get("content", "")
            language = file_data.get("language", "text")
            patch = file_data.get("patch", "")
            diff = file_data.get("diff", "")

            if self._should_analyze_file(filename):
                languages_detected.add(language)

                analysis = self.analyze_file(
                    file_content=content,
                    filename=filename,
                    language=language,
                    diff=diff,
                    patch=patch,
                )
                file_analyses.append(analysis)

        total_issues = sum(len(fa.issues) for fa in file_analyses)
        critical_issues = sum(
            1
            for fa in file_analyses
            for issue in fa.issues
            if issue.severity == "critical"
        )
        high_issues = sum(
            1 for fa in file_analyses for issue in fa.issues if issue.severity == "high"
        )
        medium_issues = sum(
            1
            for fa in file_analyses
            for issue in fa.issues
            if issue.severity == "medium"
        )
        low_issues = sum(
            1 for fa in file_analyses for issue in fa.issues if issue.severity == "low"
        )

        summary = AnalysisSummary(
            total_files=len(file_analyses),
            total_issues=total_issues,
            critical_issues=critical_issues,
            high_issues=high_issues,
            medium_issues=medium_issues,
            low_issues=low_issues,
            languages_detected=list(languages_detected),
        )

        recommendations = self._generate_recommendations(file_analyses, summary)

        return AnalysisResults(
            files=file_analyses, summary=summary, recommendations=recommendations
        )

    def _should_analyze_file(self, filename: str) -> bool:
        """Determine if a file should be analyzed."""
        # Skip binary files, images, and other non-code files
        skip_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".ico",
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".zip",
            ".tar",
            ".gz",
            ".rar",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".min.js",
            ".min.css",
        }

        skip_patterns = {
            "node_modules/",
            "vendor/",
            ".git/",
            "__pycache__/",
            ".pytest_cache/",
            "coverage/",
            "dist/",
            "build/",
        }

        filename_lower = filename.lower()

        for ext in skip_extensions:
            if filename_lower.endswith(ext):
                return False

        for pattern in skip_patterns:
            if pattern in filename_lower:
                return False

        return True

    def _generate_recommendations(
        self, file_analyses: List[FileAnalysis], summary: AnalysisSummary
    ) -> List[str]:
        """Generate high-level recommendations based on analysis results."""
        recommendations = []

        if summary.critical_issues > 0:
            recommendations.append(
                f"🚨 Address {summary.critical_issues} critical security/bug issues immediately"
            )

        if summary.high_issues > 0:
            recommendations.append(
                f"⚠️ Review {summary.high_issues} high-priority issues before merging"
            )

        if summary.total_issues > 20:
            recommendations.append(
                "📊 Consider breaking this PR into smaller, more focused changes"
            )

        # Language-specific recommendations
        if "python" in summary.languages_detected:
            recommendations.append(
                "🐍 Consider running black, flake8, and mypy for Python code quality"
            )

        if (
            "javascript" in summary.languages_detected
            or "typescript" in summary.languages_detected
        ):
            recommendations.append(
                "📦 Consider using ESLint and Prettier for JavaScript/TypeScript code"
            )

        if not recommendations:
            recommendations.append("✅ Code looks good! No major issues detected")

        return recommendations
