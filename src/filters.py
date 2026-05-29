def is_bot(user: dict) -> bool:
    if not user:
        return False
    if user.get("type") == "Bot":
        return True
    return str(user.get("login", "")).endswith("[bot]")


def is_hidden_bot(user: dict, show_bots: bool, allowlist) -> bool:
    # Bots are hidden when show_bots is False, except for the allowlist.
    if show_bots:
        return False
    if not is_bot(user):
        return False
    return user.get("login") not in set(allowlist or [])


def owned_non_fork_set(repos: list, login: str) -> set:
    return {
        r["full_name"]
        for r in repos
        if r["owner"]["login"] == login and not r.get("fork")
    }


def repo_full_from_url(repository_url: str) -> str:
    return repository_url.replace("https://api.github.com/repos/", "")


def subject_key(subject_url: str):
    tail = subject_url.replace("https://api.github.com/repos/", "")
    parts = tail.split("/")
    if len(parts) >= 4:
        return f"{parts[0]}/{parts[1]}#{parts[3]}"
    return None


def filter_issues(items, non_fork_set, show_bots, allowlist):
    out = []
    for it in items:
        if it.get("pull_request"):
            continue
        repo_full = repo_full_from_url(it["repository_url"])
        if repo_full not in non_fork_set:
            continue
        if is_hidden_bot(it.get("user"), show_bots, allowlist):
            continue
        out.append(it)
    return out


def filter_prs(items, non_fork_set, show_bots, allowlist):
    out = []
    for it in items:
        if not it.get("pull_request"):
            continue
        repo_full = repo_full_from_url(it["repository_url"])
        if repo_full not in non_fork_set:
            continue
        if is_hidden_bot(it.get("user"), show_bots, allowlist):
            continue
        out.append(it)
    return out


def build_issue_query(login: str, issue_state: str) -> str:
    # issue_state: open | closed | all
    base = f"is:issue user:{login} sort:updated-desc"
    if issue_state == "open":
        return f"{base} is:open"
    if issue_state == "closed":
        return f"{base} is:closed"
    return base


def build_pr_query(login: str, pr_state: str) -> str:
    # pr_state: open | draft | open_draft | closed | all
    base = f"is:pr user:{login} sort:updated-desc"
    if pr_state == "draft":
        return f"{base} is:open is:draft"
    if pr_state == "open_draft":
        return f"{base} is:open"
    if pr_state == "closed":
        return f"{base} is:closed"
    if pr_state == "all":
        return base
    return f"{base} is:open -is:draft"


def item_key(item) -> str:
    repo_full = repo_full_from_url(item["repository_url"])
    return f"{repo_full}#{item['number']}"
