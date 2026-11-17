"""The planning tier's read-only database login, generated from PostgreSQL's own catalog (process/factory.md,
D3 rule 3). Works for any stack: it reads the database, not an ORM's models.

Usage (standard library only; run with python3 -I):

    python3 -I planning_reader.py catalog-query
    python3 -I planning_reader.py update --catalog <catalog.json|-> --rules <rules.json> --out <dir>
    python3 -I planning_reader.py check  --catalog <catalog.json|-> --rules <rules.json> --out <dir>

catalog-query prints one read-only SELECT whose single JSON value is the catalog. Save it with
    psql "$DATABASE_URL" -At -c "$(python3 -I planning_reader.py catalog-query)" > catalog.json
check compares bytes, so update and check must read the same kind of database: the one CI migrates
from scratch is the usual choice (or commit the catalog beside the listing). Production's own catalog
can differ from it by an extension's objects in a granted schema. Nothing in the catalog names the
database, and a type's schema prefix (which depends on the session's search_path) is dropped from the
listing, so those never differ. The query lists every non-system schema
(not pg_*, not information_schema), and in each its ordinary and partitioned tables, views, materialized
views and foreign tables. A partition isn't listed: queries read it through its parent, which is what
gets the grant (the partition gets none). Each column carries its declared type, its base type (one
domain unwrapped), the varchar/char length, nullability, identity, whether it's generated and from
which columns, and the columns its foreign keys reference; each relation carries its primary key.

update classifies every column, writes <dir>/columns.json (the listing), <dir>/create_role.sql and
<dir>/verify_role.sql, and prints NEW (a column not in the previous listing), CHANGED (its class moved)
and GONE lines. check builds the same three files in memory and exits 1 when a file on disk differs
or is missing, printing NEW for each catalog column the listing on disk lacks: a project's CI runs it
after its migrations, so a migration that adds a column fails until its author reruns update and CD
reviews the diff. Both print the schemas the rules leave out (they get nothing; they're not in the
listing, since a production database and CI's differ there). Exit 2 is a bad rules file, catalog or
listing (the message says which entry).

The rules file (hand-written, CODEOWNERS-protected; CD reviews it and every generated diff):

    {
      "_doc": "optional free text",
      "role": "factory_reader",                 the login; planning.json's database.user
      "database": "app",                        create_role.sql refuses to run on any other database
      "schemas": ["public"],                    schemas the login reads (USAGE, and its search_path)
      "statement_timeout": "15s",               ms, s, min or h; a default the role can SET away
      "temp_file_limit": "1GB",                 kB, MB, GB or TB (0 = no temp files); only a superuser can lift it
      "connection_limit": 8,                    4 per planning job (pgbouncer's pool) times the planning runners
      "app_roles": ["app"],                     optional: non-superuser roles that get back what PUBLIC loses
      "overrides": {                            optional: CD's decisions, each with a one-line reason
        "public.orders.total_cents": {"class": "allow", "reason": "Order totals; no card or account data."},
        "public.sessions.*": {"class": "exclude-credential", "reason": "Login sessions."}
      },
      "derivations": {                          optional: a column built from others the catalog can't see
        "public.documents.summary": ["public.documents.body"]
      }
    }

Classes: allow; exclude-personal, exclude-credential, exclude-payment and exclude-content (free text or
derived data that may hold captured secrets or someone's words) are decided exclusions; review is
undecided and excluded until CD decides, and only the heuristics give it: an override can't. Only allow
is granted. A "schema.table.*" override sets every column of the table that has no override of its
own, and may only exclude. An override or derivation naming a column the catalog lacks is an error, so
a stale one can't linger. A reason starting "AUTO:" was written by this tool, not by a person.

Classification, first match wins (names are matched in snake case, so UserId reads as user_id, and the
names of a column's domain or enum type count too):
 1. the column's override, then its table's "*" override;
 2. a name that looks like a credential, payment data or personal data: that exclude class;
    a generated column whose source columns the catalog didn't name: review;
 3. a column of a payment-looking table (payment, invoice, billing, charge, refund, payout,
    subscription), other than its integer or uuid primary key: review;
 4. a foreign key: allow when every column it references is in the listing (rule 11 then keeps it no
    less restricted than them), review when one isn't (another schema, so nothing is known of it);
 5. the table's sole primary key: allow when integer or uuid; review otherwise (a text key can be an
    email, a username or another system's id);
 6. an integer GENERATED ALWAYS identity column: allow (the database makes its values);
 7. a type that can hold anything: review (text, varchar with no length or over 255, json, arrays,
    bytea, tsvector, vectors, network addresses, geometric values, money, any type it doesn't know);
 8. an id-like name (id, *_id, *_ids, *_uuid, *_guid; for a number or uuid also a fused userid, as an
    unquoted UserId folds) with no foreign key: review (it may hold an outside system's or person's id);
 9. boolean, date/time, interval, enum: allow; integer or numeric: allow unless the name looks like
    money (amount, price, total, balance, cents, fee, ...), then review; a uuid that is neither a key
    nor a foreign key: review;
10. a short string (varchar/char up to 255) whose last word is an enum-like label (type, kind, status,
    category, stage, phase, priority, severity, level, tier, mode, role): allow; any other: review;
    anything not matched above: review.
11. Derivations: a column is never less restricted than one it derives from. Sources are the rules'
    derivations, the columns a generated column is computed from, and the columns a foreign key
    references. A column the heuristics classed is raised to its source's class ("AUTO: derived
    from ..."); one an override classed is an error, so CD decides the source first. Repeated until
    nothing moves.
Views, materialized views and foreign tables are never granted (a view runs with its owner's rights,
so a grant on one bypasses the column exclusions; a materialized view copies other tables' data with
no column lineage; a foreign table reads another server): the listing names them under not_granted.
Schemas the rules don't name get nothing. A table or column in
a granted schema whose name isn't [A-Za-z_][A-Za-z0-9_]* (63 at most) is refused, never escaped.

columns.json is what CD reviews and the only input of the SQL (it's rendered from the parsed listing):
    {"_doc", "version": 1,
     "login": {role, database, schemas, statement_timeout, temp_file_limit, connection_limit, app_roles},
     "summary": {class: count, ..., "total": n},
     "tables": {"schema.table": {"column": {"class", "type", "reason"}, ...}, ...},   one line per column
     "not_granted": {"schema.relation": "why"}}

create_role.sql (psql, as a superuser, on a direct connection, in one transaction) refuses another
database, creates or converges the login (LOGIN, no other attribute, the connection limit, no password:
set it with psql's \\password, which hashes it on the client), resets and sets its settings
(statement_timeout and temp_file_limit from the rules; lock_timeout 3s,
idle_in_transaction_session_timeout 30s, idle_session_timeout 10min, default_transaction_read_only on,
search_path the rules' schemas), revokes everything it holds on the database and in every non-system
schema, revokes from PUBLIC EXECUTE on the large-object write functions (and the server-file ones) and
TEMPORARY on the database, grants those back to app_roles, revokes CONNECT from PUBLIC on every other
database that allows connections (the function and TEMPORARY revokes are per database), and grants
USAGE on the rules' schemas and SELECT on exactly the allowed columns. No ALTER DEFAULT PRIVILEGES: a
new table or column stays unreadable until the listing allows it. No role memberships, ever.
verify_role.sql (read-only; rerun after every migration deploy, a restore or a major upgrade) prints
one FAIL row per problem or one PASS row, then the password check when it may read pg_authid. Its
checks are a superset of planning-services.sh's login check, which the tests hold it to.
Needs PostgreSQL 14 or later (idle_session_timeout, pg_write_all_data).
"""

