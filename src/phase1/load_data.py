"""
Load GH Archive JSON files into PostgreSQL.

This is an ETL (Extract-Transform-Load) script:
- Extract: read gzipped JSON lines from GH Archive files
- Transform: normalize flat JSON into relational records (deduplicate
  actors/repos/orgs, extract typed payload fields)
- Load: insert into PostgreSQL tables

Usage:
    python src/phase1/load_data.py --db ghchat

This loads all .json.gz files found in data/.
"""

import argparse
import gzip
import json
import os
import glob
import sys
import time
import psycopg2
from psycopg2.extras import execute_values

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "sql", "create_schema.sql")

BATCH_SIZE = 5000


def safe_get(d, *keys, default=None):
    """Safely traverse nested dicts."""
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
        else:
            return default
    return d if d is not None else default


def parse_event(raw: dict) -> dict | None:
    """Parse a raw GH Archive JSON event into structured records."""
    try:
        event_id = int(raw["id"])
    except (KeyError, ValueError, TypeError):
        return None

    actor = raw.get("actor") or {}
    repo = raw.get("repo") or {}
    org = raw.get("org")
    payload = raw.get("payload") or {}
    event_type = raw.get("type", "")
    created_at = raw.get("created_at")

    result = {
        "event": {
            "id": event_id,
            "type": event_type,
            "actor_id": actor.get("id"),
            "repo_id": repo.get("id"),
            "org_id": org.get("id") if org else None,
            "created_at": created_at,
        },
        "actor": {
            "id": actor.get("id"),
            "login": actor.get("login", ""),
            "avatar_url": actor.get("avatar_url"),
        },
        "repo": {
            "id": repo.get("id"),
            "name": repo.get("name", ""),
        },
    }

    if org:
        result["org"] = {
            "id": org.get("id"),
            "login": org.get("login", ""),
            "avatar_url": org.get("avatar_url"),
        }

    if event_type == "PushEvent":
        result["push"] = {
            "event_id": event_id,
            "push_id": payload.get("push_id"),
            "size": payload.get("size", 0),
            "distinct_size": payload.get("distinct_size", 0),
            "ref": payload.get("ref"),
        }
    elif event_type == "PullRequestEvent":
        pr = payload.get("pull_request") or {}
        result["pull_request"] = {
            "event_id": event_id,
            "action": payload.get("action"),
            "pr_number": payload.get("number"),
            "pr_title": pr.get("title"),
            "pr_state": pr.get("state"),
            "pr_merged": pr.get("merged"),
            "pr_additions": pr.get("additions"),
            "pr_deletions": pr.get("deletions"),
            "pr_changed_files": pr.get("changed_files"),
            "pr_created_at": pr.get("created_at"),
            "pr_merged_at": pr.get("merged_at"),
            "pr_closed_at": pr.get("closed_at"),
        }
    elif event_type == "IssuesEvent":
        issue = payload.get("issue") or {}
        labels = issue.get("labels") or []
        result["issue"] = {
            "event_id": event_id,
            "action": payload.get("action"),
            "issue_number": issue.get("number"),
            "issue_title": issue.get("title"),
            "issue_state": issue.get("state"),
            "issue_labels": json.dumps([l.get("name") for l in labels]),
            "issue_created_at": issue.get("created_at"),
            "issue_closed_at": issue.get("closed_at"),
        }
    elif event_type == "IssueCommentEvent":
        comment = payload.get("comment") or {}
        issue = payload.get("issue") or {}
        result["issue_comment"] = {
            "event_id": event_id,
            "action": payload.get("action"),
            "issue_number": issue.get("number"),
            "comment_body": (comment.get("body") or "")[:10000],
            "comment_created_at": comment.get("created_at"),
        }
    elif event_type == "WatchEvent":
        result["watch"] = {
            "event_id": event_id,
            "action": payload.get("action"),
        }
    elif event_type == "ForkEvent":
        forkee = payload.get("forkee") or {}
        result["fork"] = {
            "event_id": event_id,
            "fork_id": forkee.get("id"),
            "fork_full_name": forkee.get("full_name"),
        }
    elif event_type == "CreateEvent":
        result["create"] = {
            "event_id": event_id,
            "ref_type": payload.get("ref_type"),
            "ref": payload.get("ref"),
            "master_branch": payload.get("master_branch"),
        }
    elif event_type == "ReleaseEvent":
        release = payload.get("release") or {}
        result["release"] = {
            "event_id": event_id,
            "action": payload.get("action"),
            "tag_name": release.get("tag_name"),
            "release_name": release.get("name"),
        }

    return result


