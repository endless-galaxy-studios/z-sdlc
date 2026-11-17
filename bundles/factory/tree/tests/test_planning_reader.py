"""Tests for planning_reader.py: deny-by-default classification from a faked catalog, overrides and derivations,
identifier refusal, the generated SQL (and that its verify checks cover planning-services.sh's login check),
and the update/check commands. No database: the catalog is a JSON fixture built here."""

import contextlib
import io
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))

import planning_reader as pr  # noqa: E402

CATEGORY = {"bool": "B", "int2": "N", "int4": "N", "int8": "N", "numeric": "N", "float8": "N", "money": "N",
            "timestamptz": "D", "date": "D", "interval": "T", "uuid": "U", "varchar": "S", "bpchar": "S",
            "text": "S", "jsonb": "U", "json": "U", "bytea": "U", "tsvector": "U", "inet": "I", "point": "G",
            "oid": "N"}


def col(name, base="int4", length=None, **kw):
    c = {"name": name, "type": kw.pop("type", base if length is None else f"{base}({length})"),
         "declared_type": base, "declared_kind": "b", "base_type": base, "base_schema": "pg_catalog",
         "base_kind": "b", "base_category": CATEGORY.get(base, "U"), "length": length, "not_null": False,
         "identity": None, "generated": False, "generated_from": [], "foreign_keys": []}
    c.update(kw)
    return c


def fk(table, column="id", schema="public"):
    return [{"schema": schema, "table": table, "column": column}]


def rel(name, columns, schema="public", kind="r", pk=("id",)):
    return {"schema": schema, "name": name, "kind": kind, "primary_key": list(pk), "columns": columns}


def catalog(*relations, schemas=("public",)):
    return {"format": pr.FORMAT, "schemas": list(schemas), "relations": list(relations)}


RULES = {"role": "factory_reader", "database": "app", "schemas": ["public"], "statement_timeout": "15s",
         "temp_file_limit": "1GB", "connection_limit": 8}

USERS = rel("users", [
    col("id", "uuid"), col("email", "varchar", 255), col("display_name", "varchar", 100),
    col("password_hash", "text"), col("created_at", "timestamptz"), col("is_active", "bool"),
    col("status", "varchar", 16), col("bio", "text"), col("preferences", "jsonb"),
])
ORDERS = rel("orders", [
    col("id", "int8", identity="always"), col("user_id", "uuid", foreign_keys=fk("users")),
    col("total_cents", "int8"), col("item_count", "int4"), col("status", "varchar", 20),
    col("note", "text"), col("external_id", "int8"), col("placed_at", "timestamptz"),
])
DOCUMENTS = rel("documents", [
    col("id", "int8"), col("body", "text"),
    col("search", "tsvector", generated=True, generated_from=["body"]),
    col("embedding", "vector", type="vector(1024)", base_schema="public"),
])


def classify(*relations, rules=None, schemas=("public",)):
    return pr.classify(catalog(*relations, schemas=schemas), pr.load_rules(json.dumps(rules or RULES)))


def classes(listing):
    return pr.column_classes(listing)


def run(*argv, stdin=None):
    out = io.StringIO()
    old_stdin = sys.stdin
    try:
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        with contextlib.redirect_stdout(out):
            code = pr.main(list(argv))
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue()