import argparse
import json
import pathlib
import re
import sys

FORMAT = "planning_reader catalog 1"
LISTING_VERSION = 1
LISTING, CREATE, VERIFY = "columns.json", "create_role.sql", "verify_role.sql"

ALLOW, REVIEW = "allow", "review"
EXCLUDE_PERSONAL, EXCLUDE_CREDENTIAL = "exclude-personal", "exclude-credential"
EXCLUDE_PAYMENT, EXCLUDE_CONTENT = "exclude-payment", "exclude-content"
EXCLUDES = (EXCLUDE_PERSONAL, EXCLUDE_CREDENTIAL, EXCLUDE_PAYMENT, EXCLUDE_CONTENT)
CLASSES = (ALLOW,) + EXCLUDES + (REVIEW,)
RESTRICTION = {ALLOW: 0, REVIEW: 1, **{c: 2 for c in EXCLUDES}}

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
ROLE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
DATABASE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,62}$")
DURATION = re.compile(r"^[1-9][0-9]{0,6}(ms|s|min|h)$")
SIZE = re.compile(r"^(0|[1-9][0-9]{0,6}(kB|MB|GB|TB))$")
REASON_MAX = 300

FIXED_SETTINGS = (("lock_timeout", "3s"), ("idle_in_transaction_session_timeout", "30s"),
                  ("idle_session_timeout", "10min"), ("default_transaction_read_only", "on"))
# Large-object writes PUBLIC may execute by default: persistent writes that need no table privilege.
LO_WRITE = ("lo_create(oid)", "lo_creat(integer)", "lo_from_bytea(oid, bytea)", "lo_put(oid, bigint, bytea)",
            "lowrite(integer, bytea)", "lo_truncate(integer, integer)", "lo_truncate64(integer, bigint)")
# Server-side file import and export: not PUBLIC's by default, revoked again in case, never granted back.
LO_SERVER_FILES = ("lo_import(text)", "lo_import(text, oid)", "lo_export(oid, text)")
POWERFUL_ROLES = ("pg_read_all_data", "pg_write_all_data", "pg_write_server_files", "pg_execute_server_program",
                  "pg_read_server_files", "pg_signal_backend")
NOT_GRANTED = {
    "v": "view: it runs with its owner's rights, so a grant would bypass the column exclusions",
    "m": "materialized view: a copy of other tables' data with no column lineage",
    "f": "foreign table: it reads another server with that server's credentials",
}


class Invalid(Exception):
    """A rules file, catalog or listing breaks a rule; the message names the entry."""


# ---------------------------------------------------------------------------------------------------------
# Names and types
# ---------------------------------------------------------------------------------------------------------

def snake(name):
    """UserId -> user_id, IPAddress -> ip_address, createdAt -> created_at, so one word list fits every stack."""
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def words(*alternatives):
    """Any of the words, as a whole word of a snake-case name."""
    return re.compile(r"(?:^|_)(?:" + "|".join(alternatives) + r")(?:_|$)")


CREDENTIAL = (re.compile(r"passw|passphrase|passcode|pincode|secret|credential|token|session|api_?key|"
                         r"private_?key|signing_?key|access_?key|bearer|cookie|jwt|oauth"),
              words("pwd", "keys?", "hash", "hashed", "digest", "salt", "nonce", "otp", "totp", "mfa",
                    "pin", "codes?", "auth", "signature", "verifier", "dsn", "cert", "certificate",
                    "enc", "encrypted", "cipher", "ciphertext", "recovery"))
PAYMENT = (re.compile(r"payment|invoice|billing|stripe|paypal|braintree|cardholder|card_?number|iban|cvv|cvc|"
                      r"routing_?number|account_?number|last_?4|last_?four"),
           words("cards?", "bank", "bic", "swift", "pan", "charges?", "refunds?", "payouts?", "mandate"))
PERSONAL = (re.compile(r"e_?mail|phone|mobile|address|street|postal|postcode|zipcode|birth|passport|surname|"
                       r"(first|last|full|display|given|family|middle|maiden|legal|real|nick|user|contact)_?name|"
                       r"avatar|photo|selfie|latitude|longitude|geoloc|user_?agent|fingerprint|ssn|national_id|"
                       r"tax_id|ethnic|religio|nationality|disabilit|diagnos|medical"),
            words("dob", "ip", "ips", "ipv4", "ipv6", "zip", "city", "country", "gender", "sex", "race", "age", "lat",
                  "lng", "lon", "geo", "gps", "locations?", "device", "handle", "login", "contacts?", "recipient",
                  "sender", "health"))
NAME_RULES = ((CREDENTIAL, EXCLUDE_CREDENTIAL, "a credential"), (PAYMENT, EXCLUDE_PAYMENT, "payment data"),
              (PERSONAL, EXCLUDE_PERSONAL, "personal data"))
PAYMENT_TABLE = re.compile(r"payment|invoice|billing|stripe|paypal|braintree|"
                           r"(?:^|_)(?:charges?|refunds?|payouts?|subscriptions?)(?:_|$)")
MONEY = words("amounts?", "prices?", "costs?", "total", "subtotal", "balance", "cents", "fees?", "salary",
              "wages?", "revenue", "income", "spend", "spent", "budget", "discount", "credits?", "debit", "paid",
              "owed")
ID_NAME = re.compile(r"(?:^|_)(?:id|ids|uuid|guid)$")
FUSED_ID = re.compile(r"(?:id|ids|uuid|guid)$")  # userid: unquoted UserId, folded to lower case
LABEL = re.compile(r"(?:^|_)(?:type|kind|status|category|stage|phase|priority|severity|level|tier|mode|role)$")
LONG_STRING = 255

BUILTIN = {
    "bool": "bool", "int2": "integer", "int4": "integer", "int8": "integer", "numeric": "number",
    "float4": "number", "float8": "number", "money": "money", "date": "datetime", "timestamp": "datetime",
    "timestamptz": "datetime", "time": "datetime", "timetz": "datetime", "interval": "interval", "uuid": "uuid",
    "varchar": "string", "bpchar": "string", "text": "text", "json": "json", "jsonb": "json", "bytea": "bytea",
    "tsvector": "tsvector", "inet": "network", "cidr": "network", "macaddr": "network", "macaddr8": "network",
    "point": "geometric", "line": "geometric", "lseg": "geometric", "box": "geometric", "path": "geometric",
    "polygon": "geometric", "circle": "geometric",
}
VECTOR_TYPES = {"vector", "halfvec", "sparsevec"}
SAFE_TYPES = {"bool": "a boolean", "datetime": "a date or time", "interval": "an interval",
              "enum": "an enum (the schema fixes its values)"}
TYPE_REVIEWS = {
    "text": "free text", "json": "JSON, which can hold anything", "array": "an array",
    "vector": "an embedding, which can be inverted to approximate its text",
    "tsvector": "a tsvector, which holds the words of its text", "bytea": "binary data",
    "network": "a network address (an IP address is personal data)",
    "geometric": "a geometric value (it may be a location)", "money": "a money amount",
    "other": "a type the generator doesn't recognise",
}


