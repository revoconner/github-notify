import logging
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal, Slot

from .github import GitHubClient
from .filters import (
    owned_non_fork_set,
    filter_issues,
    filter_prs,
    is_hidden_bot,
    subject_key,
    build_issue_query,
    build_pr_query,
    item_key,
)

log = logging.getLogger(__name__)


class PollWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._busy = False

    @Slot(str, dict, list, dict)
    def do_poll(self, token, settings, seen_list, seen_updated_at):
        if self._busy:
            log.info("poll already running, skipping")
            return
        self._busy = True
        client = None
        try:
            seen = set(seen_list)
            client = GitHubClient(token)
            me = client.get_me()
            login = me["login"]

            repos = client.list_owned_repos()
            non_fork = owned_non_fork_set(repos, login)

            issue_state = settings.get("issue_state", "open")
            pr_state = settings.get("pr_state", "open")
            show_bots = bool(settings.get("show_bots", False))
            bot_allowlist = settings.get("bot_allowlist", ["claude[bot]"])
            notify_scope = settings.get("notify_scope", "owned")
            flag_first_sight = bool(settings.get("flag_first_sight", False))

            issues_raw = client.search(build_issue_query(login, issue_state))
            prs_raw = client.search(build_pr_query(login, pr_state))

            issues = filter_issues(issues_raw, non_fork, show_bots, bot_allowlist)
            prs = filter_prs(prs_raw, non_fork, show_bots, bot_allowlist)

            activity_by_subject = {}
            new_seen_updated_at = {}
            poll_interval = 60
            notifications_error = None
            seen_now = set(seen)

            if notify_scope == "watched":
                # /notifications-driven: respects GitHub watch settings.
                since_iso = settings.get("last_poll_iso")
                notifications = []
                try:
                    notifications, poll_interval = client.list_notifications(since_iso)
                except Exception as e:
                    notifications_error = str(e)
                    log.warning("notifications fetch failed: %s", e)

                for n in notifications:
                    nid = n.get("id")
                    if not nid or nid in seen_now:
                        continue
                    seen_now.add(nid)
                    subject = n.get("subject") or {}
                    subject_url = subject.get("url")
                    if not subject_url:
                        continue
                    # Bot check on the latest comment author.
                    if n.get("reason") == "comment" and not show_bots:
                        comment_url = subject.get("latest_comment_url")
                        if comment_url:
                            try:
                                payload = client.get_url(comment_url)
                                if is_hidden_bot(payload.get("user"), show_bots, bot_allowlist):
                                    continue
                            except Exception as e:
                                log.warning("comment fetch failed: %s", e)
                    key = subject_key(subject_url)
                    if not key:
                        continue
                    activity_by_subject.setdefault(key, []).append({
                        "updated_at": n.get("updated_at"),
                    })
            else:
                # owned: track per-item updated_at deltas across all displayed items.
                current_keys = set()
                for it in issues + prs:
                    key = item_key(it)
                    current_keys.add(key)
                    current_ts = it.get("updated_at") or ""
                    prev_ts = seen_updated_at.get(key)
                    if prev_ts is None:
                        # First time seeing this item: normally just record a baseline,
                        # but flag_first_sight (testing) treats it as new activity too.
                        if flag_first_sight:
                            activity_by_subject.setdefault(key, []).append({
                                "updated_at": current_ts,
                            })
                        new_seen_updated_at[key] = current_ts
                        continue
                    if current_ts > prev_ts:
                        activity_by_subject.setdefault(key, []).append({
                            "updated_at": current_ts,
                        })
                    new_seen_updated_at[key] = current_ts

            self.finished.emit({
                "issues": issues,
                "prs": prs,
                "activity_by_subject": activity_by_subject,
                "seen_ids": list(seen_now),
                "seen_updated_at": new_seen_updated_at if notify_scope == "owned" else None,
                "poll_interval": poll_interval,
                "now_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "notifications_error": notifications_error,
                "notify_scope": notify_scope,
            })
        except Exception as e:
            log.exception("poll failed")
            self.error.emit(str(e))
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            self._busy = False