class Heuristics(unittest.TestCase):
    def test_example_tables(self):
        got = classes(classify(USERS, ORDERS))
        self.assertEqual(got["public.users.id"], "allow")
        self.assertEqual(got["public.users.email"], "exclude-personal")
        self.assertEqual(got["public.users.display_name"], "exclude-personal")
        self.assertEqual(got["public.users.password_hash"], "exclude-credential")
        self.assertEqual(got["public.users.created_at"], "allow")
        self.assertEqual(got["public.users.is_active"], "allow")
        self.assertEqual(got["public.users.status"], "allow")
        self.assertEqual(got["public.users.bio"], "review")
        self.assertEqual(got["public.users.preferences"], "review")
        self.assertEqual(got["public.orders.id"], "allow")
        self.assertEqual(got["public.orders.user_id"], "allow")
        self.assertEqual(got["public.orders.total_cents"], "review")
        self.assertEqual(got["public.orders.item_count"], "allow")
        self.assertEqual(got["public.orders.note"], "review")
        self.assertEqual(got["public.orders.external_id"], "review")

    def test_every_type_that_can_hold_anything_is_review(self):
        risky = [col("a", "inet"), col("b", "citext", base_schema="public"), col("c", "money"), col("d", "oid"),
                 col("e", "_int4", base_category="A"), col("f", "bytea"), col("g", "tsvector"),
                 col("h", "vector", base_schema="public"), col("i", "json"), col("j", "varchar"),
                 col("k", "varchar", 1000), col("l", "text"), col("m", "point"), col("n", "int4range", base_kind="r"),
                 col("o", "dom2", declared_kind="d", base_kind="d"), col("p", "address_t", base_kind="c")]
        got = classes(classify(rel("things", [col("id", "int8")] + risky)))
        for c in risky:
            self.assertEqual(got[f"public.things.{c['name']}"], "review", c)

    def test_unknown_short_text_is_review(self):
        # The finding that started this tool: an unrecognised short string must not be allowed by default.
        got = classes(classify(rel("t", [col("id", "int8"), col("promo_hint", "varchar", 40),
                                         col("region", "varchar", 10), col("shipping_kind", "varchar", 10)])))
        self.assertEqual(got["public.t.promo_hint"], "review")
        self.assertEqual(got["public.t.region"], "review")
        self.assertEqual(got["public.t.shipping_kind"], "allow")

    def test_an_id_needs_a_foreign_key_into_the_listing(self):
        got = classes(classify(
            rel("accounts", [col("id", "int8")]),
            rel("events", [col("id", "int8"), col("account_id", "int8", foreign_keys=fk("accounts")),
                           col("partner_id", "int8"), col("UserId", "int8"), col("ref_uuid", "uuid"),
                           col("audit_id", "int8", foreign_keys=fk("log", schema="audit"))]),
            schemas=("public", "audit")))
        self.assertEqual(got["public.events.account_id"], "allow")
        self.assertEqual(got["public.events.partner_id"], "review")
        self.assertEqual(got["public.events.UserId"], "review")  # camelCase reads as user_id
        self.assertEqual(got["public.events.ref_uuid"], "review")
        self.assertEqual(got["public.events.audit_id"], "review")  # its target isn't in a granted schema

    def test_fused_names_fail_closed(self):
        # Unquoted camelCase DDL folds UserId to userid, AuthToken to authtoken.
        got = classes(classify(rel("t", [col("id", "int8"), col("userid", "int8"), col("customerid", "uuid"),
                                         col("authtoken", "varchar", 64), col("sessionid", "int8"),
                                         col("is_valid", "bool")])))
        self.assertEqual(got["public.t.userid"], "review")
        self.assertEqual(got["public.t.customerid"], "review")
        self.assertEqual(got["public.t.authtoken"], "exclude-credential")
        self.assertEqual(got["public.t.sessionid"], "exclude-credential")
        self.assertEqual(got["public.t.is_valid"], "allow")

    def test_a_generated_column_without_lineage_is_review(self):
        got = classes(classify(rel("t", [col("id", "int8"), col("n", "int4"),
                                         col("doubled", "int4", generated=True, generated_from=[]),
                                         col("tripled", "int4", generated=True, generated_from=["n"])])))
        self.assertEqual(got["public.t.doubled"], "review")
        self.assertEqual(got["public.t.tripled"], "allow")

    def test_sensitive_names_beat_structure(self):
        got = classes(classify(
            rel("api_tokens", [col("token", "uuid")], pk=("token",)),
            rel("subscribers", [col("email", "varchar", 100)], pk=("email",)),
            rel("lookups", [col("code", "varchar", 10)], pk=("code",)),
            rel("kinds", [col("label", "varchar", 10)], pk=("label",))))
        self.assertEqual(got["public.api_tokens.token"], "exclude-credential")
        self.assertEqual(got["public.subscribers.email"], "exclude-personal")
        self.assertEqual(got["public.lookups.code"], "exclude-credential")
        self.assertEqual(got["public.kinds.label"], "review")  # a text primary key isn't safe by being a key

    def test_camel_case_names(self):
        self.assertEqual(pr.snake("UserId"), "user_id")
        self.assertEqual(pr.snake("IPAddress"), "ip_address")
        self.assertEqual(pr.snake("createdAt"), "created_at")
        self.assertEqual(pr.snake("APIKey"), "api_key")
        got = classes(classify(rel("AspNetUsers", [col("Id", "uuid"), col("PasswordHash", "text"),
                                                   col("PhoneNumber", "varchar", 30), col("LockoutEnabled", "bool")],
                                   pk=("Id",))))
        self.assertEqual(got["public.AspNetUsers.Id"], "allow")
        self.assertEqual(got["public.AspNetUsers.PasswordHash"], "exclude-credential")
        self.assertEqual(got["public.AspNetUsers.PhoneNumber"], "exclude-personal")
        self.assertEqual(got["public.AspNetUsers.LockoutEnabled"], "allow")

    def test_type_names_count(self):
        got = classes(classify(rel("people", [
            col("id", "int8"), col("g", "gender_t", declared_kind="e", base_kind="e", base_category="E",
                                   base_schema="public"),
            col("tier", "plan_tier", declared_kind="e", base_kind="e", base_category="E", base_schema="public"),
            col("ref", "secret_ref", declared_kind="d", base_type="int8", base_category="N"),
            col("qty", "positive_int", declared_kind="d", base_type="int4", base_category="N")])))
        self.assertEqual(got["public.people.g"], "exclude-personal")
        self.assertEqual(got["public.people.tier"], "allow")
        self.assertEqual(got["public.people.ref"], "exclude-credential")
        self.assertEqual(got["public.people.qty"], "allow")

    def test_payment_tables_and_money(self):
        got = classes(classify(rel("invoices", [col("id", "int8"), col("is_paid", "bool"), col("status", "varchar", 10)]),
                               rel("products", [col("id", "int8"), col("price", "numeric"), col("weight", "numeric")])))
        self.assertEqual(got["public.invoices.id"], "allow")
        self.assertEqual(got["public.invoices.is_paid"], "review")
        self.assertEqual(got["public.invoices.status"], "review")
        self.assertEqual(got["public.products.price"], "review")
        self.assertEqual(got["public.products.weight"], "allow")

    def test_every_non_allow_has_a_reason(self):
        listing = classify(USERS, ORDERS, DOCUMENTS)
        for table, cols in listing["tables"].items():
            for name, entry in cols.items():
                self.assertTrue(entry["reason"], f"{table}.{name}")