def create_database(db_name: str, host: str, port: int, user: str, password: str):
    """Create the database if it doesn't exist."""
    conn = psycopg2.connect(
        host=host, port=port, user=user, password=password, dbname="postgres"
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{db_name}"')
        print(f"Created database: {db_name}")
    else:
        print(f"Database already exists: {db_name}")
    cur.close()
    conn.close()


def create_schema(conn):
    """Run the schema creation SQL."""
    with open(SCHEMA_FILE, "r") as f:
        sql = f.read()
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    print("Schema created/verified.")


def flush_batch(conn, actors, repos, orgs, events,
                pushes, pull_requests, issues, issue_comments,
                watches, forks, creates, releases, created_at_map):
    """Insert a batch of parsed records into PostgreSQL using bulk inserts."""
    cur = conn.cursor()

    if actors:
        execute_values(cur, """
            INSERT INTO actors (id, login, avatar_url, first_seen, last_seen)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                login = EXCLUDED.login,
                last_seen = GREATEST(actors.last_seen, EXCLUDED.last_seen)
        """, [(a["id"], a["login"], a["avatar_url"],
               created_at_map.get(a["id"]), created_at_map.get(a["id"]))
              for a in actors.values() if a["id"] is not None])

    if repos:
        execute_values(cur, """
            INSERT INTO repos (id, name, first_seen, last_seen)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                last_seen = GREATEST(repos.last_seen, EXCLUDED.last_seen)
        """, [(r["id"], r["name"],
               created_at_map.get(r["id"]), created_at_map.get(r["id"]))
              for r in repos.values() if r["id"] is not None])

    if orgs:
        execute_values(cur, """
            INSERT INTO orgs (id, login, avatar_url) VALUES %s
            ON CONFLICT (id) DO UPDATE SET login = EXCLUDED.login
        """, [(o["id"], o["login"], o["avatar_url"])
              for o in orgs.values() if o["id"] is not None])

    if events:
        execute_values(cur, """
            INSERT INTO events (id, type, actor_id, repo_id, org_id, created_at)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, [(e["id"], e["type"], e["actor_id"], e["repo_id"],
               e["org_id"], e["created_at"]) for e in events])

    if pushes:
        execute_values(cur, """
            INSERT INTO push_events (event_id, push_id, size, distinct_size, ref)
            VALUES %s ON CONFLICT (event_id) DO NOTHING
        """, [(p["event_id"], p["push_id"], p["size"],
               p["distinct_size"], p["ref"]) for p in pushes])

    if pull_requests:
        execute_values(cur, """
            INSERT INTO pull_request_events
            (event_id, action, pr_number, pr_title, pr_state, pr_merged,
             pr_additions, pr_deletions, pr_changed_files,
             pr_created_at, pr_merged_at, pr_closed_at)
            VALUES %s ON CONFLICT (event_id) DO NOTHING
        """, [(p["event_id"], p["action"], p["pr_number"], p["pr_title"],
               p["pr_state"], p["pr_merged"], p["pr_additions"],
               p["pr_deletions"], p["pr_changed_files"],
               p["pr_created_at"], p["pr_merged_at"], p["pr_closed_at"])
              for p in pull_requests])

    if issues:
        execute_values(cur, """
            INSERT INTO issue_events
            (event_id, action, issue_number, issue_title, issue_state,
             issue_labels, issue_created_at, issue_closed_at)
            VALUES %s ON CONFLICT (event_id) DO NOTHING
        """, [(i["event_id"], i["action"], i["issue_number"], i["issue_title"],
               i["issue_state"], i["issue_labels"],
               i["issue_created_at"], i["issue_closed_at"]) for i in issues])

    if issue_comments:
        execute_values(cur, """
            INSERT INTO issue_comment_events
            (event_id, action, issue_number, comment_body, comment_created_at)
            VALUES %s ON CONFLICT (event_id) DO NOTHING
        """, [(c["event_id"], c["action"], c["issue_number"],
               c["comment_body"], c["comment_created_at"])
              for c in issue_comments])

    if watches:
        execute_values(cur, """
            INSERT INTO watch_events (event_id, action)
            VALUES %s ON CONFLICT (event_id) DO NOTHING
        """, [(w["event_id"], w["action"]) for w in watches])

    if forks:
        execute_values(cur, """
            INSERT INTO fork_events (event_id, fork_id, fork_full_name)
            VALUES %s ON CONFLICT (event_id) DO NOTHING
        """, [(f["event_id"], f["fork_id"], f["fork_full_name"]) for f in forks])

    if creates:
        execute_values(cur, """
            INSERT INTO create_events (event_id, ref_type, ref, master_branch)
            VALUES %s ON CONFLICT (event_id) DO NOTHING
        """, [(c["event_id"], c["ref_type"], c["ref"], c["master_branch"])
              for c in creates])

    if releases:
        execute_values(cur, """
            INSERT INTO release_events (event_id, action, tag_name, release_name)
            VALUES %s ON CONFLICT (event_id) DO NOTHING
        """, [(r["event_id"], r["action"], r["tag_name"], r["release_name"])
              for r in releases])

    conn.commit()
    cur.close()


def load_file(conn, filepath: str):
    """Load a single GH Archive gzipped JSON file into the database."""
    filename = os.path.basename(filepath)
    print(f"\nLoading: {filename}")

    actors, repos, orgs = {}, {}, {}
    events_batch = []
    pushes, pull_requests, issues = [], [], []
    issue_comments, watches, forks = [], [], []
    creates, releases = [], []
    created_at_map = {}

    total_lines = 0
    total_loaded = 0
    parse_errors = 0
    start = time.time()

    with gzip.open(filepath, "rt", encoding="utf-8") as f:
        for line in f:
            total_lines += 1
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue

            parsed = parse_event(raw)
            if not parsed:
                parse_errors += 1
                continue

            total_loaded += 1

            a = parsed["actor"]
            if a["id"] is not None:
                actors[a["id"]] = a
                created_at_map[a["id"]] = parsed["event"]["created_at"]

            r = parsed["repo"]
            if r["id"] is not None:
                repos[r["id"]] = r
                created_at_map[r["id"]] = parsed["event"]["created_at"]

            if "org" in parsed:
                o = parsed["org"]
                if o["id"] is not None:
                    orgs[o["id"]] = o

            events_batch.append(parsed["event"])

            if "push" in parsed:
                pushes.append(parsed["push"])
            elif "pull_request" in parsed:
                pull_requests.append(parsed["pull_request"])
            elif "issue" in parsed:
                issues.append(parsed["issue"])
            elif "issue_comment" in parsed:
                issue_comments.append(parsed["issue_comment"])
            elif "watch" in parsed:
                watches.append(parsed["watch"])
            elif "fork" in parsed:
                forks.append(parsed["fork"])
            elif "create" in parsed:
                creates.append(parsed["create"])
            elif "release" in parsed:
                releases.append(parsed["release"])

            if total_loaded % BATCH_SIZE == 0:
                flush_batch(conn, actors, repos, orgs, events_batch,
                           pushes, pull_requests, issues, issue_comments,
                           watches, forks, creates, releases, created_at_map)
                actors, repos, orgs = {}, {}, {}
                events_batch = []
                pushes, pull_requests, issues = [], [], []
                issue_comments, watches, forks = [], [], []
                creates, releases = [], []
                created_at_map = {}
                elapsed = time.time() - start
                rate = total_loaded / elapsed if elapsed > 0 else 0
                print(f"\r  {total_loaded:,} events loaded ({rate:,.0f} events/sec)", end="")

    # Flush remaining
    if events_batch:
        flush_batch(conn, actors, repos, orgs, events_batch,
                   pushes, pull_requests, issues, issue_comments,
                   watches, forks, creates, releases, created_at_map)

    elapsed = time.time() - start
    print(f"\r  {filename}: {total_loaded:,} events loaded, "
          f"{parse_errors} errors, {elapsed:.1f}s")


def print_summary(conn):
    """Print row counts for all tables."""
    cur = conn.cursor()
    tables = [
        "actors", "repos", "orgs", "events",
        "push_events", "pull_request_events", "issue_events",
        "issue_comment_events", "watch_events", "fork_events",
        "create_events", "release_events",
    ]
    print("\n--- Database Summary ---")
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table:30s} {count:>10,} rows")
    cur.close()


def main():
    parser = argparse.ArgumentParser(description="Load GH Archive data into PostgreSQL")
    parser.add_argument("--db", default="ghchat", help="Database name (default: ghchat)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--password", default="postgres", help="PostgreSQL password")
    args = parser.parse_args()

    gz_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json.gz")))
    if not gz_files:
        print(f"No .json.gz files found in {os.path.abspath(DATA_DIR)}")
        print("Run download_data.py first.")
        sys.exit(1)

    print(f"Found {len(gz_files)} file(s) to load.")

    create_database(args.db, args.host, args.port, args.user, args.password)

    conn = psycopg2.connect(
        host=args.host, port=args.port,
        user=args.user, password=args.password,
        dbname=args.db,
    )
    create_schema(conn)

    for gz_file in gz_files:
        load_file(conn, gz_file)

    print_summary(conn)
    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
