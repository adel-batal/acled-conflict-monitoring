import os


def get_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def get_env_optional(name: str) -> str | None:
    val = os.getenv(name)
    return val if val else None


class Settings:
    DATABASE_URL: str = get_env("DATABASE_URL")

    JWT_SECRET: str = get_env("JWT_SECRET")
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10"))

    # R1-lite: optional env-seeded admin
    ADMIN_EMAIL: str | None = get_env_optional("ADMIN_EMAIL")
    ADMIN_PASSWORD: str | None = get_env_optional("ADMIN_PASSWORD")


settings = Settings()