class Relations(unittest.TestCase):
    def test_views_and_other_schemas_are_never_granted(self):
        listing = classify(USERS, rel("active_users", [col("id", "uuid")], kind="v", pk=()),
                           rel("user_totals", [col("n", "int8")], kind="m", pk=()),
                           rel("remote", [col("id", "int8")], kind="f", pk=()),
                           rel("trail", [col("id", "int8")], schema="audit"),
                           schemas=("audit", "public"))
        self.assertEqual(sorted(listing["not_granted"]), ["public.active_users", "public.remote", "public.user_totals"])
        self.assertEqual(listing["ungranted_schemas"], ["audit"])
        self.assertEqual(sorted(listing["tables"]), ["public.users"])

    def test_partitions_are_left_to_their_parent(self):
        self.assertIn("not c.relispartition", pr.CATALOG_QUERY)
        self.assertIn("'r', 'p', 'v', 'm', 'f'", pr.CATALOG_QUERY)
        listing = classify(rel("measurements", [col("id", "int8"), col("taken_at", "timestamptz")], kind="p"))
        self.assertEqual(classes(listing)["public.measurements.taken_at"], "allow")

    def test_type_text_does_not_depend_on_the_session(self):
        self.assertEqual(pr.display_type("public.vector(1024)"), "vector(1024)")
        self.assertEqual(pr.display_type('"My Schema".money_t[]'), "money_t[]")
        for same in ("character varying(64)", "numeric(10,2)", "timestamp(3) with time zone", "integer[]"):
            self.assertEqual(pr.display_type(same), same)
        a = classify(rel("t", [col("id", "int8"), col("v", "vector", type="public.vector(3)", base_schema="public")]))
        b = classify(rel("t", [col("id", "int8"), col("v", "vector", type="vector(3)", base_schema="public")]))
        self.assertEqual(pr.render_listing(a), pr.render_listing(b))

    def test_odd_names_are_refused_where_they_would_reach_sql(self):
        for bad in [rel('we"ird', [col("id", "int8")]), rel("t", [col("a b", "int4")]), rel("t", [col("x;", "int4")])]:
            with self.assertRaises(pr.Invalid, msg=bad):
                classify(bad)
        # In a schema the rules don't grant, or as a view, the name never reaches SQL.
        classify(USERS, rel("odd-name", [col("id", "int8")], schema="other"), schemas=("other", "public"))
        classify(USERS, rel("odd view", [col("id", "int8")], kind="v", pk=()))

    def test_a_granted_schema_must_exist(self):
        with self.assertRaisesRegex(pr.Invalid, "aren't in the catalog"):
            classify(USERS, rules=dict(RULES, schemas=["public", "app"]))


