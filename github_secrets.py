def update_org_repos_secrets(
    org_name: str, github_token: str, secrets: dict, test_mode=True, limit_repos=None
):
    from github import Github, Auth
    import requests, base64, nacl.public

    g = Github(auth=Auth.Token(github_token))
    org = g.get_organization(org_name)

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    def encrypt_secret(public_key: str, secret_value: str) -> str:
        public_key_bytes = base64.b64decode(public_key)
        sealed_box = nacl.public.SealedBox(nacl.public.PublicKey(public_key_bytes))
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    def update_repo_secrets(repo_name: str, secrets: dict):
        print(f"\nUpdating secrets for repository: {repo_name}")
        key_url = f"https://api.github.com/repos/{org_name}/{repo_name}/actions/secrets/public-key"
        r = requests.get(key_url, headers=headers)
        if r.status_code != 200:
            print(
                f"Failed to fetch public key for {repo_name}: {r.status_code}-{r.text}"
            )
            return
        key_data = r.json()
        public_key = key_data["key"]
        key_id = key_data["key_id"]

        for name, value in secrets.items():
            encrypted_value = encrypt_secret(public_key, value)
            if test_mode:
                print(f"[Test mode] would update '{name}' in {repo_name}")
            else:
                secret_url = f"https://api.github.com/repos/{org_name}/{repo_name}/actions/secrets/{name}"
                payload = {"encrypted_value": encrypted_value, "key_id": key_id}
                r = requests.put(secret_url, headers=headers, json=payload)
                if r.status_code in (201, 204):
                    print(f"Secret '{name}' updated successfully in {repo_name}")
                else:
                    print(f"Failed to update secret '{name}': {r.status_code}-{r.text}")

    repos = org.get_repos()
    if limit_repos:
        repos = list(repos)[:limit_repos]

    for repo in repos:
        update_repo_secrets(repo.name, secrets)
