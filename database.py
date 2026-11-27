import asyncpg
from config import DATABASE_URL

pool: asyncpg.Pool | None = None


def normalize_database_url(url: str) -> str:
    # Render/Postgres URL ba'zan postgres:// ko'rinishida beriladi.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


async def init_db() -> None:
    global pool
    pool = await asyncpg.create_pool(
        normalize_database_url(DATABASE_URL),
        min_size=1,
        max_size=5,
        command_timeout=30,
        ssl="require" if "render.com" in DATABASE_URL else None,
    )
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS business_connections (
                connection_id TEXT PRIMARY KEY,
                owner_user_id BIGINT NOT NULL,
                is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                can_reply BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGSERIAL PRIMARY KEY,
                connection_id TEXT NOT NULL,
                chat_id BIGINT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_memory
                ON chat_messages(connection_id, chat_id, id DESC);

            CREATE TABLE IF NOT EXISTS pending_replies (
                id BIGSERIAL PRIMARY KEY,
                connection_id TEXT NOT NULL,
                chat_id BIGINT NOT NULL,
                sender_user_id BIGINT,
                original_text TEXT NOT NULL,
                suggested_reply TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                resolved_at TIMESTAMPTZ
            );
        """)


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool ishga tushmagan")
    return pool


async def save_message(connection_id: str, chat_id: int, role: str, content: str) -> None:
    async with get_pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO chat_messages(connection_id, chat_id, role, content)
               VALUES($1, $2, $3, $4)""",
            connection_id, chat_id, role, content[:12000]
        )


async def get_history(connection_id: str, chat_id: int, limit: int = 12) -> list[dict]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT role, content FROM (
                   SELECT id, role, content FROM chat_messages
                   WHERE connection_id=$1 AND chat_id=$2
                   ORDER BY id DESC LIMIT $3
               ) recent ORDER BY id ASC""",
            connection_id, chat_id, limit
        )
    return [{"role": row["role"], "content": row["content"]} for row in rows]


async def create_pending(connection_id: str, chat_id: int, sender_user_id: int | None,
                         original_text: str, suggested_reply: str) -> int:
    async with get_pool().acquire() as conn:
        return await conn.fetchval(
            """INSERT INTO pending_replies
               (connection_id, chat_id, sender_user_id, original_text, suggested_reply)
               VALUES($1, $2, $3, $4, $5) RETURNING id""",
            connection_id, chat_id, sender_user_id, original_text[:12000], suggested_reply[:4000]
        )


async def get_pending(pending_id: int):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM pending_replies WHERE id=$1", pending_id
        )


async def resolve_pending(pending_id: int, status: str) -> bool:
    async with get_pool().acquire() as conn:
        result = await conn.execute(
            """UPDATE pending_replies SET status=$2, resolved_at=NOW()
               WHERE id=$1 AND status='pending'""",
            pending_id, status
        )
    return result == "UPDATE 1"


async def save_connection(connection_id: str, owner_user_id: int, enabled: bool,
                          can_reply: bool) -> None:
    async with get_pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO business_connections
               (connection_id, owner_user_id, is_enabled, can_reply, updated_at)
               VALUES($1, $2, $3, $4, NOW())
               ON CONFLICT(connection_id) DO UPDATE SET
                 owner_user_id=EXCLUDED.owner_user_id,
                 is_enabled=EXCLUDED.is_enabled,
                 can_reply=EXCLUDED.can_reply,
                 updated_at=NOW()""",
            connection_id, owner_user_id, enabled, can_reply
        )


async def get_stats() -> dict:
    async with get_pool().acquire() as conn:
        messages = await conn.fetchval("SELECT COUNT(*) FROM chat_messages")
        chats = await conn.fetchval(
            "SELECT COUNT(DISTINCT (connection_id, chat_id)) FROM chat_messages"
        )
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM pending_replies WHERE status='pending'"
        )
        return {"messages": messages, "chats": chats, "pending": pending}


async def close_db() -> None:
    global pool
    if pool:
        await pool.close()
        pool = None