class Overrides(unittest.TestCase):
    def test_override_decides_with_its_reason(self):
        listing = classify(ORDERS, USERS, rules=dict(RULES, overrides={
            "public.orders.total_cents": {"class": "allow", "reason": "Order totals; no card data."},
            "public.users.status": {"class": "exclude-content", "reason": "Holds typed notes in practice."}}))
        self.assertEqual(listing["tables"]["public.orders"]["total_cents"]["class"], "allow")
        self.assertEqual(listing["tables"]["public.orders"]["total_cents"]["reason"], "Order totals; no card data.")
        self.assertEqual(listing["tables"]["public.users"]["status"]["class"], "exclude-content")

    def test_bad_overrides(self):
        bad = [
            {"public.orders.note": {"class": "review", "reason": "x"}},
            {"public.orders.note": {"class": "allow"}},
            {"public.orders.note": {"class": "allow", "reason": ""}},
            {"public.orders.note": {"class": "allow", "reason": "two\nlines"}},
            {"public.orders.note": {"class": "allow", "reason": "AUTO: pretending"}},
            {"public.orders.note": {"class": "allow", "reason": "x", "by": "me"}},
            {"public.orders.note": {"class": "maybe", "reason": "x"}},
            {"public.orders.*": {"class": "allow", "reason": "everything"}},
            {"orders.note": {"class": "allow", "reason": "x"}},
            {"public.orders.gone": {"class": "allow", "reason": "stale"}},
            {"public.nothing.*": {"class": "exclude-content", "reason": "stale"}},
        ]
        for overrides in bad:
            with self.assertRaises(pr.Invalid, msg=overrides):
                classify(ORDERS, USERS, rules=dict(RULES, overrides=overrides))

    def test_table_override_excludes_and_a_column_override_wins(self):
        got = classes(classify(ORDERS, USERS, rules=dict(RULES, overrides={
            "public.orders.*": {"class": "exclude-content", "reason": "Whole table held back."},
            "public.orders.id": {"class": "allow", "reason": "Join key."}})))
        self.assertEqual(got["public.orders.item_count"], "exclude-content")
        self.assertEqual(got["public.orders.id"], "allow")