def display_type(text):
    """format_type's text without the schema it adds when the caller's search_path doesn't reach the type, so
    the listing is the same from any session: public.vector(1024) -> vector(1024)."""
    return re.sub(r'^(?:"[^"]+"|[A-Za-z_][A-Za-z0-9_$]*)\.', "", text)


def family(col):
    """What kind of value a column holds, from the catalog's facts: only pg_catalog's own types are known."""
    if col["base_category"] == "A":
        return "array"
    if col["base_kind"] == "e":
        return "enum"
    if col["base_kind"] != "b":
        return "other"  # a domain over a domain, a composite, a range or a pseudo-type
    if col["base_schema"] != "pg_catalog":
        return "vector" if col["base_type"] in VECTOR_TYPES else "other"
    return BUILTIN.get(col["base_type"], "other")


def heuristic(col, rel, listed):
    """(class, reason) for a column no override decides. Ends in review: allow is a whitelist."""
    names = [snake(col["name"])]
    if col["declared_kind"] in ("d", "e"):
        names.append(snake(col["declared_type"]))
    if col["base_kind"] == "e":
        names.append(snake(col["base_type"]))
    for (substrings, whole_words), klass, what in NAME_RULES:
        for name in names:
            if substrings.search(name) or whole_words.search(name):
                return klass, f"AUTO: the name looks like {what} ({name})."
    if col["generated"] and not col["generated_from"]:
        return REVIEW, "AUTO: a generated column whose source columns the catalog didn't name."
    fam = family(col)
    sole_pk = rel["primary_key"] == [col["name"]]
    surrogate = fam in ("integer", "uuid")
    if PAYMENT_TABLE.search(snake(rel["name"])) and not (sole_pk and surrogate):
        return REVIEW, "AUTO: a column of a payment-looking table."
    targets = [f"{fk['schema']}.{fk['table']}.{fk['column']}" for fk in col["foreign_keys"]]
    if targets:
        outside = [t for t in targets if t not in listed]
        if outside:
            return REVIEW, f"AUTO: a foreign key to {outside[0]}, which the listing doesn't classify."
        return ALLOW, f"AUTO: a foreign key to {targets[0]}, never less restricted than it."
    if sole_pk:
        if surrogate:
            return ALLOW, "AUTO: the table's integer or uuid primary key."
        return REVIEW, "AUTO: a primary key that isn't an integer or uuid (it can be an email, a username or another system's id)."
    if col["identity"] == "always" and fam == "integer":
        return ALLOW, "AUTO: an identity column; the database makes its values."
    if fam in TYPE_REVIEWS:
        return REVIEW, f"AUTO: {TYPE_REVIEWS[fam]} ({display_type(col['type'])})."
    if fam == "string" and (col["length"] is None or col["length"] > LONG_STRING):
        return REVIEW, f"AUTO: a string with no length limit or a long one ({display_type(col['type'])})."
    if ID_NAME.search(names[0]) or (fam in ("integer", "number", "uuid") and FUSED_ID.search(names[0])):
        return REVIEW, "AUTO: an id with no foreign key; it may hold another system's or a person's id."
    if fam in SAFE_TYPES:
        return ALLOW, f"AUTO: {SAFE_TYPES[fam]}."
    if fam in ("integer", "number"):
        if MONEY.search(names[0]):
            return REVIEW, "AUTO: a number whose name looks like money."
        return ALLOW, "AUTO: a number."
    if fam == "uuid":
        return REVIEW, "AUTO: a uuid that is neither the primary key nor a foreign key."
    if fam == "string":
        if LABEL.search(names[0]):
            return ALLOW, "AUTO: a short string named like an enum-like label."
        return REVIEW, "AUTO: a short string whose name isn't an enum-like label."
    return REVIEW, f"AUTO: {TYPE_REVIEWS['other']} ({display_type(col['type'])})."


# ---------------------------------------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------------------------------------

def _ident(value, what, pattern=IDENT):
    if not isinstance(value, str) or not pattern.match(value):
        raise Invalid(f"{what} {value!r} must match {pattern.pattern} (the generator puts it in SQL, so it refuses odd names)")
    return value


def _role(value, what):
    _ident(value, what, ROLE if what == "role" else IDENT)
    if value.lower().startswith("pg_") or value.lower() == "public":
        raise Invalid(f"{what} {value!r} is reserved")
    return value


