"""
One-time setup script: creates the Databricks secret scope. Run this locally (with the Databricks CLI configured) or
from a notebook - never commit the resulting secret value anywhere.

Usage:
    python setup_secrets.py
"""
import getpass

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import ResourceAlreadyExists
from databricks.sdk.service import workspace

w = WorkspaceClient()

# Principal (service principal application ID, or workspace group name) that
# the app runs as. Only this principal gets read access to the secret -
# NOT the built-in "users" group, since the secret contains the full
# Lakebase URL including the plaintext Postgres password.
APP_PRINCIPAL = "<app-service-principal-or-group>"

try:
    w.secrets.create_scope(scope="database")
except ResourceAlreadyExists:
    print("Scope 'database' already exists, skipping creation.")

w.secrets.put_secret(
    scope="database",
    key="lakebase-url",
    string_value=getpass.getpass("Paste your Lakebase URL: ")
)

w.secrets.put_acl(
    scope="database",
    principal=APP_PRINCIPAL,
    permission=workspace.AclPermission.READ,
)