class Derivations(unittest.TestCase):
    def test_generated_and_declared_derivations_follow_their_source(self):
        rules = dict(RULES, overrides={"public.documents.body": {"class": "exclude-content", "reason": "User text."}},
                     derivations={"public.documents.embedding": ["public.documents.body"]})
        got = classes(classify(DOCUMENTS, rules=rules))
        self.assertEqual(got["public.documents.search"], "exclude-content")
        self.assertEqual(got["public.documents.embedding"], "exclude-content")

    def test_a_foreign_key_follows_its_target(self):
        rules = dict(RULES, overrides={"public.users.id": {"class": "exclude-personal", "reason": "Ids are public handles."}})
        listing = classify(USERS, ORDERS, rules=rules)
        self.assertEqual(classes(listing)["public.orders.user_id"], "exclude-personal")
        self.assertIn("derived from public.users.id", listing["tables"]["public.orders"]["user_id"]["reason"])

    def test_chains_settle(self):
        got = classes(classify(
            rel("a", [col("id", "int8"), col("secret_ref", "int8", foreign_keys=fk("a", "id"))]),
            rel("b", [col("id", "int8"), col("a_secret", "int8")]),
            rel("c", [col("id", "int8"), col("b_copy", "int8")]),
            rules=dict(RULES, derivations={"public.c.b_copy": ["public.b.a_secret"],
                                           "public.b.a_secret": ["public.a.secret_ref"]})))
        self.assertEqual(got["public.a.secret_ref"], "exclude-credential")
        self.assertEqual(got["public.b.a_secret"], "exclude-credential")
        self.assertEqual(got["public.c.b_copy"], "exclude-credential")

    def test_an_override_cannot_be_less_restricted_than_its_source(self):
        with self.assertRaisesRegex(pr.Invalid, "decide public.documents.body first"):
            classify(DOCUMENTS, rules=dict(RULES, overrides={
                "public.documents.search": {"class": "allow", "reason": "Only words."}}))
        with self.assertRaisesRegex(pr.Invalid, "isn't a column"):
            classify(DOCUMENTS, rules=dict(RULES, derivations={"public.documents.embedding": ["public.gone.body"]}))


class Rules(unittest.TestCase):
    def test_bad_rules(self):
        bad = [
            {k: v for k, v in RULES.items() if k != "connection_limit"},
            dict(RULES, role="Factory"), dict(RULES, role="pg_reader"), dict(RULES, role="public"),
            dict(RULES, database="app'; drop"), dict(RULES, schemas=[]), dict(RULES, schemas=["pg_catalog"]),
            dict(RULES, schemas=["public", "public"]), dict(RULES, statement_timeout="0"),
            dict(RULES, statement_timeout="15"), dict(RULES, temp_file_limit="-1"),
            dict(RULES, temp_file_limit="1 GB"), dict(RULES, connection_limit=0), dict(RULES, connection_limit=True),
            dict(RULES, app_roles=["factory_reader"]), dict(RULES, app_roles=["bad role"]), dict(RULES, extra=1),
        ]
        for rules in bad:
            with self.assertRaises(pr.Invalid, msg=rules):
                pr.load_rules(json.dumps(rules))

    def test_bad_catalog(self):
        for bad in [{}, dict(catalog(USERS), format="other"), {"format": pr.FORMAT, "schemas": ["public"]},
                    catalog(rel("t", [{"name": "id"}])), catalog(rel("t", [col("id", identity="sometimes")])),
                    catalog(dict(USERS, kind="S"))]:
            with self.assertRaises(pr.Invalid, msg=bad):
                pr.load_catalog(json.dumps(bad))


