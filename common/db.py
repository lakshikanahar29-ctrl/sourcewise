"""
Parse DATABASE_URL leniently, so passwords with symbols (@ $ # / ?) work without URL-encoding.
Standard parsers split on the first '@' or treat '#' as a fragment; here the host is taken after the LAST '@'.
"""


def parse_database_url(url: str) -> dict:
    rest = url.split("://", 1)[1] if "://" in url else url
    userinfo, _, hostpart = rest.rpartition("@")
    user, _, password = userinfo.partition(":")
    hostport, _, dbpart = hostpart.partition("/")
    host, _, port = hostport.partition(":")
    dbname = dbpart.split("?", 1)[0] or "postgres"
    local = host in ("localhost", "127.0.0.1")
    return {
        "host": host,
        "port": int(port or 5432),
        "user": user,
        "password": password,  # used exactly as typed; no URL-decoding
        "dbname": dbname,
        "sslmode": "prefer" if local else "require",
    }


def connect(url: str):
    import psycopg2
    return psycopg2.connect(**parse_database_url(url))
