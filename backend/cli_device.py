import argparse
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.connection import ASYNC_DB_URL
from db.models.user import User
from db.models.user_device import UserDevice


async def reset_device(identifier: str):
    engine = create_async_engine(ASYNC_DB_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        result = await session.execute(
            select(User).where((User.login == identifier) | (User.phone == identifier))
        )
        user = result.scalar_one_or_none()
        if not user:
            print(f"[ERROR] User '{identifier}' not found in database.")
            await engine.dispose()
            return

        dev_result = await session.execute(
            select(UserDevice).where(UserDevice.user_id == user.id)
        )
        device = dev_result.scalar_one_or_none()
        if device:
            await session.delete(device)
            print(f"[OK] Device '{device.device_name}' (credential_id={device.credential_id[:16]}...) removed.")
        else:
            print(f"[INFO] User '{identifier}' had no registered device.")

        user.token_version += 1
        await session.commit()
        print(f"[SUCCESS] User '{user.login or user.phone}' (id={user.id}) device reset. Active sessions invalidated. User can now bind new PC.")

    await engine.dispose()


async def list_devices():
    engine = create_async_engine(ASYNC_DB_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        result = await session.execute(
            select(UserDevice, User).join(User, User.id == UserDevice.user_id)
        )
        rows = result.all()
        print(f"\n{'ID':<5} {'USER':<20} {'ROLE':<20} {'DEVICE NAME':<25} {'LAST LOGIN':<20}")
        print("-" * 95)
        for dev, user in rows:
            last_login = str(dev.last_login_at)[:19] if dev.last_login_at else "Never"
            name = dev.device_name or "N/A"
            user_label = user.login or user.phone
            print(f"{dev.id:<5} {user_label:<20} {user.role.value:<20} {name:<25} {last_login:<20}")
        print("-" * 95)
        print(f"Total registered devices: {len(rows)}\n")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Prokratura Device Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Reset command
    reset_parser = subparsers.add_parser("reset", help="Reset/unlink a user's PC device")
    reset_parser.add_argument("--login", "-l", required=True, help="Username or phone number")

    # List command
    subparsers.add_parser("list", help="List all registered hardware devices")

    args = parser.parse_args()
    if args.command == "reset":
        asyncio.run(reset_device(args.login))
    elif args.command == "list":
        asyncio.run(list_devices())


if __name__ == "__main__":
    main()