class Sql(unittest.TestCase):
    def files(self, *relations, rules=None):
        files, _ = pr.build(json.dumps(catalog(*relations)), json.dumps(rules or RULES))
        return files

    def test_create_grants_exactly_the_allowed_columns(self):
        sql = self.files(USERS, ORDERS)[pr.CREATE]
        grants = re.findall(r"GRANT SELECT \(\n(.*?)\n\) ON TABLE (\S+) TO", sql, re.S)
        got = {table: sorted(c.strip(' ,"') for c in cols.replace("\n", " ").split(",")) for cols, table in grants}
        self.assertEqual(got, {'"public"."orders"': ["id", "item_count", "placed_at", "status", "user_id"],
                               '"public"."users"': ["created_at", "id", "is_active", "status"]})
        self.assertNotIn("DEFAULT PRIVILEGES", sql.replace("ALTER DEFAULT PRIVILEGES (a new", ""))
        self.assertNotRegex(sql, r"(?m)^ALTER DEFAULT PRIVILEGES")
        self.assertIn('CONNECTION LIMIT 8', sql)
        self.assertIn("IF current_database() <> 'app' THEN", sql)
        self.assertLess(sql.index("IF current_database() <> 'app'"), sql.index("REVOKE CONNECT ON DATABASE"))
        self.assertIn('REVOKE TEMPORARY ON DATABASE "app" FROM PUBLIC;', sql)
        self.assertIn('GRANT USAGE ON SCHEMA "public" TO "factory_reader";', sql)
        self.assertIn('ALTER ROLE "factory_reader" SET search_path TO "public";', sql)
        self.assertIn("ALTER ROLE \"factory_reader\" SET temp_file_limit = '1GB';", sql)
        self.assertIn("ALTER ROLE \"factory_reader\" SET statement_timeout = '15s';", sql)
        for f in pr.LO_WRITE + pr.LO_SERVER_FILES:
            self.assertIn(f"pg_catalog.{f}", sql)
        self.assertNotIn("GRANT TEMPORARY", sql)

    def test_app_roles_get_back_only_what_public_had(self):
        sql = self.files(USERS, rules=dict(RULES, app_roles=["app_user"]))[pr.CREATE]
        self.assertIn('GRANT TEMPORARY ON DATABASE "app" TO "app_user";', sql)
        grant = sql[sql.index("GRANT EXECUTE ON FUNCTION"):]
        grant = grant[:grant.index(";")]
        for f in pr.LO_WRITE:
            self.assertIn(f, grant)
        self.assertNotIn("lo_import", grant)
        self.assertNotIn("lo_export", grant)

    def test_no_free_text_reaches_the_sql(self):
        rules = dict(RULES, _doc="never in SQL", overrides={
            "public.orders.total_cents": {"class": "allow", "reason": "marker-reason -- ; DROP TABLE x"}})
        files = self.files(ORDERS, USERS, rules=rules)
        for name in (pr.CREATE, pr.VERIFY):
            self.assertNotIn("marker-reason", files[name])
            self.assertNotIn("never in SQL", files[name])

    def test_empty_allow_list_still_renders(self):
        rules = dict(RULES, overrides={"public.t.*": {"class": "exclude-content", "reason": "Nothing to read."}})
        files = self.files(rel("t", [col("id", "int8")]), rules=rules)
        self.assertNotIn("GRANT SELECT", files[pr.CREATE])
        self.assertIn("SELECT NULL::text, NULL::text, NULL::text WHERE false", files[pr.VERIFY])
        self.assertNotRegex(files[pr.VERIFY], r"VALUES\s*\)")

    def test_verify_expects_the_allowed_columns_schema_qualified(self):
        sql = self.files(USERS, ORDERS)[pr.VERIFY]
        self.assertIn("('public', 'orders', 'user_id')", sql)
        self.assertNotIn("'total_cents'", sql)
        self.assertIn("BEGIN TRANSACTION READ ONLY;", sql)
        self.assertIn("rolconnlimit <> 8", sql)
        self.assertIn("'temp_file_limit=1GB'", sql)
        for verb in ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "GRANT", "REVOKE", "TRUNCATE"):
            self.assertNotRegex(sql, rf"(?m)^\s*{verb}\b", verb)

    def test_verify_is_a_superset_of_the_planning_login_check(self):
        script = (FACTORY / "planning-services.sh").read_text()
        check = re.search(r"reader_check=\$\(cat <<'SQL'\n(.*?)\nSQL\n", script, re.S).group(1)
        sql = self.files(USERS)[pr.VERIFY]
        flat = re.sub(r"\s+", "", sql)
        lists = re.findall(r"unnest\(array\[(.*?)\]\) (\w)", check, re.S)
        functions = re.findall(r"'([^']+)'", lists[0][0])
        self.assertGreaterEqual(len(functions), 9)
        for f in functions:
            self.assertIn("pg_catalog." + f.replace(" ", ""), flat, f)
        roles = re.findall(r"'([^']+)'", lists[1][0])
        self.assertGreaterEqual(len(roles), 5)
        for r in roles:
            self.assertIn(f"'{r}'", sql, r)
        # One marker per branch of the login check, and what covers it here. A new branch there fails this test
        # until verify_role.sql covers it and the list grows.
        covered = [
            ("has_function_privilege(f, 'EXECUTE')", ["has_function_privilege("]),
            ("'TEMPORARY')", ["current_database(), 'TEMPORARY')"]),
            ("has_database_privilege(current_database(), 'CREATE')", ["current_database(), 'CREATE')"]),
            ("temp_file_limit", ["c <> 'temp_file_limit=-1'"]),
            ("rolsuper or rolcreaterole or rolcreatedb or rolbypassrls",
             ["rolsuper", "rolcreaterole", "rolcreatedb", "rolbypassrls"]),
            ("pg_has_role(current_user, r, 'MEMBER')", ["pg_has_role("]),
            ("datdba", ["d.datdba = reader.oid"]),
            ("relowner", ["c.relowner = reader.oid"]),
            ("has_schema_privilege(n.oid, 'CREATE')", ["has_schema_privilege('factory_reader', n.oid, 'CREATE')"]),
            ("has_any_column_privilege(c.oid, 'INSERT')", ["'INSERT,UPDATE,REFERENCES'", "DELETE,TRUNCATE"]),
            ("has_sequence_privilege(c.oid, 'UPDATE')", ["has_sequence_privilege('factory_reader', r.oid, 'USAGE,SELECT,UPDATE')"]),
        ]
        branches = re.split(r"\n\s*union all\n", check)
        self.assertEqual(len(branches), len(covered), "planning-services.sh's login check changed: cover it in verify_role.sql")
        for branch, (marker, fragments) in zip(branches, covered):
            self.assertIn(marker, branch)
            for fragment in fragments:
                self.assertIn(fragment, sql, marker)

    def test_catalog_query_is_one_read_only_select(self):
        query = pr.CATALOG_QUERY
        self.assertTrue(query.lstrip().startswith("select json_build_object("))
        self.assertNotIn(";", query)
        for verb in ("insert", "update", "delete", "create", "drop", "alter", "grant", "revoke", "truncate", "copy"):
            self.assertNotRegex(query.lower(), rf"\b{verb}\b", verb)
        for field in ("primary_key", "foreign_keys", "generated_from", "identity", "not_null", "length", "base_type",
                      "conparentid = 0"):
            self.assertIn(field, query)
        code, out = run("catalog-query")
        self.assertEqual((code, out), (0, query))


