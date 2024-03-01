import requests
import zipfile
import os
from datetime import datetime
import base64
import shutil
import time
import git

def build_commit_message(message):
    now = datetime.now()
    return f'[{now.strftime("%d/%m/%Y, %H:%M:%S")}] {message}\n\n\non-behalf-of: @{os.environ["REPO_OWNER"]}'

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

while True:
    download_crx(os.environ['EXTENSION_ID'], "downloaded_extension.crx")

    if os.path.exists('extension_unpacked'):
        shutil.rmtree("./extension_unpacked")
        print("Removed unintentional junk")

    repo_local = git.Repo.clone_from(f'https://NekoPavel:{os.environ["GITHUB_TOKEN"]}@github.com/{os.environ["REPO_OWNER"]}/{os.environ["REPO_NAME"]}.git', 'extension_unpacked')

    repo_local.git.config('user.name', 'GoogleThing')
    repo_local.git.config('user.email', 'thing@google.com')


    with zipfile.ZipFile("downloaded_extension.crx","r") as zip_ref:
        zip_ref.extractall("extension_unpacked")

    print("Extension successfully unpacked.")

    try:
        for root, dirs, files in os.walk('./extension_unpacked'):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, start='./extension_unpacked')
                repo_local.git.add(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extension_unpacked', relative_path))

        print("Committing to the repository")
        repo_local.git.commit(m=build_commit_message(f"Automatic update :: {os.environ['EXTENSION_ID']}"))
        repo_local.git.push('origin', os.environ['REPO_BRANCH']) 
    except Exception as e:
        print(f"GIT: {e}")
    print("Cleaning up...")
    shutil.rmtree("./extension_unpacked")
    os.unlink("downloaded_extension.crx")

    print("Waiting for an hour to merge another version...")
    time.sleep(60 * 60)