import os
import json
import requests
from github import Github
import openai

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")

# Authenticate with GitHub using the token
github = Github(GITHUB_TOKEN)

def get_pr_details(event_path):
    with open(event_path, "r") as f:
        event_data = json.load(f)

    repository = event_data["repository"]
    pull_request = event_data["number"]

    print(f"Repository: {repository['full_name']}")
    print(f"Pull Request Number: {pull_request}")

    try:
        pr = github.get_repo(repository["full_name"]).get_pull(pull_request)
    except Exception as e:
        print(f"Error retrieving pull request: {e}")
        raise

    return {
        "owner": repository["owner"]["login"],
        "repo": repository["name"],
        "pull_number": pull_request,
        "title": pr.title,
        "description": pr.body or ""
    }


def get_diff(owner, repo, pull_number):
    repo = github.get_repo(f"{owner}/{repo}")
    pr = repo.get_pull(pull_number)
    diff = pr.get_files()
    return diff

def analyze_code(diff, pr_details):
    comments = []
    for file in diff:
        if file.status == 'removed':
            continue
        # Assume Azure OpenAI API call for code review:
        prompt = create_prompt(file, pr_details)
        ai_response = get_ai_response(prompt)
        if ai_response:
            comments.append(create_comment(file, ai_response))
    return comments

def create_prompt(file, pr_details):
    return f"""Your task is to review pull requests...
    Title: {pr_details['title']}
    Description: {pr_details['description']}
    Diff to review: {file.patch}"""

def get_ai_response(prompt):
    headers = {
        "api-key": OPENAI_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": prompt,
        "model": OPENAI_MODEL,
        "max_tokens": 700,
        "temperature": 0.2
    }

    response = requests.post(f"{OPENAI_ENDPOINT}/openai/deployments/{OPENAI_MODEL}/completions", headers=headers, json=payload)
    result = response.json()
    return result.get("choices", [])[0].get("text")

def create_comment(file, ai_response):
    return {
        "path": file.filename,
        "body": ai_response,
        "line": file.patch.splitlines()[0]  # Example: just taking the first line as the target
    }

def create_review_comment(owner, repo, pull_number, comments):
    pr = github.get_repo(f"{owner}/{repo}").get_pull(pull_number)
    for comment in comments:
        pr.create_review_comment(comment["body"], comment["path"], comment["line"])

if __name__ == "__main__":
    event_path = os.getenv("GITHUB_EVENT_PATH")
    print(event_path)
    pr_details = get_pr_details(event_path)
    diff = get_diff(pr_details["owner"], pr_details["repo"], pr_details["pull_number"])
    create_review_comment(pr_details["owner"], pr_details["repo"], pr_details["pull_number"], diff)
    #comments = analyze_code(diff, pr_details)
    #if comments:
    #    create_review_comment(pr_details["owner"], pr_details["repo"], pr_details["pull_number"], comments)