def _login(data, where):
    """The login's settings, shared by the rules file and the listing's login object."""
    out = {"role": _role(data.get("role"), "role"),
           "database": _ident(data.get("database"), "database", DATABASE)}
    schemas = data.get("schemas")
    if not isinstance(schemas, list) or not schemas or len(set(map(str, schemas))) != len(schemas):
        raise Invalid(f"{where}: schemas must be a non-empty list of distinct schema names")
    for s in schemas:
        _ident(s, "schema")
        if s.startswith("pg_") or s == "information_schema":
            raise Invalid(f"{where}: {s} is a system schema")
    out["schemas"] = list(schemas)
    for key, pattern in (("statement_timeout", DURATION), ("temp_file_limit", SIZE)):
        value = data.get(key)
        if not isinstance(value, str) or not pattern.match(value):
            raise Invalid(f"{where}: {key} must match {pattern.pattern}, not {value!r}")
        out[key] = value
    limit = data.get("connection_limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
        raise Invalid(f"{where}: connection_limit must be an integer from 1 to 1000")
    out["connection_limit"] = limit
    app_roles = data.get("app_roles", [])
    if not isinstance(app_roles, list) or len(set(map(str, app_roles))) != len(app_roles):
        raise Invalid(f"{where}: app_roles must be a list of distinct role names")
    for r in app_roles:
        _role(r, "app role")
        if r == out["role"]:
            raise Invalid(f"{where}: the login can't be one of app_roles")
    out["app_roles"] = list(app_roles)
    return out


def _reason(value, where):
    if not isinstance(value, str) or not value.strip() or len(value) > REASON_MAX \
            or any(ord(ch) < 32 for ch in value) or value.startswith("AUTO:"):
        raise Invalid(f"{where}: reason must be one line of 1 to {REASON_MAX} characters, not starting AUTO:")
    return value


def load_rules(text):
    try:
        data = json.loads(text)
    except ValueError as e:
        raise Invalid(f"rules: not JSON: {e}")
    if not isinstance(data, dict):
        raise Invalid("rules: must be a JSON object")
    known = {"_doc", "role", "database", "schemas", "statement_timeout", "temp_file_limit", "connection_limit",
             "app_roles", "overrides", "derivations"}
    if set(data) - known:
        raise Invalid(f"rules: unknown keys {sorted(set(data) - known)}")
    rules = {"login": _login(data, "rules")}
    overrides = data.get("overrides", {})
    if not isinstance(overrides, dict):
        raise Invalid("rules: overrides must be an object")
    rules["overrides"] = {}
    for key, value in overrides.items():
        where = f"override {key}"
        parts = key.split(".")
        if len(parts) != 3:
            raise Invalid(f"{where}: the key must be schema.table.column or schema.table.*")
        _ident(parts[0], "schema")
        _ident(parts[1], "table")
        if parts[2] != "*":
            _ident(parts[2], "column")
        if not isinstance(value, dict) or set(value) != {"class", "reason"}:
            raise Invalid(f"{where}: must be exactly {{\"class\", \"reason\"}}")
        klass = value["class"]
        if klass == REVIEW:
            raise Invalid(f"{where}: review is undecided and comes only from the heuristics; an override decides")
        if klass not in CLASSES:
            raise Invalid(f"{where}: class must be one of {CLASSES[:-1]}")
        if parts[2] == "*" and klass == ALLOW:
            raise Invalid(f"{where}: a whole-table override may only exclude (allow columns one by one)")
        rules["overrides"][key] = {"class": klass, "reason": _reason(value["reason"], where)}
    derivations = data.get("derivations", {})
    if not isinstance(derivations, dict):
        raise Invalid("rules: derivations must be an object")
    rules["derivations"] = {}
    for key, sources in derivations.items():
        if not isinstance(sources, list) or not sources or not all(isinstance(s, str) for s in sources):
            raise Invalid(f"derivation {key}: must be a non-empty list of schema.table.column sources")
        if key in sources:
            raise Invalid(f"derivation {key}: a column can't derive from itself")
        rules["derivations"][key] = list(sources)
    return rules


def _need(obj, key, kind, where):
    value = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise Invalid(f"catalog: {where}: {key} is missing or not {getattr(kind, '__name__', kind)}")
    return value


def load_catalog(text):
    """The catalog-query output, its shape checked. Names are checked later, only where they reach SQL."""
    try:
        data = json.loads(text)
    except ValueError as e:
        raise Invalid(f"catalog: not JSON: {e}")
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise Invalid(f"catalog: not the output of this tool's catalog-query (format {FORMAT!r})")
    schemas = _need(data, "schemas", list, "top level")
    if not all(isinstance(s, str) for s in schemas):
        raise Invalid("catalog: schemas must be names")
    for rel in _need(data, "relations", list, "top level"):
        where = f"{rel.get('schema')}.{rel.get('name')}" if isinstance(rel, dict) else "a relation"
        for key in ("schema", "name", "kind"):
            _need(rel, key, str, where)
        if rel["kind"] not in ("r", "p", "v", "m", "f"):
            raise Invalid(f"catalog: {where}: kind {rel['kind']!r}")
        if not all(isinstance(c, str) for c in _need(rel, "primary_key", list, where)):
            raise Invalid(f"catalog: {where}: primary_key must be column names")
        for col in _need(rel, "columns", list, where):
            cwhere = f"{where}.{col.get('name') if isinstance(col, dict) else '?'}"
            for key in ("name", "type", "declared_type", "declared_kind", "base_type", "base_schema", "base_kind",
                        "base_category"):
                _need(col, key, str, cwhere)
            for key in ("not_null", "generated"):
                _need(col, key, bool, cwhere)
            if col.get("length") is not None and (not isinstance(col["length"], int) or isinstance(col["length"], bool)):
                raise Invalid(f"catalog: {cwhere}: length must be an integer or null")
            if col.get("identity") not in (None, "always", "by default"):
                raise Invalid(f"catalog: {cwhere}: identity must be always, by default or null")
            col.setdefault("length", None)
            col.setdefault("identity", None)
            if not all(isinstance(c, str) for c in _need(col, "generated_from", list, cwhere)):
                raise Invalid(f"catalog: {cwhere}: generated_from must be column names")
            for fk in _need(col, "foreign_keys", list, cwhere):
                for key in ("schema", "table", "column"):
                    _need(fk, key, str, f"{cwhere} foreign key")
    return data


# ---------------------------------------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------------------------------------

def classify(catalog, rules):
    """The listing (a dict) for this catalog and these rules: a pure function of the two."""
    login = rules["login"]
    granted = set(login["schemas"])
    missing = granted - set(catalog["schemas"])
    if missing:
        raise Invalid(f"rules: schemas {sorted(missing)} aren't in the catalog")
    tables, not_granted = {}, {}
    for rel in catalog["relations"]:
        if rel["schema"] not in granted:
            continue
        key = f"{rel['schema']}.{rel['name']}"
        if rel["kind"] in NOT_GRANTED:
            not_granted[key] = NOT_GRANTED[rel["kind"]]
            continue
        _ident(rel["name"], f"table in {rel['schema']}")
        names = [c["name"] for c in rel["columns"]]
        for name in names:
            _ident(name, f"column of {key}")
        if len(set(names)) != len(names):
            raise Invalid(f"catalog: {key} lists a column twice")
        tables[key] = rel
    columns = {f"{t}.{c['name']}": (c, rel) for t, rel in tables.items() for c in rel["columns"]}

    overrides = rules["overrides"]
    for key in overrides:
        table, _, column = key.rpartition(".")
        if (column == "*" and table not in tables) or (column != "*" and key not in columns):
            raise Invalid(f"override {key}: no such table or column in the granted schemas (stale?)")

    entries, decided = {}, set()
    for key, (col, rel) in columns.items():
        table = f"{rel['schema']}.{rel['name']}"
        ov = overrides.get(key) or overrides.get(f"{table}.*")
        if ov:
            entries[key] = {"class": ov["class"], "type": display_type(col["type"]), "reason": ov["reason"]}
            decided.add(key)
        else:
            klass, reason = heuristic(col, rel, columns)
            entries[key] = {"class": klass, "type": display_type(col["type"]), "reason": reason}

    sources = {}
    for key, srcs in rules["derivations"].items():
        for name in [key] + srcs:
            if name not in columns:
                raise Invalid(f"derivation {key}: {name} isn't a column in the granted schemas (stale?)")
        sources.setdefault(key, set()).update(srcs)
    for key, (col, rel) in columns.items():
        table = f"{rel['schema']}.{rel['name']}"
        for name in col["generated_from"]:
            if f"{table}.{name}" in columns:
                sources.setdefault(key, set()).add(f"{table}.{name}")
        for fk in col["foreign_keys"]:
            target = f"{fk['schema']}.{fk['table']}.{fk['column']}"
            if target in columns and target != key:
                sources.setdefault(key, set()).add(target)
    changed = True
    while changed:
        changed = False
        for key in sorted(sources):
            for src in sorted(sources[key]):
                mine, theirs = entries[key]["class"], entries[src]["class"]
                if RESTRICTION[mine] >= RESTRICTION[theirs]:
                    continue
                if key in decided:
                    raise Invalid(f"override {key}: it derives from {src}, which is {theirs}, so it can't be {mine}; "
                                  f"decide {src} first")
                entries[key]["class"] = theirs
                entries[key]["reason"] = f"AUTO: derived from {src}, which is {theirs}."
                changed = True

    listing_tables = {}
    for key, entry in entries.items():
        table, _, column = key.rpartition(".")
        listing_tables.setdefault(table, {})[column] = entry
    for table in tables:
        listing_tables.setdefault(table, {})
    summary = {c: 0 for c in CLASSES}
    for entry in entries.values():
        summary[entry["class"]] += 1
    summary["total"] = len(entries)
    return {"version": LISTING_VERSION, "login": login, "summary": summary, "tables": listing_tables,
            "not_granted": not_granted,
            "ungranted_schemas": sorted(s for s in catalog["schemas"] if s not in granted)}  # printed, not written


# ---------------------------------------------------------------------------------------------------------
# The listing
# ---------------------------------------------------------------------------------------------------------

LISTING_DOC = ("GENERATED by planning_reader.py update from the database catalog and the rules file; do not "
               "edit. Only allow columns are granted to the planning login. review is undecided and excluded "
               "until CD decides it with an override. AUTO: marks a reason the generator wrote.")


def _one_line(value):
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def render_listing(listing):
    out = ["{", f'  "_doc": {_one_line(LISTING_DOC)},', f'  "version": {listing["version"]},',
           f'  "login": {_one_line(listing["login"])},', f'  "summary": {_one_line(listing["summary"])},',
           '  "tables": {']
    tables = sorted(listing["tables"])
    for i, table in enumerate(tables):
        cols = listing["tables"][table]
        out.append(f"    {_one_line(table)}: {{")
        names = sorted(cols)
        for j, name in enumerate(names):
            entry = {k: cols[name][k] for k in ("class", "type", "reason")}
            out.append(f"      {_one_line(name)}: {_one_line(entry)}{',' if j < len(names) - 1 else ''}")
        out.append("    }" + ("," if i < len(tables) - 1 else ""))
    out.append("  },")
    out.append('  "not_granted": {')
    relations = sorted(listing["not_granted"])
    for i, rel in enumerate(relations):
        out.append(f"    {_one_line(rel)}: {_one_line(listing['not_granted'][rel])}{',' if i < len(relations) - 1 else ''}")
    out.append("  }")
    out.append("}")
    return "\n".join(out) + "\n"


def parse_listing(text):
    """A listing read back and checked again, since the SQL is rendered from it."""
    try:
        data = json.loads(text)
    except ValueError as e:
        raise Invalid(f"listing: not JSON: {e}")
    if not isinstance(data, dict) or data.get("version") != LISTING_VERSION or not isinstance(data.get("tables"), dict):
        raise Invalid(f"listing: not a version {LISTING_VERSION} listing")
    login = _login(data.get("login") or {}, "listing login")
    tables = {}
    for table, cols in data["tables"].items():
        parts = table.split(".")
        if len(parts) != 2 or not isinstance(cols, dict):
            raise Invalid(f"listing: table {table!r} must be schema.table with an object of columns")
        _ident(parts[0], "schema")
        _ident(parts[1], "table")
        if parts[0] not in login["schemas"]:
            raise Invalid(f"listing: {table} isn't in a granted schema")
        tables[table] = {}
        for name, entry in cols.items():
            _ident(name, f"column of {table}")
            if not isinstance(entry, dict) or entry.get("class") not in CLASSES:
                raise Invalid(f"listing: {table}.{name} has no valid class")
            tables[table][name] = entry
    return {"login": login, "tables": tables}


def allowed(listing):
    """[(schema, table, [columns])] the login may read, sorted."""
    out = []
    for table in sorted(listing["tables"]):
        cols = sorted(c for c, e in listing["tables"][table].items() if e["class"] == ALLOW)
        if cols:
            schema, name = table.split(".")
            out.append((schema, name, cols))
    return out


# ---------------------------------------------------------------------------------------------------------
# SQL. Only validated identifiers and settings reach it, always double-quoted as identifiers or single-quoted
# as literals (neither can contain a quote); nothing free-form from the rules, not even in a comment.
# ---------------------------------------------------------------------------------------------------------

def q(name):
    return f'"{name}"'


def lit(value):
    return f"'{value}'"


def _functions(names, indent="    "):
    return ",\n".join(f"{indent}pg_catalog.{f}" for f in names)


def _wrap(items, indent="    ", width=110):
    lines, line = [], indent
    for i, item in enumerate(items):
        piece = item + ("," if i < len(items) - 1 else "")
        if len(line) + len(piece) + 1 > width and line.strip():
            lines.append(line.rstrip())
            line = indent
        line += piece + " "
    lines.append(line.rstrip())
    return lines


def _settings(login):
    return (("statement_timeout", login["statement_timeout"]),) + FIXED_SETTINGS + \
        (("temp_file_limit", login["temp_file_limit"]),)


def render_create(listing):
    login = listing["login"]
    role, db = login["role"], login["database"]
    r = q(role)
    out = f"""\
-- GENERATED by planning_reader.py from columns.json; do not edit. Regenerate with its update command.
--
-- The planning tier's read-only login (process/factory.md, D3 rule 3): role {role} on database {db}.
-- Run it with psql as a superuser on a direct connection (not through pgbouncer), then set the password
-- with psql's \\password (it hashes the password on the client, so the plaintext never reaches the server's
-- logs), then run verify_role.sql and expect one PASS row:
--
--     psql "$DATABASE_URL" -f create_role.sql
--     psql "$DATABASE_URL"            and at its prompt:  \\password {role}
--     psql "$DATABASE_URL" -f verify_role.sql
--
-- One transaction, safe to rerun (a rerun leaves the password alone). It refuses any database but {db}.
--
-- Read-only is the role's privileges, never a session default: any session can BEGIN READ WRITE. So this
-- script also takes from PUBLIC the writes PostgreSQL gives every role: EXECUTE on the large-object write
-- functions and TEMPORARY on this database. Those are per database, so it revokes CONNECT from PUBLIC on
-- every other database too. A superuser ignores all of it. Before the first run, check every other role:
--   SELECT rolname FROM pg_roles WHERE NOT rolsuper AND rolname !~ '^pg_';
-- A non-superuser application role that uses temporary tables or large objects belongs in the rules'
-- app_roles (they're granted back below). One that connects to another database of the cluster (a
-- monitoring agent, pgbouncer's auth user, another application on a shared cluster) needs
-- GRANT CONNECT ON DATABASE <that one> TO <it> after this runs.
--
-- Not done, on purpose: no ALTER DEFAULT PRIVILEGES (a new table or column stays unreadable until the
-- listing allows it), no grant on a view, materialized view or foreign table, no role membership.
--
-- Rollback: remove the password from the proxy that holds it, ALTER ROLE {r} NOLOGIN, end its sessions,
-- DROP OWNED BY {r} in this database, DROP ROLE {r}. The revokes from PUBLIC stay.

\\set ON_ERROR_STOP on

BEGIN;

-- 0. The right database, or nothing.
DO $guard$
BEGIN
    IF current_database() <> {lit(db)} THEN
        RAISE EXCEPTION 'create_role.sql is for database {db}, and this is %', current_database();
    END IF;
END
$guard$;

-- 1. The login, with no attribute but LOGIN and its connection limit.
DO $role$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {lit(role)}) THEN
        CREATE ROLE {r} LOGIN;
    END IF;
END
$role$;
ALTER ROLE {r} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT CONNECTION LIMIT {login["connection_limit"]};

-- 2. Session settings, reset first so nothing stray survives. temp_file_limit only a superuser can change;
--    the others the role can SET away (guard rails; pgbouncer's query_timeout is the deadline it can't lift).
ALTER ROLE {r} RESET ALL;
DO $settings$
DECLARE d name;
BEGIN
    FOR d IN SELECT db.datname FROM pg_db_role_setting s JOIN pg_database db ON db.oid = s.setdatabase
              WHERE s.setrole = (SELECT oid FROM pg_roles WHERE rolname = {lit(role)}) LOOP
        EXECUTE format('ALTER ROLE %I IN DATABASE %I RESET ALL', {lit(role)}, d);
    END LOOP;
END
$settings$;
"""
    for name, value in _settings(login):
        out += f"ALTER ROLE {r} SET {name} = {lit(value)};\n"
    out += f"ALTER ROLE {r} SET search_path TO {', '.join(q(s) for s in login['schemas'])};\n"
    out += f"""
-- 3. Nothing the role held before: on this database, and on every schema and everything in it.
REVOKE ALL ON DATABASE {q(db)} FROM {r};
DO $schemas$
DECLARE s name;
BEGIN
    FOR s IN SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname <> 'information_schema' LOOP
        EXECUTE format('REVOKE ALL ON SCHEMA %I FROM %I', s, {lit(role)});
        EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM %I', s, {lit(role)});
        EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM %I', s, {lit(role)});
        EXECUTE format('REVOKE ALL ON ALL ROUTINES IN SCHEMA %I FROM %I', s, {lit(role)});
    END LOOP;
END
$schemas$;

-- 4. What PUBLIC would hand the role: large-object writes, server-file import and export, temporary tables,
--    and (since those are per database) a connection to any other database.
REVOKE EXECUTE ON FUNCTION
{_functions(LO_WRITE + LO_SERVER_FILES)}
FROM PUBLIC;
REVOKE TEMPORARY ON DATABASE {q(db)} FROM PUBLIC;
"""
    for app in login["app_roles"]:
        out += f"GRANT TEMPORARY ON DATABASE {q(db)} TO {q(app)};\n"
        out += f"GRANT EXECUTE ON FUNCTION\n{_functions(LO_WRITE)}\nTO {q(app)};\n"
    out += f"""DO $others$
DECLARE d name;
BEGIN
    FOR d IN SELECT datname FROM pg_database WHERE datname <> current_database() AND datallowconn LOOP
        EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', d);
        EXECUTE format('REVOKE ALL ON DATABASE %I FROM %I', d, {lit(role)});
    END LOOP;
END
$others$;

-- 5. Connect, see the granted schemas, read exactly the allowed columns.
GRANT CONNECT ON DATABASE {q(db)} TO {r};
"""
    for schema in login["schemas"]:
        out += f"GRANT USAGE ON SCHEMA {q(schema)} TO {r};\n"
    for schema, table, cols in allowed(listing):
        out += "GRANT SELECT (\n" + "\n".join(_wrap([q(c) for c in cols])) + f"\n) ON TABLE {q(schema)}.{q(table)} TO {r};\n"
    return out + "\nCOMMIT;\n"


def render_verify(listing):
    login = listing["login"]
    role, db, rl = login["role"], login["database"], lit(login["role"])
    rows = [f"({lit(s)}, {lit(t)}, {lit(c)})" for s, t, cols in allowed(listing) for c in cols]
    expected = ("    VALUES\n" + ",\n".join(f"        {row}" for row in rows)) if rows else \
        "    SELECT NULL::text, NULL::text, NULL::text WHERE false"
    settings = ", ".join(lit(f"{n}={v}") for n, v in _settings(login))
    setting_names = ", ".join(lit(n) for n, _ in _settings(login)) + ", 'search_path'"
    functions = ", ".join(lit(f"pg_catalog.{f}") for f in LO_WRITE + LO_SERVER_FILES)
    powerful = ", ".join(lit(p) for p in POWERFUL_ROLES)
    return f"""\
-- GENERATED by planning_reader.py from columns.json; do not edit. Regenerate with its update command.
--
-- Read-only checks of the planning login {role} on database {db} (process/factory.md, D3 rule 3), a superset
-- of planning-services.sh's login check. Run after create_role.sql and \\password, and again after every
-- migration deploy, restore or major upgrade: a grant follows a column's identity, not its name, so a
-- column dropped and re-added loses it, and a new table or extension can bring a grant to PUBLIC.
--
--     psql "$DATABASE_URL" -f verify_role.sql
--
-- Prints one FAIL row per problem, or one PASS row; then the password check, which needs a superuser.

\\set ON_ERROR_STOP on

BEGIN TRANSACTION READ ONLY;

DO $guard$
BEGIN
    IF current_database() <> {lit(db)} THEN
        RAISE EXCEPTION 'verify_role.sql is for database {db}, and this is %', current_database();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {rl}) THEN
        RAISE EXCEPTION 'role {role} does not exist: run create_role.sql first';
    END IF;
END
$guard$;

WITH expected(sch, tbl, col) AS (
{expected}
),
reader AS (SELECT * FROM pg_roles WHERE rolname = {rl}),
config AS (
    SELECT coalesce((SELECT s.setconfig FROM pg_db_role_setting s, reader
                      WHERE s.setrole = reader.oid AND s.setdatabase = 0), '{{}}'::text[]) AS cfg
),
rels AS (
    SELECT c.oid, c.relkind, c.relacl, n.nspname::text AS nsp, c.relname::text AS rel
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
),
cols AS (
    SELECT r.oid, r.nsp, r.rel, a.attnum, a.attname::text AS att
      FROM rels r JOIN pg_attribute a ON a.attrelid = r.oid AND a.attnum > 0 AND NOT a.attisdropped
     WHERE r.relkind IN ('r', 'p', 'v', 'm', 'f')
),
problems(check_name, detail) AS (
    -- Exactly the allowed columns, and only to read.
    SELECT 'allowed column missing or not readable', e.sch || '.' || e.tbl || '.' || e.col
      FROM expected e
     WHERE NOT EXISTS (SELECT 1 FROM cols u WHERE u.nsp = e.sch AND u.rel = e.tbl AND u.att = e.col
                          AND has_column_privilege({rl}, u.oid, u.attnum, 'SELECT'))
    UNION ALL
    SELECT 'column outside the allow list is accessible', u.nsp || '.' || u.rel || '.' || u.att
      FROM cols u
     WHERE has_column_privilege({rl}, u.oid, u.attnum, 'SELECT,INSERT,UPDATE,REFERENCES')
       AND (u.nsp, u.rel, u.att) NOT IN (SELECT sch, tbl, col FROM expected)
    UNION ALL
    SELECT 'write privilege held on a column', u.nsp || '.' || u.rel || '.' || u.att
      FROM cols u
     WHERE has_column_privilege({rl}, u.oid, u.attnum, 'INSERT,UPDATE,REFERENCES')
    UNION ALL
    SELECT 'grant option held on a column', u.nsp || '.' || u.rel || '.' || u.att
      FROM cols u
     WHERE has_column_privilege({rl}, u.oid, u.attnum, 'SELECT WITH GRANT OPTION,INSERT WITH GRANT OPTION,'
                                'UPDATE WITH GRANT OPTION,REFERENCES WITH GRANT OPTION')
    UNION ALL
    -- No privilege on a whole relation: a table-level SELECT would cover the excluded columns.
    SELECT 'relation-level privilege held', r.nsp || '.' || r.rel
      FROM rels r
     WHERE r.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND has_table_privilege({rl}, r.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
    UNION ALL
    SELECT 'relation grants ' || x.privilege_type || CASE WHEN x.grantee = 0 THEN ' to PUBLIC' ELSE ' to the role' END,
           r.nsp || '.' || r.rel
      FROM rels r, reader, aclexplode(r.relacl) x
     WHERE r.relkind IN ('r', 'p', 'v', 'm', 'f', 'S') AND x.grantee IN (0, reader.oid)
    UNION ALL
    SELECT 'sequence privilege held', r.nsp || '.' || r.rel
      FROM rels r
     WHERE CASE WHEN r.relkind = 'S' THEN has_sequence_privilege({rl}, r.oid, 'USAGE,SELECT,UPDATE') ELSE false END
    UNION ALL
    -- Nothing to create or keep: database, schemas, temporary tables, large objects, other databases.
    SELECT 'CREATE privilege held', 'database ' || current_database()
     WHERE has_database_privilege({rl}, current_database(), 'CREATE')
    UNION ALL
    SELECT 'TEMPORARY privilege held (revoke it from PUBLIC)', 'database ' || current_database()
     WHERE has_database_privilege({rl}, current_database(), 'TEMPORARY')
    UNION ALL
    SELECT 'grant option held', 'database ' || current_database()
     WHERE has_database_privilege({rl}, current_database(),
                                  'CONNECT WITH GRANT OPTION,TEMPORARY WITH GRANT OPTION,CREATE WITH GRANT OPTION')
    UNION ALL
    SELECT 'CREATE privilege held', 'schema ' || n.nspname
      FROM pg_namespace n
     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' AND has_schema_privilege({rl}, n.oid, 'CREATE')
    UNION ALL
    SELECT 'grant option held', 'schema ' || n.nspname
      FROM pg_namespace n
     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
       AND has_schema_privilege({rl}, n.oid, 'USAGE WITH GRANT OPTION,CREATE WITH GRANT OPTION')
    UNION ALL
    SELECT 'large-object or server-file function executable (revoke EXECUTE from PUBLIC)', f
      FROM unnest(ARRAY[{functions}]) f
     WHERE has_function_privilege({rl}, f, 'EXECUTE')
    UNION ALL
    SELECT 'large object owned by the role', l.oid::text
      FROM pg_largeobject_metadata l, reader WHERE l.lomowner = reader.oid
    UNION ALL
    SELECT 'large objects readable by everyone', 'lo_compat_privileges is on'
     WHERE current_setting('lo_compat_privileges') = 'on'
    UNION ALL
    SELECT 'large objects readable by the role or PUBLIC', count(*)::text
      FROM pg_largeobject_metadata l, reader, aclexplode(l.lomacl) x
     WHERE x.grantee IN (0, reader.oid) AND x.privilege_type IN ('SELECT', 'UPDATE')
    HAVING count(*) > 0
    UNION ALL
    SELECT 'role can connect to another database', d.datname::text
      FROM pg_database d
     WHERE d.datname <> current_database() AND d.datallowconn AND has_database_privilege({rl}, d.oid, 'CONNECT')
    UNION ALL
    -- A SECURITY DEFINER function runs with its owner's rights and bypasses every column grant.
    SELECT 'SECURITY DEFINER function executable', n.nspname || '.' || p.proname
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE p.prosecdef AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
       AND has_function_privilege({rl}, p.oid, 'EXECUTE')
    UNION ALL
    -- Owns nothing, holds no role.
    SELECT 'role owns the database', d.datname::text
      FROM pg_database d, reader WHERE d.datname = current_database() AND d.datdba = reader.oid
    UNION ALL
    SELECT 'role owns a relation', c.oid::regclass::text
      FROM pg_class c, reader WHERE c.relowner = reader.oid
    UNION ALL
    SELECT 'role owns an object',
           CASE WHEN s.dbid IN (0, (SELECT oid FROM pg_database WHERE datname = current_database()))
                THEN pg_describe_object(s.classid, s.objid, s.objsubid)
                ELSE 'an object in another database (oid ' || s.dbid || ')' END
      FROM pg_shdepend s, reader
     WHERE s.refclassid = 'pg_authid'::regclass AND s.refobjid = reader.oid AND s.deptype = 'o'
    UNION ALL
    SELECT 'role is a member of a powerful built-in role', b
      FROM unnest(ARRAY[{powerful}]) b
     WHERE pg_has_role({rl}, b, 'MEMBER')
    UNION ALL
    SELECT 'role is a member of a role', m.roleid::regrole::text
      FROM pg_auth_members m, reader WHERE m.member = reader.oid
    UNION ALL
    SELECT 'role attribute', 'superuser, createrole, createdb, replication, bypassrls, nologin or connection limit'
      FROM reader
     WHERE rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls OR NOT rolcanlogin
        OR rolconnlimit <> {login["connection_limit"]}
    UNION ALL
    -- Settings: temp_file_limit is the one the role can't lift; the others are guard rails.
    SELECT 'temp_file_limit is unlimited (set it on the role; only a superuser can change it)', {rl}
      FROM config
     WHERE NOT EXISTS (SELECT 1 FROM unnest(cfg) c WHERE c ~ '^temp_file_limit=' AND c <> 'temp_file_limit=-1')
    UNION ALL
    SELECT 'role setting missing or different', e
      FROM config, unnest(ARRAY[{settings}]) e
     WHERE NOT e = ANY (cfg)
    UNION ALL
    SELECT 'role setting missing', 'search_path'
      FROM config WHERE NOT EXISTS (SELECT 1 FROM unnest(cfg) c WHERE c LIKE 'search_path=%')
    UNION ALL
    SELECT 'unexpected role setting', split_part(c, '=', 1)
      FROM config, unnest(cfg) c
     WHERE split_part(c, '=', 1) NOT IN ({setting_names})
    UNION ALL
    SELECT 'role has a per-database setting', coalesce(d.datname::text, s.setdatabase::text)
      FROM pg_db_role_setting s JOIN reader ON s.setrole = reader.oid LEFT JOIN pg_database d ON d.oid = s.setdatabase
     WHERE s.setdatabase <> 0
    UNION ALL
    SELECT 'password_encryption is not scram-sha-256', current_setting('password_encryption')
     WHERE current_setting('password_encryption') <> 'scram-sha-256'
)
SELECT 'FAIL' AS status, check_name, detail FROM problems
UNION ALL
SELECT 'PASS', 'no problems', '' WHERE NOT EXISTS (SELECT 1 FROM problems)
ORDER BY 1, 2, 3;

-- The password must be a SCRAM verifier (set with \\password). Only a superuser can read pg_authid.
SELECT has_table_privilege('pg_catalog.pg_authid', 'SELECT') AS planning_reader_can_read_authid \\gset
\\if :planning_reader_can_read_authid
SELECT CASE WHEN coalesce(rolpassword, '') ~ '^SCRAM-SHA-256[$]' THEN 'PASS' ELSE 'FAIL' END AS status,
       'password is a SCRAM verifier (set it with \\password {role})' AS check_name, '' AS detail
  FROM pg_authid WHERE rolname = {rl};
\\else
SELECT 'SKIP' AS status, 'password check needs a superuser (pg_authid)' AS check_name, '' AS detail;
\\endif

ROLLBACK;
"""


# ---------------------------------------------------------------------------------------------------------
# The catalog query
# ---------------------------------------------------------------------------------------------------------

CATALOG_QUERY = f"""\
select json_build_object(
  'format', '{FORMAT}',
  'schemas', (select coalesce(json_agg(n.nspname order by n.nspname), '[]'::json)
                from pg_namespace n
               where n.nspname !~ '^pg_' and n.nspname <> 'information_schema'),
  'relations', (select coalesce(json_agg(r.doc order by r.sch, r.rel), '[]'::json) from (
    select n.nspname as sch, c.relname as rel, json_build_object(
      'schema', n.nspname,
      'name', c.relname,
      'kind', c.relkind,
      'primary_key', (select coalesce(json_agg(pa.attname order by pa.attnum), '[]'::json)
                        from pg_constraint pk
                        join pg_attribute pa on pa.attrelid = pk.conrelid and pa.attnum = any (pk.conkey)
                       where pk.conrelid = c.oid and pk.contype = 'p'),
      'columns', (select coalesce(json_agg(col.doc order by col.attnum), '[]'::json) from (
        select a.attnum, json_build_object(
          'name', a.attname,
          'type', format_type(a.atttypid, a.atttypmod),
          'declared_type', t.typname,
          'declared_kind', t.typtype,
          'base_type', bt.typname,
          'base_schema', btn.nspname,
          'base_kind', bt.typtype,
          'base_category', bt.typcategory,
          'length', case when btn.nspname = 'pg_catalog' and bt.typname in ('varchar', 'bpchar')
                          and (case when t.typtype = 'd' then t.typtypmod else a.atttypmod end) >= 4
                         then (case when t.typtype = 'd' then t.typtypmod else a.atttypmod end) - 4 end,
          'not_null', a.attnotnull,
          'identity', case a.attidentity when 'a' then 'always' when 'd' then 'by default' end,
          'generated', a.attgenerated <> '',
          'generated_from', (select coalesce(json_agg(distinct sa.attname), '[]'::json)
                               from pg_depend d
                               join pg_attribute sa on sa.attrelid = d.refobjid and sa.attnum = d.refobjsubid
                              where a.attgenerated <> ''
                                and d.refclassid = 'pg_class'::regclass and d.refobjid = c.oid
                                and d.refobjsubid > 0 and d.refobjsubid <> a.attnum
                                and ((d.classid = 'pg_class'::regclass and d.objid = c.oid and d.objsubid = a.attnum)
                                  or (d.classid = 'pg_attrdef'::regclass
                                      and d.objid in (select ad.oid from pg_attrdef ad
                                                       where ad.adrelid = c.oid and ad.adnum = a.attnum)))),
          'foreign_keys', (select coalesce(json_agg(json_build_object('schema', fn.nspname, 'table', fc.relname,
                                                                      'column', fa.attname)
                                                    order by fn.nspname, fc.relname, fa.attname), '[]'::json)
                             from pg_constraint k
                             cross join lateral unnest(k.conkey, k.confkey) as u(src, dst)
                             join pg_class fc on fc.oid = k.confrelid
                             join pg_namespace fn on fn.oid = fc.relnamespace
                             join pg_attribute fa on fa.attrelid = k.confrelid and fa.attnum = u.dst
                            where k.conrelid = c.oid and k.contype = 'f' and k.conparentid = 0
                              and u.src = a.attnum)
        ) as doc
        from pg_attribute a
        join pg_type t on t.oid = a.atttypid
        join pg_type bt on bt.oid = case when t.typtype = 'd' then t.typbasetype else t.oid end
        join pg_namespace btn on btn.oid = bt.typnamespace
        where a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped
      ) col)
    ) as doc
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where c.relkind in ('r', 'p', 'v', 'm', 'f')
      and not c.relispartition
      and n.nspname !~ '^pg_' and n.nspname <> 'information_schema'
  ) r)
)
"""


# ---------------------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------------------

def build(catalog_text, rules_text):
    """{file name: content} for the three generated files, and the parsed listing they came from."""
    listing = classify(load_catalog(catalog_text), load_rules(rules_text))
    listing_text = render_listing(listing)
    parsed = parse_listing(listing_text)
    parsed["ungranted_schemas"] = listing["ungranted_schemas"]
    return {LISTING: listing_text, CREATE: render_create(parsed), VERIFY: render_verify(parsed)}, parsed


def column_classes(listing):
    return {f"{t}.{c}": e["class"] for t, cols in listing["tables"].items() for c, e in cols.items()}


def _read(path):
    return sys.stdin.read() if path == "-" else pathlib.Path(path).read_text(encoding="utf-8")


def _previous(out_dir):
    path = pathlib.Path(out_dir) / LISTING
    if not path.exists():
        return None
    try:
        return parse_listing(path.read_text(encoding="utf-8"))
    except Invalid as e:
        print(f"planning_reader: the listing on disk is unreadable, so every column counts as new ({e})")
        return None


def _ungranted(listing):
    if listing["ungranted_schemas"]:
        print(f"planning_reader: schemas not granted (the login reads nothing there): "
              f"{', '.join(listing['ungranted_schemas'])}")


def cmd_update(args):
    files, listing = build(_read(args.catalog), _read(args.rules))
    _ungranted(listing)
    previous = _previous(args.out)
    old = column_classes(previous) if previous else {}
    new = column_classes(listing)
    reasons = {f"{t}.{c}": e["reason"] for t, cols in listing["tables"].items() for c, e in cols.items()}
    for key in sorted(new):
        if key not in old:
            print(f"NEW     {key}: {new[key]}  {reasons[key]}")
        elif old[key] != new[key]:
            print(f"CHANGED {key}: {old[key]} -> {new[key]}  {reasons[key]}")
    for key in sorted(set(old) - set(new)):
        print(f"GONE    {key}")
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
        print(f"wrote {out / name}")
    summary = json.loads(files[LISTING])["summary"]
    print("summary: " + ", ".join(f"{k} {v}" for k, v in summary.items()))
    if summary[REVIEW]:
        print(f"{summary[REVIEW]} columns are review: excluded until CD decides them (an override with a reason).")
    return 0


def cmd_check(args):
    files, listing = build(_read(args.catalog), _read(args.rules))
    _ungranted(listing)
    out = pathlib.Path(args.out)
    stale = [name for name, content in files.items()
             if not (out / name).exists() or (out / name).read_text(encoding="utf-8") != content]
    if not stale:
        summary = json.loads(files[LISTING])["summary"]
        print("planning_reader: up to date (" + ", ".join(f"{k} {v}" for k, v in summary.items()) + ")")
        return 0
    try:
        on_disk = column_classes(parse_listing((out / LISTING).read_text(encoding="utf-8")))
    except (OSError, Invalid):
        on_disk = {}
    for key, klass in sorted(column_classes(listing).items()):
        if key not in on_disk:
            print(f"NEW     {key}: {klass}")
    print(f"::error::planning_reader: stale: {', '.join(stale)}. Rerun: python3 -I planning_reader.py update "
          f"--catalog <catalog> --rules {args.rules} --out {args.out}, and have CD review the diff.")
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="planning_reader.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog-query", help="print the read-only catalog query")
    for name in ("update", "check"):
        p = sub.add_parser(name)
        p.add_argument("--catalog", required=True, help="catalog-query's JSON output, or - for stdin")
        p.add_argument("--rules", required=True, help="the rules file")
        p.add_argument("--out", required=True, help="the directory of columns.json, create_role.sql, verify_role.sql")
    args = parser.parse_args(argv)
    if args.command == "catalog-query":
        sys.stdout.write(CATALOG_QUERY)
        return 0
    try:
        return cmd_update(args) if args.command == "update" else cmd_check(args)
    except (Invalid, OSError) as e:
        print(f"::error::planning_reader: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
