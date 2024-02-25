import requests
import zipfile
import os
from datetime import datetime
import base64
import shutil
import time

def build_commit_message(message):
    now = datetime.now()
    return f'[{now.strftime("%d/%m/%Y, %H:%M:%S")}] {message}'

def download_crx(extension_id, output_path):
    api_url = f"https://clients2.google.com/service/update2/crx?response=redirect&prodversion=49.0&acceptformat=crx3&x=id%3D{extension_id}%26installsource%3Dondemand%26uc"

    USER_AGENT = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://chrome.google.com",
    }

    try:
        response = requests.get(api_url, allow_redirects=True, headers=headers)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"CRX file downloaded successfully to {output_path}")
        else:
            print(f"Failed to download CRX file. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error occurred: {str(e)}")

def print_response_error(response):
    try:
        error_message = response.json().get('message', 'Unknown error')
    except json.JSONDecodeError:
        error_message = response.text
    print(f"Failed with status code {response.status_code}: {error_message}")

def rebase_and_push(github_token, repo_owner, repo_name, branch_name, commit_sha):
    base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    branch_url = f"{base_url}/git/refs/heads/{branch_name}"

    # Fetch the latest changes from the branch
    response = requests.get(
        branch_url,
        headers={"Authorization": f"token {github_token}"}
    )

    if response.status_code == 200:
        latest_commit_sha = response.json()["object"]["sha"]
        payload = {
            "base": latest_commit_sha,
            "head": commit_sha,
            "commit_message": build_commit_message(f"Automatic rebase :: {os.environ['EXTENSION_ID']}")
        }
        rebase_url = f"{base_url}/git/rebases"
        rebase_response = requests.post(
            rebase_url,
            headers={"Authorization": f"token {github_token}"},
            json=payload
        )

        if rebase_response.status_code == 200:
            print("Rebase successful.")
            # Update the branch reference
            update_branch_url = f"{base_url}/git/refs/heads/{branch_name}"
            update_payload = {
                "sha": commit_sha,
                "force": False  # Don't force update
            }
            update_response = requests.patch(
                update_branch_url,
                headers={"Authorization": f"token {github_token}"},
                json=update_payload
            )
            if update_response.status_code == 200:
                print(f"Branch '{branch_name}' updated successfully.")
            else:
                print(f"Failed to update branch '{branch_name}': {update_response.status_code}")
        else:
            print(f"Rebase failed: {rebase_response.status_code}")
    else:
        print(f"Failed to fetch branch '{branch_name}': {response.status_code}")

def merge_and_push(github_token, repo_owner, repo_name, branch_name, commit_sha):
    base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    merge_url = f"{base_url}/merges"

    payload = {
        "base": branch_name,
        "head": commit_sha,
        "commit_message": build_commit_message(f"Automatic merge :: {os.environ['EXTENSION_ID']}")
    }

    merge_response = requests.post(
        merge_url,
        headers={"Authorization": f"token {github_token}"},
        json=payload
    )

    if merge_response.status_code == 201:
        print("Merge successful.")
        # No need to update branch reference, merge operation does it automatically
    else:
        print(f"Merge failed: {merge_response.status_code}")

def create_tree(repo_owner, repo_name, github_token, path, commit_message, branch_name="master"):
    base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    tree_url = f"{base_url}/git/trees"

    # Create a tree object
    tree = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            with open(file_path, 'rb') as f:  # Open in binary mode
                content = f.read()
            content_encoded = base64.b64encode(content).decode('utf-8')  # Base64 encode
            tree.append({
                "path": file_path.replace(path, "").lstrip("/"),
                "mode": "100644",
                "type": "blob",
                "content": content_encoded
            })

    # Create a new tree on GitHub
    response = requests.post(
        tree_url,
        headers={"Authorization": f"token {github_token}"},
        json={"tree": tree, "base_tree": None}
    )

    if response.status_code == 201:
        tree_sha = response.json()["sha"]
        # Create a new commit
        commit_url = f"{base_url}/git/commits"
        commit_payload = {
            "message": commit_message,
            "tree": tree_sha
        }
        commit_response = requests.post(
            commit_url,
            headers={"Authorization": f"token {github_token}"},
            json=commit_payload
        )
        if commit_response.status_code == 201:
            commit_sha = commit_response.json()["sha"]
            # Attempt to merge and push the changes
            merge_and_push(github_token, repo_owner, repo_name, branch_name, commit_sha)
        else:
            print_response_error(commit_response)
    else:
        print_response_error(response)

while True:
    download_crx(os.environ['EXTENSION_ID'], "downloaded_extension.crx")

    with zipfile.ZipFile("downloaded_extension.crx","r") as zip_ref:
        zip_ref.extractall("extension_unpacked")

    print("Extension successfully unpacked.")

    print("Committing to the repository")

    now = datetime.now()

    create_tree(os.environ['REPO_OWNER'], os.environ['REPO_NAME'], os.environ['GITHUB_TOKEN'], './extension_unpacked', build_commit_message(f"Automatic update :: {os.environ['EXTENSION_ID']}"), os.environ['REPO_BRANCH'])

    print("Cleaning up...")
    shutil.rmtree("./extension_unpacked")
    os.unlink("downloaded_extension.crx")

    print("Waiting for an hour to merge another version...")
    time.sleep(60 * 60)