class Commands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.cat = self.dir / "catalog.json"
        self.rules = self.dir / "rules.json"
        self.out = self.dir / "reader"
        self.cat.write_text(json.dumps(catalog(USERS, ORDERS)))
        self.rules.write_text(json.dumps(RULES))

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, command, stdin=None, catalog_arg=None):
        return run(command, "--catalog", catalog_arg or str(self.cat), "--rules", str(self.rules),
                   "--out", str(self.out), stdin=stdin)

    def test_update_then_check(self):
        code, out = self.cli("update")
        self.assertEqual(code, 0, out)
        self.assertIn("NEW     public.users.email: exclude-personal", out)
        for name in (pr.LISTING, pr.CREATE, pr.VERIFY):
            self.assertTrue((self.out / name).exists())
        listing = json.loads((self.out / pr.LISTING).read_text())
        self.assertEqual(listing["summary"]["total"], 17)
        self.assertEqual(listing["login"]["role"], "factory_reader")
        lines = (self.out / pr.LISTING).read_text().splitlines()
        self.assertTrue(any(line.strip().startswith('"email": {"class": "exclude-personal"') for line in lines))
        self.assertEqual(self.cli("check")[0], 0)
        # Rerunning update changes nothing and reports nothing new.
        before = {n: (self.out / n).read_text() for n in (pr.LISTING, pr.CREATE, pr.VERIFY)}
        code, out = self.cli("update")
        self.assertNotIn("NEW", out)
        self.assertEqual(before, {n: (self.out / n).read_text() for n in before})

    def test_other_schemas_are_printed_not_written(self):
        self.cat.write_text(json.dumps(catalog(USERS, ORDERS, rel("trail", [col("id", "int8")], schema="audit"),
                                               schemas=("audit", "public"))))
        code, out = self.cli("update")
        self.assertIn("schemas not granted (the login reads nothing there): audit", out)
        self.assertNotIn("audit", (self.out / pr.LISTING).read_text())
        # CI's database may lack a schema production has: the listing doesn't change.
        self.cat.write_text(json.dumps(catalog(USERS, ORDERS)))
        self.assertEqual(self.cli("check")[0], 0)

    def test_check_fails_on_a_new_column_until_update(self):
        self.cli("update")
        orders = dict(ORDERS, columns=ORDERS["columns"] + [col("coupon", "varchar", 30)])
        self.cat.write_text(json.dumps(catalog(USERS, orders)))
        code, out = self.cli("check")
        self.assertEqual(code, 1)
        self.assertIn("NEW     public.orders.coupon: review", out)
        self.assertIn("stale: columns.json", out)
        code, out = self.cli("update")
        self.assertIn("NEW     public.orders.coupon: review", out)
        self.assertEqual(self.cli("check")[0], 0)

    def test_check_fails_on_a_hand_edit_and_a_rules_change(self):
        self.cli("update")
        sql = self.out / pr.CREATE
        sql.write_text(sql.read_text().replace('"is_active", ', '"is_active", "email", '))
        self.assertEqual(self.cli("check")[0], 1)
        self.cli("update")
        self.rules.write_text(json.dumps(dict(RULES, connection_limit=12)))
        code, out = self.cli("check")
        self.assertEqual(code, 1)
        self.assertIn(pr.CREATE, out)

    def test_changed_and_gone(self):
        self.cli("update")
        self.rules.write_text(json.dumps(dict(RULES, overrides={
            "public.orders.note": {"class": "exclude-content", "reason": "Typed by customers."}})))
        self.cat.write_text(json.dumps(catalog(USERS, dict(ORDERS, columns=ORDERS["columns"][:-1]))))
        code, out = self.cli("update")
        self.assertIn("CHANGED public.orders.note: review -> exclude-content", out)
        self.assertIn("GONE    public.orders.placed_at", out)

    def test_catalog_from_stdin_and_errors(self):
        code, out = self.cli("update", stdin=self.cat.read_text(), catalog_arg="-")
        self.assertEqual(code, 0, out)
        self.rules.write_text(json.dumps(dict(RULES, overrides={"public.orders.note": {"class": "review", "reason": "x"}})))
        code, out = self.cli("check")
        self.assertEqual(code, 2)
        self.assertIn("::error::planning_reader: override public.orders.note", out)
        code, out = self.cli("check", catalog_arg=str(self.dir / "missing.json"))
        self.assertEqual(code, 2)

    def test_runs_isolated(self):
        r = subprocess.run([sys.executable, "-I", str(FACTORY / "planning_reader.py"), "update", "--catalog",
                            str(self.cat), "--rules", str(self.rules), "--out", str(self.out)],
                           capture_output=True, text=True, cwd=self.tmp.name)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = subprocess.run([sys.executable, "-I", str(FACTORY / "planning_reader.py"), "check", "--catalog",
                            str(self.cat), "--rules", str(self.rules), "--out", str(self.out)],
                           capture_output=True, text=True, cwd=self.tmp.name)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
